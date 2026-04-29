import shutil
from pathlib import Path

from ptm.config import BIN_DIR
from ptm.models import ToolSpec
from ptm.store import (
    PTM_TOOLS_DIR,
    CleanCandidate,
    collect_clean_candidates,
    is_link_to_tool_dir,
)


def find_clean_candidates(
    tools: list[ToolSpec], tools_dir: Path = PTM_TOOLS_DIR
) -> list[CleanCandidate]:
    return collect_clean_candidates(tools, tools_dir)


def apply_clean_candidate(tool_dir: Path, bin_dir: Path = BIN_DIR) -> None:
    if bin_dir.exists():
        for path in bin_dir.iterdir():
            if is_link_to_tool_dir(path, tool_dir):
                path.unlink()
    shutil.rmtree(tool_dir)
