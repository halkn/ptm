import json
from pathlib import Path

from ptm.models import ToolSpec
from ptm.store import (
    CleanCandidate,
    collect_clean_candidates,
    is_link_to_tool_dir,
    write_tool_metadata,
)


def test_write_tool_metadata_records_links(tmp_path: Path) -> None:
    tool_dir = tmp_path / "tools" / "rg"
    link = tmp_path / "bin" / "rg"
    spec = ToolSpec(bin="rg", type="github_release")

    write_tool_metadata(spec, tool_dir, [link])

    data = json.loads((tool_dir / ".ptm.json").read_text(encoding="utf-8"))
    assert data["bin"] == "rg"
    assert data["type"] == "github_release"
    assert data["links"] == [str(link)]
    assert "installed_at" in data


def test_is_link_to_tool_dir_only_accepts_links_into_tool_dir(tmp_path: Path) -> None:
    tool_dir = tmp_path / "tools" / "rg"
    current = tool_dir / "current"
    current.mkdir(parents=True)
    target = current / "rg"
    target.write_text("bin", encoding="utf-8")

    link = tmp_path / "bin" / "rg"
    link.parent.mkdir()
    link.symlink_to(target)

    external = tmp_path / "bin" / "external"
    external.symlink_to(tmp_path / "elsewhere" / "external")

    assert is_link_to_tool_dir(link, tool_dir)
    assert not is_link_to_tool_dir(external, tool_dir)
    assert not is_link_to_tool_dir(target, tool_dir)


def test_collect_clean_candidates_ignores_configured_tools(tmp_path: Path) -> None:
    tools_dir = tmp_path / "tools"
    (tools_dir / "rg" / "current").mkdir(parents=True)
    (tools_dir / "fd" / "current").mkdir(parents=True)

    candidates = collect_clean_candidates([ToolSpec(bin="rg")], tools_dir)

    assert candidates == [CleanCandidate(bin="fd", tool_dir=tools_dir / "fd")]
