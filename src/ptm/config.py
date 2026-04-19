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


def load_tools(path: Path) -> list[ToolSpec]:
    if not path.exists():
        console.print(f"[red]Config not found: {path}[/red]")
        console.print("[dim]Create it or specify with --config[/dim]")
        sys.exit(1)
    data = _load_toml_data(path)
    tools = [_tool_from_named_table(name, raw) for name, raw in _iter_named_tools(data)]
    tools.extend(ToolSpec.from_dict(raw) for raw in _iter_legacy_tools(data))
    return tools


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


def _iter_named_tools(data: dict[str, object]) -> list[tuple[str, dict[str, object]]]:
    raw_tools = data.get("tools")
    if raw_tools is None:
        return []
    if not isinstance(raw_tools, dict):
        _exit_config_error("[tools] must be a table")

    named_tools: list[tuple[str, dict[str, object]]] = []
    for name, raw in raw_tools.items():
        if not isinstance(name, str):
            _exit_config_error("tool names must be strings")
        if not isinstance(raw, dict):
            _exit_config_error(f"[tools.{name}] must be a table")
        named_tools.append((name, {str(key): value for key, value in raw.items()}))
    return named_tools


def _tool_from_named_table(name: str, raw: dict[str, object]) -> ToolSpec:
    tool_data = {key: value for key, value in raw.items()}
    tool_data.setdefault("bin", name)
    return ToolSpec.from_dict(tool_data)


def _iter_legacy_tools(data: dict[str, object]) -> list[dict[str, object]]:
    tools: list[dict[str, object]] = []
    for tool_type in ("github_release", "url_release", "installer", "npm"):
        raw_items = data.get(tool_type, [])
        if not isinstance(raw_items, list):
            _exit_config_error(f"{tool_type} must be an array of tables")
        for raw in raw_items:
            if not isinstance(raw, dict):
                _exit_config_error(f"{tool_type} entries must be tables")
            tool_data = {str(key): value for key, value in raw.items()}
            tools.append({**tool_data, "type": tool_type})
    return tools


def _exit_config_error(message: str) -> Never:
    console.print(f"[red]Invalid config:[/red] {message}")
    sys.exit(1)
