import textwrap
from pathlib import Path

import pytest

from ptm.config import load_tools


def test_load_tools_named_table_github_release(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools.rg]
        type = "github_release"
        repo = "BurntSushi/ripgrep"

        [tools.rg.platforms]
        linux-x86_64 = "ripgrep-{version}-x86_64.tar.gz"
        """),
        encoding="utf-8",
    )
    tools = load_tools(config)
    assert len(tools) == 1
    assert tools[0].bin == "rg"
    assert tools[0].type == "github_release"
    assert tools[0].repo == "BurntSushi/ripgrep"


def test_load_tools_named_table_all_types(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools.rg]
        type = "github_release"
        repo = "BurntSushi/ripgrep"

        [tools.node]
        type = "url_release"
        version_url = "https://nodejs.org/dist/index.json"

        [tools.uv]
        type = "installer"
        url = "https://astral.sh/uv/install.sh"

        [tools.markdownlint-cli2]
        type = "npm"
        """),
        encoding="utf-8",
    )
    tools = load_tools(config)
    assert len(tools) == 4
    types = {t.type for t in tools}
    assert types == {"github_release", "url_release", "installer", "npm"}


def test_load_tools_named_table_uses_key_as_default_bin(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools.uv]
        type = "installer"
        command = "echo install"
        """),
        encoding="utf-8",
    )

    tools = load_tools(config)

    assert len(tools) == 1
    assert tools[0].bin == "uv"
    assert tools[0].type == "installer"


def test_load_tools_legacy_toml_is_still_supported(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [[github_release]]
        bin = "rg"
        repo = "BurntSushi/ripgrep"
        """),
        encoding="utf-8",
    )

    tools = load_tools(config)

    assert len(tools) == 1
    assert tools[0].bin == "rg"


def test_load_tools_supports_mixed_named_and_legacy_formats(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools.uv]
        type = "installer"
        command = "echo install"

        [[npm]]
        bin = "markdownlint-cli2"
        """),
        encoding="utf-8",
    )

    tools = load_tools(config)

    assert len(tools) == 2
    assert {tool.bin for tool in tools} == {"uv", "markdownlint-cli2"}


def test_load_tools_exits_when_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        load_tools(tmp_path / "nonexistent.toml")


def test_load_tools_exits_for_unsupported_format(tmp_path: Path) -> None:
    config = tmp_path / "tools.yaml"
    config.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit):
        load_tools(config)


def test_load_tools_exits_when_tools_is_not_table(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text('tools = "invalid"', encoding="utf-8")

    with pytest.raises(SystemExit):
        load_tools(config)
