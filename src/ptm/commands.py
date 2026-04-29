import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import httpx
from rich.table import Table

from ptm.cleaner import apply_clean_candidate, find_clean_candidates
from ptm.console import console
from ptm.installer import do_install
from ptm.models import InstallPlan, ToolSpec
from ptm.resolver import (
    get_comparable_version,
    get_installed_version,
    resolve_install_plan,
    version_status,
)

_MAX_VERSION_CHECK_WORKERS = 8
_UP_TO_DATE = "[green]up-to-date[/green]"


@dataclass(frozen=True)
class _VersionCheck:
    spec: ToolSpec
    installed: str | None
    latest: str | None = None
    status: str = ""
    plan: InstallPlan | None = None
    error: Exception | None = None


def _filter_tools(tools: list[ToolSpec], target: str | None) -> list[ToolSpec]:
    targets = [t for t in tools if target is None or t.bin == target]
    if not targets:
        console.print(f"[red]Tool not found: {target}[/red]")
        sys.exit(1)
    return targets


def cmd_install(
    tools: list[ToolSpec], target: str | None, client: httpx.Client
) -> None:
    failed = False
    for spec in _filter_tools(tools, target):
        installed = get_installed_version(spec)
        if installed is not None and target is None:
            console.print(
                f"[dim]  {spec.bin}: already installed ({installed}), skipping[/dim]"
            )
            continue
        if not do_install(spec, client):
            failed = True
    if failed:
        sys.exit(1)


def cmd_update(tools: list[ToolSpec], target: str | None, client: httpx.Client) -> None:
    failed = False
    checks = _collect_version_checks(
        _filter_tools(tools, target),
        lambda spec: _check_update_version(spec, client),
    )
    for check in checks:
        if check.error is not None:
            console.print(
                f"  [red]{check.spec.bin}: version check failed: {check.error}[/red]"
            )
            failed = True
            continue
        if (
            check.installed is not None
            and check.latest is not None
            and check.status == _UP_TO_DATE
        ):
            console.print(
                f"[dim]  {check.spec.bin}: already up-to-date "
                f"({check.installed}), skipping[/dim]"
            )
            continue
        if not do_install(check.spec, client, update=True, plan=check.plan):
            failed = True
    if failed:
        sys.exit(1)


def _collect_version_checks(
    tools: list[ToolSpec], check: Callable[[ToolSpec], _VersionCheck]
) -> list[_VersionCheck]:
    if not tools:
        return []

    results: list[_VersionCheck | None] = [None] * len(tools)
    workers = min(_MAX_VERSION_CHECK_WORKERS, len(tools))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(check, spec): index for index, spec in enumerate(tools)
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()

    return [result for result in results if result is not None]


def _check_update_version(spec: ToolSpec, client: httpx.Client) -> _VersionCheck:
    installed = get_installed_version(spec)
    try:
        plan = resolve_install_plan(spec, client)
        latest = get_comparable_version(spec, plan.version)
    except Exception as e:
        return _VersionCheck(spec=spec, installed=installed, error=e)

    status = version_status(installed, latest) if latest is not None else ""
    return _VersionCheck(
        spec=spec,
        installed=installed,
        latest=latest,
        status=status,
        plan=plan,
    )


def _check_display_version(spec: ToolSpec, client: httpx.Client) -> _VersionCheck:
    installed = get_installed_version(spec)

    if spec.type == "installer" and not spec.version_url:
        return _VersionCheck(
            spec=spec,
            installed=installed,
            latest="-",
            status=f"[dim]{spec.type}[/dim]",
        )

    if spec.version == "nightly":
        return _VersionCheck(
            spec=spec,
            installed=installed,
            latest="nightly",
            status="[dim]always latest[/dim]",
        )

    try:
        plan = resolve_install_plan(spec, client)
        latest = get_comparable_version(spec, plan.version)
    except Exception as e:
        return _VersionCheck(spec=spec, installed=installed, error=e)

    if latest is None:
        return _VersionCheck(spec=spec, installed=installed, latest="-")

    return _VersionCheck(
        spec=spec,
        installed=installed,
        latest=latest,
        status=version_status(installed, latest),
        plan=plan,
    )


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

    checks = _collect_version_checks(
        tools, lambda spec: _check_display_version(spec, client)
    )
    for check in checks:
        installed_str = check.installed or "[red]not installed[/red]"
        if check.error is not None:
            table.add_row(
                check.spec.bin,
                installed_str,
                f"[red]error: {check.error}[/red]",
                "",
            )
            continue
        table.add_row(check.spec.bin, installed_str, check.latest or "-", check.status)

    console.print(table)


def cmd_clean(tools: list[ToolSpec], apply: bool = False) -> None:
    candidates = find_clean_candidates(tools)
    if not candidates:
        console.print("[dim]No tools to clean.[/dim]")
        return

    table = Table(title="Clean Candidates")
    table.add_column("Bin", style="cyan")
    table.add_column("Directory")
    table.add_column("Action")
    action = "remove" if apply else "dry-run"

    failed = False
    for candidate in candidates:
        table.add_row(candidate.bin, str(candidate.tool_dir), action)

    console.print(table)

    if not apply:
        console.print("[dim]Run with --apply to remove these tools.[/dim]")
        return

    for candidate in candidates:
        try:
            apply_clean_candidate(candidate.tool_dir)
        except Exception as e:
            console.print(f"  [red]{candidate.bin}: clean failed: {e}[/red]")
            failed = True
    if failed:
        sys.exit(1)
