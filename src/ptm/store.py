import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ptm.models import ToolSpec
from ptm.package_managers import is_npm_registry_package_type

PTM_TOOLS_DIR = (
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    / "ptm"
    / "tools"
)


@dataclass(frozen=True)
class CleanCandidate:
    bin: str
    tool_dir: Path


def get_tool_dir(bin_name: str, tools_dir: Path = PTM_TOOLS_DIR) -> Path:
    return tools_dir / bin_name


def get_current_dir(bin_name: str, tools_dir: Path = PTM_TOOLS_DIR) -> Path:
    return get_tool_dir(bin_name, tools_dir) / "current"


def write_tool_metadata(spec: ToolSpec, tool_dir: Path, links: list[Path]) -> None:
    tool_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "bin": spec.bin,
        "type": spec.type,
        "links": [str(link) for link in links],
        "installed_at": datetime.now(UTC).isoformat(),
        "ptm_version": "1",
    }
    if is_npm_registry_package_type(spec.type):
        metadata["package"] = spec.package
    (tool_dir / ".ptm.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def is_link_to_tool_dir(path: Path, tool_dir: Path) -> bool:
    if not path.is_symlink():
        return False
    try:
        root = tool_dir.resolve(strict=True)
    except FileNotFoundError:
        return False
    target = path.resolve(strict=False)
    return is_relative_to(target, root)


def collect_clean_candidates(
    configured_tools: list[ToolSpec], tools_dir: Path = PTM_TOOLS_DIR
) -> list[CleanCandidate]:
    configured_bins = {tool.bin for tool in configured_tools}
    if not tools_dir.exists():
        return []

    candidates: list[CleanCandidate] = []
    for tool_dir in sorted(path for path in tools_dir.iterdir() if path.is_dir()):
        if tool_dir.name in configured_bins:
            continue
        if (tool_dir / "current").exists() or (tool_dir / ".ptm.json").exists():
            candidates.append(CleanCandidate(bin=tool_dir.name, tool_dir=tool_dir))
    return candidates
