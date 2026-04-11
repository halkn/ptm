import textwrap
from pathlib import Path

import pytest

from ptm.config import load_tools


def test_load_tools_github_release(tmp_path: Path):
    toml = tmp_path / "tools.toml"
    toml.write_text(
        textwrap.dedent("""\
        [[github_release]]
        bin = "rg"
        repo = "BurntSushi/ripgrep"

        [github_release.platforms]
        linux-x86_64 = "ripgrep-{version}-x86_64.tar.gz"
        """)
    )
    tools = load_tools(toml)
    assert len(tools) == 1
    assert tools[0].bin == "rg"
    assert tools[0].type == "github_release"
    assert tools[0].repo == "BurntSushi/ripgrep"


def test_load_tools_all_types(tmp_path: Path):
    toml = tmp_path / "tools.toml"
    toml.write_text(
        textwrap.dedent("""\
        [[github_release]]
        bin = "rg"
        repo = "BurntSushi/ripgrep"

        [[url_release]]
        bin = "node"
        version_url = "https://nodejs.org/dist/index.json"

        [[installer]]
        bin = "uv"
        url = "https://astral.sh/uv/install.sh"
        """)
    )
    tools = load_tools(toml)
    assert len(tools) == 3
    types = {t.type for t in tools}
    assert types == {"github_release", "url_release", "installer"}


def test_load_tools_exits_when_file_not_found(tmp_path: Path):
    with pytest.raises(SystemExit):
        load_tools(tmp_path / "nonexistent.toml")
