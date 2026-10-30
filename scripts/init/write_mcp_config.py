"""Write .cursor/mcp.json for the AWS and Strands MCP servers.

Existing MCP servers in the file are kept. The retired CDK server entry is removed.
"""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("uvx")
    parser.add_argument("region")
    parser.add_argument("profile", nargs="?", default="")
    args = parser.parse_args()

    path = args.root / ".cursor" / "mcp.json"
    existing: dict = {}
    if path.exists():
        existing = json.loads(path.read_text())

    aws_args = [
        "mcp-proxy-for-aws@latest",
        "https://aws-mcp.us-east-1.api.aws/mcp",
    ]
    aws_env = {
        "AWS_REGION": args.region,
        "AWS_DEFAULT_REGION": args.region,
    }
    if args.profile:
        aws_args.extend(["--profile", args.profile])
        aws_env["AWS_PROFILE"] = args.profile
    aws_args.extend(["--metadata", f"AWS_REGION={args.region}"])

    servers = existing.get("mcpServers", {})
    servers.pop("awslabs.cdk-mcp-server", None)
    servers["aws-mcp"] = {
        "type": "stdio",
        "command": args.uvx,
        "args": aws_args,
        "env": aws_env,
    }
    servers["awsdocs"] = {
        "url": "https://knowledge-mcp.global.api.aws",
    }
    servers["strands-agents"] = {
        "type": "stdio",
        "command": args.uvx,
        "args": ["strands-agents-mcp-server"],
        "env": {
            "FASTMCP_LOG_LEVEL": "INFO",
        },
    }
    existing["mcpServers"] = servers
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2) + "\n")


if __name__ == "__main__":
    main()
