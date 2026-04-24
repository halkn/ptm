from typing import NotRequired, TypedDict, Unpack
from unittest.mock import MagicMock, patch

import pytest

from ptm.commands import cmd_check, cmd_install, cmd_list, cmd_update
from ptm.models import InstallPlan, ToolSpec


class ToolSpecOverrides(TypedDict):
    bin: NotRequired[str]
    type: NotRequired[str]
    version: NotRequired[str]
    repo: NotRequired[str]
    command: NotRequired[str]
    version_url: NotRequired[str]


def _make_spec(**kwargs: Unpack[ToolSpecOverrides]) -> ToolSpec:
    spec = ToolSpec(bin="rg", type="github_release", repo="BurntSushi/ripgrep")
    for key, value in kwargs.items():
        setattr(spec, key, value)
    return spec


# ---- cmd_install ------------------------------------------------------------


class TestCmdInstall:
    def test_installs_when_not_installed(self):
        tools = [_make_spec(bin="rg")]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value=None),
            patch("ptm.commands.do_install") as mock_do,
        ):
            cmd_install(tools, None, client)
        mock_do.assert_called_once_with(tools[0], client)

    def test_skips_already_installed_when_no_target(self):
        tools = [_make_spec(bin="rg")]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value="14.1.0"),
            patch("ptm.commands.do_install") as mock_do,
        ):
            cmd_install(tools, None, client)
        mock_do.assert_not_called()

    def test_reinstalls_when_target_is_specified(self):
        tools = [_make_spec(bin="rg")]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value="14.1.0"),
            patch("ptm.commands.do_install") as mock_do,
        ):
            cmd_install(tools, "rg", client)
        mock_do.assert_called_once()

    def test_installs_only_specified_target(self):
        tools = [_make_spec(bin="rg"), _make_spec(bin="fd", repo="sharkdp/fd")]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value=None),
            patch("ptm.commands.do_install") as mock_do,
        ):
            cmd_install(tools, "rg", client)
        assert mock_do.call_count == 1
        assert mock_do.call_args[0][0].bin == "rg"

    def test_exits_when_target_not_found(self):
        tools = [_make_spec(bin="rg")]
        client = MagicMock()
        with pytest.raises(SystemExit):
            cmd_install(tools, "nonexistent", client)


# ---- cmd_update -------------------------------------------------------------


class TestCmdUpdate:
    def test_updates_all_tools(self):
        tools = [_make_spec(bin="rg"), _make_spec(bin="fd", repo="sharkdp/fd")]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value=None),
            patch(
                "ptm.commands.resolve_install_plan",
                side_effect=[InstallPlan(tools[0]), InstallPlan(tools[1])],
            ),
            patch("ptm.commands.do_install") as mock_do,
        ):
            cmd_update(tools, None, client)
        assert mock_do.call_count == 2
        for c in mock_do.call_args_list:
            assert c[1]["update"] is True

    def test_updates_only_specified_target(self):
        tools = [_make_spec(bin="rg"), _make_spec(bin="fd", repo="sharkdp/fd")]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value=None),
            patch(
                "ptm.commands.resolve_install_plan",
                return_value=InstallPlan(tools[0]),
            ),
            patch("ptm.commands.do_install") as mock_do,
        ):
            cmd_update(tools, "rg", client)
        assert mock_do.call_count == 1
        assert mock_do.call_args[0][0].bin == "rg"

    def test_exits_when_target_not_found(self):
        tools = [_make_spec(bin="rg")]
        client = MagicMock()
        with pytest.raises(SystemExit):
            cmd_update(tools, "nonexistent", client)

    def test_skips_up_to_date_github_release(self):
        tools = [_make_spec(bin="rg", version="latest")]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value="14.1.0"),
            patch(
                "ptm.commands.resolve_install_plan",
                return_value=InstallPlan(tools[0], version="v14.1.0"),
            ),
            patch("ptm.commands.do_install") as mock_do,
        ):
            cmd_update(tools, None, client)
        mock_do.assert_not_called()

    def test_skips_up_to_date_url_release(self):
        tools = [
            ToolSpec(bin="node", type="url_release", version_url="https://nodejs.org")
        ]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value="22.0.0"),
            patch(
                "ptm.commands.resolve_install_plan",
                return_value=InstallPlan(tools[0], version="v22.0.0"),
            ),
            patch("ptm.commands.do_install") as mock_do,
        ):
            cmd_update(tools, None, client)
        mock_do.assert_not_called()

    def test_updates_outdated_tool(self):
        tools = [_make_spec(bin="rg", version="latest")]
        client = MagicMock()
        plan = InstallPlan(tools[0], version="v14.1.0")
        with (
            patch("ptm.commands.get_installed_version", return_value="14.0.0"),
            patch("ptm.commands.resolve_install_plan", return_value=plan),
            patch("ptm.commands.do_install") as mock_do,
        ):
            cmd_update(tools, None, client)
        mock_do.assert_called_once_with(tools[0], client, update=True, plan=plan)


