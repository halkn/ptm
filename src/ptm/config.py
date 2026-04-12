import os
import sys
import tomllib
from pathlib import Path

from ptm.console import console
from ptm.models import ToolSpec

BIN_DIR = Path(os.environ.get("XDG_BIN_HOME", Path.home() / ".local" / "bin"))
DEFAULT_TOOLS_TOML = Path(
    os.environ.get("PTM_CONFIG", Path.home() / ".config" / "ptm" / "tools.toml")
)


def load_tools(path: Path) -> list[ToolSpec]:
    if not path.exists():
        console.print(f"[red]Config not found: {path}[/red]")
        console.print("[dim]Create it or specify with --config[/dim]")
        sys.exit(1)
    with open(path, "rb") as f:
        data = tomllib.load(f)
    tools = []
    for t in data.get("github_release", []):
        tools.append(ToolSpec.from_dict({**t, "type": "github_release"}))
    for t in data.get("url_release", []):
        tools.append(ToolSpec.from_dict({**t, "type": "url_release"}))
    for t in data.get("installer", []):
        tools.append(ToolSpec.from_dict({**t, "type": "installer"}))
    for t in data.get("npm", []):
        tools.append(ToolSpec.from_dict({**t, "type": "npm"}))
    return tools
