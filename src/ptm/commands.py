import sys

import httpx
from rich.table import Table

from ptm.config import console
from ptm.installer import do_install
from ptm.models import ToolSpec
from ptm.resolver import (
    get_installed_version,
    get_latest_tag,
    get_url_release_version,
    version_status,
)


def cmd_install(
    tools: list[ToolSpec], target: str | None, client: httpx.Client
) -> None:
    targets = [t for t in tools if target is None or t.bin == target]
    if not targets:
        console.print(f"[red]Tool not found: {target}[/red]")
        sys.exit(1)
    for spec in targets:
        installed = get_installed_version(spec)
        if installed is not None and target is None:
            console.print(
                f"[dim]  {spec.bin}: already installed ({installed}), skipping[/dim]"
            )
            continue
        do_install(spec, client)


def cmd_update(tools: list[ToolSpec], target: str | None, client: httpx.Client) -> None:
    targets = [t for t in tools if target is None or t.bin == target]
    if not targets:
        console.print(f"[red]Tool not found: {target}[/red]")
        sys.exit(1)
    for spec in targets:
        do_install(spec, client, update=True)


def cmd_list(tools: list[ToolSpec]) -> None:
    table = Table(title="Managed Tools")
    table.add_column("Bin", style="cyan")
    table.add_column("Type")
    table.add_column("Version Config")
    table.add_column("Installed")

    for spec in tools:
        installed = get_installed_version(spec)
        installed_str = installed if installed else "[red]not installed[/red]"
        table.add_row(spec.bin, spec.type, spec.version, installed_str)

    console.print(table)


def cmd_check(tools: list[ToolSpec], client: httpx.Client) -> None:
    table = Table(title="Version Check")
    table.add_column("Bin", style="cyan")
    table.add_column("Installed")
    table.add_column("Latest")
    table.add_column("Status")

    for spec in tools:
        installed = get_installed_version(spec)
        installed_str = installed or "[red]not installed[/red]"

        if spec.type == "installer":
            table.add_row(spec.bin, installed_str, "-", "[dim]installer[/dim]")
            continue

        if spec.version == "nightly":
            table.add_row(
                spec.bin, installed_str, "nightly", "[dim]always latest[/dim]"
            )
            continue

        try:
            if spec.type == "url_release":
                latest = get_url_release_version(spec, client).lstrip("v")
            else:
                latest = get_latest_tag(spec, client).lstrip("v")
        except Exception as e:
            table.add_row(spec.bin, installed_str, f"[red]error: {e}[/red]", "")
            continue

        status = version_status(installed, latest)
        table.add_row(spec.bin, installed_str, latest, status)

    console.print(table)
