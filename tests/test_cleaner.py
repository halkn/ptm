from pathlib import Path

from ptm.cleaner import apply_clean_candidate, find_clean_candidates
from ptm.models import ToolSpec


def test_find_clean_candidates_uses_ptm_tools_dir(tmp_path: Path) -> None:
    tools_dir = tmp_path / "tools"
    (tools_dir / "rg" / "current").mkdir(parents=True)
    (tools_dir / "fd" / "current").mkdir(parents=True)

    candidates = find_clean_candidates([ToolSpec(bin="rg")], tools_dir)

    assert [candidate.bin for candidate in candidates] == ["fd"]


def test_apply_clean_candidate_removes_only_links_into_tool_dir(tmp_path: Path) -> None:
    tools_dir = tmp_path / "tools"
    tool_dir = tools_dir / "fd"
    current = tool_dir / "current"
    current.mkdir(parents=True)
    target = current / "fd"
    target.write_text("bin", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    managed_link = bin_dir / "fd"
    managed_link.symlink_to(target)

    external_target = tmp_path / "external" / "cmd"
    external_target.parent.mkdir()
    external_target.write_text("external", encoding="utf-8")
    external_link = bin_dir / "external"
    external_link.symlink_to(external_target)

    apply_clean_candidate(tool_dir, bin_dir)

    assert not tool_dir.exists()
    assert not managed_link.exists()
    assert external_link.is_symlink()