# ---- cmd_list ---------------------------------------------------------------


class TestCmdList:
    def test_shows_installed_version(self):
        tools = [_make_spec(bin="rg")]
        with patch("ptm.commands.get_installed_version", return_value="14.1.0"):
            cmd_list(tools)  # 例外なく完了すること

    def test_shows_not_installed(self):
        tools = [_make_spec(bin="rg")]
        with patch("ptm.commands.get_installed_version", return_value=None):
            cmd_list(tools)


# ---- cmd_check --------------------------------------------------------------


class TestCmdCheck:
    def test_github_release_up_to_date(self):
        tools = [_make_spec(bin="rg", version="latest")]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value="14.1.0"),
            patch(
                "ptm.commands.resolve_install_plan",
                return_value=InstallPlan(tools[0], version="v14.1.0"),
            ),
        ):
            cmd_check(tools, client)

    def test_installer_type_skips_version_fetch(self):
        tools = [ToolSpec(bin="uv", type="installer", command="install.sh")]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value="0.5.0"),
            patch("ptm.commands.resolve_install_plan") as mock_plan,
        ):
            cmd_check(tools, client)
        mock_plan.assert_not_called()

    def test_installer_type_fetches_version_when_version_url_is_set(self):
        tools = [
            ToolSpec(
                bin="uv",
                type="installer",
                command="install.sh",
                version_url="https://example.com/uv.json",
            )
        ]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value="0.5.0"),
            patch(
                "ptm.commands.resolve_install_plan",
                return_value=InstallPlan(tools[0], version="0.5.1"),
            ) as mock_plan,
        ):
            cmd_check(tools, client)
        mock_plan.assert_called_once_with(tools[0], client)

    def test_npm_type_fetches_version(self):
        tools = [ToolSpec(bin="markdownlint-cli2", type="npm")]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value="0.15.0"),
            patch(
                "ptm.commands.resolve_install_plan",
                return_value=InstallPlan(tools[0], version="0.15.0"),
            ) as mock_plan,
        ):
            cmd_check(tools, client)
        mock_plan.assert_called_once_with(tools[0], client)

    def test_nightly_skips_version_fetch(self):
        tools = [_make_spec(bin="nvim", version="nightly")]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value="0.10.0-dev"),
            patch("ptm.commands.resolve_install_plan") as mock_plan,
        ):
            cmd_check(tools, client)
        mock_plan.assert_not_called()

    def test_url_release_fetches_url_version(self):
        tools = [
            ToolSpec(bin="node", type="url_release", version_url="https://nodejs.org")
        ]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value="22.0.0"),
            patch(
                "ptm.commands.resolve_install_plan",
                return_value=InstallPlan(tools[0], version="v22.0.0"),
            ),
        ):
            cmd_check(tools, client)

    def test_handles_version_fetch_error_gracefully(self):
        tools = [_make_spec(bin="rg")]
        client = MagicMock()
        with (
            patch("ptm.commands.get_installed_version", return_value="14.0.0"),
            patch(
                "ptm.commands.resolve_install_plan",
                side_effect=RuntimeError("API error"),
            ),
        ):
            cmd_check(tools, client)  # 例外が外に漏れないこと
