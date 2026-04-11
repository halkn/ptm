"""CLI tool manager - install and update tools via GitHub Releases or official installers."""  # noqa: E501

import argparse
from pathlib import Path

import httpx

from ptm.commands import cmd_check, cmd_install, cmd_list, cmd_update
from ptm.config import DEFAULT_TOOLS_TOML, load_tools


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "CLI tool manager - install/update tools"
            " via GitHub Releases or official installers"
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_TOOLS_TOML,
        metavar="PATH",
        help=f"Path to tools.toml (default: {DEFAULT_TOOLS_TOML})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_install = subparsers.add_parser(
        "install", help="Install tools (skip if already installed)"
    )
    p_install.add_argument("tool", nargs="?", help="Tool name (default: all)")

    p_update = subparsers.add_parser("update", help="Update tools to latest version")
    p_update.add_argument("tool", nargs="?", help="Tool name (default: all)")

    subparsers.add_parser("list", help="List all tools with installed version")
    subparsers.add_parser("check", help="Compare installed vs latest version")

    args = parser.parse_args()
    tools = load_tools(args.config)

    if args.command == "list":
        cmd_list(tools)
        return

    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        match args.command:
            case "install":
                cmd_install(tools, args.tool, client)
            case "update":
                cmd_update(tools, args.tool, client)
            case "check":
                cmd_check(tools, client)


if __name__ == "__main__":
    main()
