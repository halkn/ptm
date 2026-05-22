import os
import sys
import tomllib
from pathlib import Path
from typing import Never

from ptm.console import console
from ptm.models import ToolSpec

BIN_DIR = Path(os.environ.get("XDG_BIN_HOME", Path.home() / ".local" / "bin"))
DEFAULT_TOOLS_TOML = Path(
    os.environ.get("PTM_CONFIG", Path.home() / ".config" / "ptm" / "config.toml")
)

_SOURCE_BACKENDS: dict[str, str] = {
    "github": "github_release",
    "url": "url_release",
    "installer": "installer",
    "npm": "npm",
    "bun": "bun",
}


def load_tools(path: Path) -> list[ToolSpec]:
    if not path.exists():
        console.print(f"[red]Config not found: {path}[/red]")
        console.print("[dim]Create it or specify with --config[/dim]")
        sys.exit(1)
    data = _load_toml_data(path)
    return [_tool_from_entry(name, raw) for name, raw in _iter_tool_entries(data)]


def _load_toml_data(path: Path) -> dict[str, object]:
    if path.suffix.lower() != ".toml":
        console.print(f"[red]Unsupported config format: {path.suffix}[/red]")
        console.print("[dim]Use .toml[/dim]")
        sys.exit(1)

    with path.open("rb") as f:
        data = tomllib.load(f)

    if not isinstance(data, dict):
        console.print("[red]Config root must be a mapping[/red]")
        sys.exit(1)
    return data


def _iter_tool_entries(data: dict[str, object]) -> list[tuple[str, str | dict]]:
    raw_tools = data.get("tools")
    if raw_tools is None:
        _exit_config_error("missing [tools] table")
    if not isinstance(raw_tools, dict):
        _exit_config_error("[tools] must be a table")

    entries: list[tuple[str, str | dict]] = []
    for name, raw in raw_tools.items():
        if not isinstance(name, str):
            _exit_config_error("tool names must be strings")
        if not isinstance(raw, (str, dict)):
            _exit_config_error(f"[tools.{name}] must be a source string or a table")
        entries.append((name, raw))
    return entries


def _tool_from_entry(name: str, raw: str | dict) -> ToolSpec:
    if isinstance(raw, str):
        tool_data = _parse_source(name, raw)
    else:
        tool_data = _tool_data_from_table(name, raw)
    tool_data.setdefault("bin", name)
    return ToolSpec.from_dict(tool_data)


def _tool_data_from_table(name: str, raw: dict) -> dict[str, object]:
    table = {str(key): value for key, value in raw.items()}
    source = table.pop("source", None)
    if source is None:
        _exit_config_error(f"[tools.{name}] missing 'source'")
    if not isinstance(source, str):
        _exit_config_error(f"[tools.{name}].source must be a string")
    tool_data = _parse_source(name, source)
    tool_data.update(table)
    return tool_data


def _parse_source(name: str, source: str) -> dict[str, object]:
    backend, _, rest = source.partition(":")
    tool_type = _SOURCE_BACKENDS.get(backend)
    if tool_type is None:
        backends = ", ".join(sorted(_SOURCE_BACKENDS))
        _exit_config_error(
            f"[tools.{name}] unknown source backend '{backend}'; use one of: {backends}"
        )

    locator, version = _split_version(rest)
    tool_data: dict[str, object] = {"type": tool_type}
    if version:
        tool_data["version"] = version

    if tool_type == "github_release":
        if not locator:
            _exit_config_error(f"[tools.{name}] github source needs 'owner/repo'")
        tool_data["repo"] = locator
    elif tool_type in {"npm", "bun"}:
        if locator:
            tool_data["package"] = locator
    elif tool_type == "installer":
        if locator:
            tool_data["url"] = locator
    # url_release carries no locator; configure platforms/version_url in table form.
    return tool_data


def _split_version(rest: str) -> tuple[str, str | None]:
    at = rest.rfind("@")
    if at > 0 and "/" not in rest[at:]:
        return rest[:at], rest[at + 1 :]
    return rest, None


def _exit_config_error(message: str) -> Never:
    console.print(f"[red]Invalid config:[/red] {message}")
    sys.exit(1)
