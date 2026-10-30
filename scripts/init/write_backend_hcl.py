"""Write infra/envs/*/backend.hcl from the committed Terraform variables.

The bucket name is {project}-tfstate-{account}. dev and prod must use the same
aws_region as infra/bootstrap.
"""

import argparse
import re
from pathlib import Path


def read_tfvar(path: Path, name: str, root: Path) -> str:
    match = re.search(rf'^{name}\s*=\s*"([^"]+)"\s*$', path.read_text(), re.M)
    if not match:
        raise SystemExit(f"{name} missing from {path.relative_to(root)}")
    return match.group(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("account")
    args = parser.parse_args()

    root = args.root
    bootstrap = root / "infra" / "bootstrap" / "terraform.tfvars"
    dev = root / "infra" / "envs" / "dev" / "terraform.tfvars"
    prod = root / "infra" / "envs" / "prod" / "terraform.tfvars"

    project = read_tfvar(bootstrap, "project", root)
    region = read_tfvar(bootstrap, "aws_region", root)
    for path in (dev, prod):
        env_region = read_tfvar(path, "aws_region", root)
        if env_region != region:
            raise SystemExit(
                f"aws_region in {path.relative_to(root)} is {env_region}, "
                f"but infra/bootstrap uses {region}."
            )

    body = f'bucket = "{project}-tfstate-{args.account}"\nregion = "{region}"\n'
    for env_name in ("dev", "prod"):
        path = root / "infra" / "envs" / env_name / "backend.hcl"
        path.write_text(body)
        print(f"Wrote {path.relative_to(root)}")


if __name__ == "__main__":
    main()
