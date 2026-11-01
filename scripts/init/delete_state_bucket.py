"""Delete the bootstrap Terraform state bucket.

infra/bootstrap protects that bucket with prevent_destroy, so terraform destroy
will not remove it. This deletes the bucket directly after checking that the
name is {project}-tfstate-{account} for the current credentials and that the
bootstrap state contains only the bucket and its settings.
"""

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


MANAGED_TYPES = frozenset(
    {
        "aws_s3_bucket",
        "aws_s3_bucket_lifecycle_configuration",
        "aws_s3_bucket_ownership_controls",
        "aws_s3_bucket_policy",
        "aws_s3_bucket_public_access_block",
        "aws_s3_bucket_server_side_encryption_configuration",
        "aws_s3_bucket_versioning",
    }
)


def read_tfvar(path: Path, name: str) -> str:
    match = re.search(rf'^{name}\s*=\s*"([^"]+)"\s*$', path.read_text(), re.M)
    if not match:
        raise SystemExit(f"{name} missing from {path}")
    return match.group(1)


def aws_command(*args: str) -> list[str]:
    command = ["aws"]
    profile = os.environ.get("AWS_PROFILE", "")
    if profile:
        command.extend(["--profile", profile])
    command.extend(args)
    return command


def run_aws(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        aws_command(*args),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SystemExit(f"aws {' '.join(args)} failed: {detail}")
    return result


def account_id() -> str:
    result = run_aws(
        ["sts", "get-caller-identity", "--query", "Account", "--output", "text"]
    )
    account = result.stdout.strip()
    if not re.fullmatch(r"\d{12}", account):
        raise SystemExit("Could not read a 12-digit account id from AWS credentials.")
    return account


def state_bucket(state: dict, project: str, account: str, region: str) -> str | None:
    managed = [
        resource
        for resource in state.get("resources", [])
        if resource.get("mode", "managed") == "managed"
    ]
    unexpected = sorted(
        {
            resource.get("type", "")
            for resource in managed
            if resource.get("type") not in MANAGED_TYPES
        }
    )
    if unexpected:
        raise SystemExit(
            "Bootstrap state has resources this cleanup does not delete: "
            + ", ".join(unexpected)
        )

    buckets = [resource for resource in managed if resource.get("type") == "aws_s3_bucket"]
    if not buckets:
        return None
    if len(buckets) != 1 or len(buckets[0].get("instances") or []) != 1:
        raise SystemExit("Bootstrap state does not have exactly one state bucket.")

    attributes = buckets[0]["instances"][0].get("attributes") or {}
    name = attributes.get("bucket") or attributes.get("id")
    if not name:
        raise SystemExit("Bootstrap state bucket has no name.")

    output = (state.get("outputs") or {}).get("state_bucket_name", {}).get("value")
    if output != name:
        raise SystemExit("Bootstrap state output does not match the bucket resource.")

    state_region = (state.get("outputs") or {}).get("state_bucket_region", {}).get("value")
    if state_region != region:
        raise SystemExit(
            "State bucket region does not match infra/bootstrap/terraform.tfvars."
        )

    expected = f"{project}-tfstate-{account}"
    if name != expected:
        raise SystemExit(
            "Refusing to delete the state bucket because its name does not match "
            f"{project}-tfstate-<account> for the current AWS credentials."
        )
    return name


def bucket_exists(bucket: str, region: str) -> bool:
    result = subprocess.run(
        aws_command("s3api", "head-bucket", "--bucket", bucket, "--region", region),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True
    detail = f"{result.stderr}\n{result.stdout}"
    if "404" in detail or "Not Found" in detail or "NoSuchBucket" in detail:
        return False
    raise SystemExit(f"Could not inspect state bucket: {detail.strip()}")


def delete_versions(bucket: str, region: str) -> None:
    key_marker = ""
    version_marker = ""
    while True:
        args = [
            "s3api",
            "list-object-versions",
            "--bucket",
            bucket,
            "--region",
            region,
            "--output",
            "json",
        ]
        if key_marker:
            args.extend(["--key-marker", key_marker])
        if version_marker:
            args.extend(["--version-id-marker", version_marker])
        data = json.loads(run_aws(args).stdout or "{}")
        objects = [
            {"Key": item["Key"], "VersionId": item["VersionId"]}
            for item in (data.get("Versions") or []) + (data.get("DeleteMarkers") or [])
        ]
        for start in range(0, len(objects), 1000):
            chunk = objects[start : start + 1000]
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
                json.dump({"Objects": chunk, "Quiet": False}, handle)
                payload = handle.name
            try:
                deleted = json.loads(
                    run_aws(
                        [
                            "s3api",
                            "delete-objects",
                            "--bucket",
                            bucket,
                            "--region",
                            region,
                            "--delete",
                            f"file://{payload}",
                            "--output",
                            "json",
                        ]
                    ).stdout
                    or "{}"
                )
            finally:
                os.unlink(payload)
            errors = deleted.get("Errors") or []
            if errors:
                raise SystemExit(f"Could not empty the state bucket: {errors[0]}")

        if not data.get("IsTruncated"):
            return
        next_key = data.get("NextKeyMarker") or ""
        next_version = data.get("NextVersionIdMarker") or ""
        if not next_key or (next_key == key_marker and next_version == version_marker):
            raise SystemExit("Listing state bucket versions did not advance.")
        key_marker = next_key
        version_marker = next_version


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()

    root = args.root
    state_path = root / "infra" / "bootstrap" / "terraform.tfstate"
    if not state_path.exists():
        print("No bootstrap state file. The state bucket was not deleted.")
        return

    tfvars = root / "infra" / "bootstrap" / "terraform.tfvars"
    project = read_tfvar(tfvars, "project")
    region = read_tfvar(tfvars, "aws_region")
    state = json.loads(state_path.read_text())
    bucket = state_bucket(state, project, account_id(), region)
    if bucket is None:
        print("Bootstrap state has no state bucket.")
        return
    if not bucket_exists(bucket, region):
        print(f"State bucket {bucket} is already gone.")
        return

    print(f"Deleting state bucket {bucket}...")
    delete_versions(bucket, region)
    run_aws(["s3api", "delete-bucket", "--bucket", bucket, "--region", region])
    print(f"Deleted state bucket {bucket}.")


if __name__ == "__main__":
    main()
