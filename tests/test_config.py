import textwrap
from pathlib import Path

import pytest

from ptm.config import load_tools


def test_load_tools_github_release_source_string(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools]
        rg = "github:BurntSushi/ripgrep"
        """),
        encoding="utf-8",
    )
    tools = load_tools(config)
    assert len(tools) == 1
    assert tools[0].bin == "rg"
    assert tools[0].type == "github_release"
    assert tools[0].repo == "BurntSushi/ripgrep"
    assert tools[0].version == "latest"


def test_load_tools_source_string_all_backends(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools]
        rg = "github:BurntSushi/ripgrep"
        markdownlint-cli2 = "npm:markdownlint-cli2"
        prettier = "bun:prettier"

        [tools.node]
        source = "url"
        version_url = "https://nodejs.org/dist/index.json"

        [tools.uv]
        source = "installer:https://astral.sh/uv/install.sh"
        """),
        encoding="utf-8",
    )
    tools = load_tools(config)
    assert len(tools) == 5
    types = {t.type for t in tools}
    assert types == {"github_release", "url_release", "installer", "npm", "bun"}


def test_load_tools_source_string_pins_version(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools]
        prettier = "npm:prettier@3.2.0"
        """),
        encoding="utf-8",
    )
    tools = load_tools(config)
    assert tools[0].package == "prettier"
    assert tools[0].version == "3.2.0"


def test_load_tools_source_string_pins_github_version(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools]
        nvim = "github:neovim/neovim@nightly"
        """),
        encoding="utf-8",
    )
    tools = load_tools(config)
    assert tools[0].repo == "neovim/neovim"
    assert tools[0].version == "nightly"


def test_load_tools_npm_scoped_package(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools]
        ng = "npm:@angular/cli@18"
        """),
        encoding="utf-8",
    )
    tools = load_tools(config)
    assert tools[0].package == "@angular/cli"
    assert tools[0].version == "18"


def test_load_tools_npm_package_defaults_to_bin(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools]
        tsc = "npm:typescript"
        """),
        encoding="utf-8",
    )
    tools = load_tools(config)
    assert tools[0].bin == "tsc"
    assert tools[0].package == "typescript"


def test_load_tools_table_form_overrides_source(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools.nvim]
        source = "github:neovim/neovim"
        version = "nightly"
        bin_path_in_archive = "bin/nvim"
        """),
        encoding="utf-8",
    )
    tools = load_tools(config)
    assert tools[0].bin == "nvim"
    assert tools[0].repo == "neovim/neovim"
    assert tools[0].version == "nightly"
    assert tools[0].bin_path_in_archive == "bin/nvim"


def test_load_tools_uses_key_as_default_bin(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools.uv]
        source = "installer:https://astral.sh/uv/install.sh"
        """),
        encoding="utf-8",
    )

    tools = load_tools(config)

    assert len(tools) == 1
    assert tools[0].bin == "uv"
    assert tools[0].type == "installer"
    assert tools[0].url == "https://astral.sh/uv/install.sh"


def test_load_tools_exits_for_unknown_backend(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools]
        rg = "cargo:ripgrep"
        """),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        load_tools(config)


def test_load_tools_exits_when_github_source_missing_repo(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools]
        rg = "github:"
        """),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        load_tools(config)


def test_load_tools_exits_when_table_missing_source(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [tools.rg]
        version = "latest"
        """),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        load_tools(config)


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


def test_load_tools_exits_when_tools_table_is_missing(tmp_path: Path) -> None:
    config = tmp_path / "tools.toml"
    config.write_text(
        textwrap.dedent("""\
        [github_release.rg]
        repo = "BurntSushi/ripgrep"
        """),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        load_tools(config)
