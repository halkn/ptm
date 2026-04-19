import subprocess
from unittest.mock import MagicMock, patch

import pytest

from ptm.models import ToolSpec
from ptm.resolver import (
    _get_latest_tag_via_gh,
    _score_asset_name,
    detect_platform,
    get_comparable_latest_version,
    get_installed_version,
    get_latest_tag,
    get_npm_latest_version,
    get_url_release_version,
    resolve_asset_url,
    resolve_github_release_asset,
    resolve_url_release_asset,
    resolve_url_release_url,
    version_status,
)


class TestDetectPlatform:
    def test_linux_x86_64(self):
        with (
            patch("platform.system", return_value="Linux"),
            patch("platform.machine", return_value="x86_64"),
        ):
            assert detect_platform() == "linux-x86_64"

    def test_darwin_arm64(self):
        with (
            patch("platform.system", return_value="Darwin"),
            patch("platform.machine", return_value="arm64"),
        ):
            assert detect_platform() == "darwin-arm64"

    def test_aarch64_is_normalized_to_arm64(self):
        with (
            patch("platform.system", return_value="Linux"),
            patch("platform.machine", return_value="aarch64"),
        ):
            assert detect_platform() == "linux-arm64"


class TestVersionStatus:
    def test_not_installed(self):
        assert version_status(None, "1.0.0") == "[red]not installed[/red]"

    def test_up_to_date_exact_match(self):
        assert version_status("1.0.0", "1.0.0") == "[green]up-to-date[/green]"

    def test_up_to_date_with_v_prefix(self):
        assert version_status("v1.0.0", "1.0.0") == "[green]up-to-date[/green]"

    def test_up_to_date_does_not_strip_multiple_v(self):
        assert version_status("vv1.0.0", "1.0.0") == "[yellow]outdated[/yellow]"

    def test_outdated(self):
        assert version_status("1.0.0", "1.1.0") == "[yellow]outdated[/yellow]"


class TestGetInstalledVersion:
    def test_returns_version_on_success(self):
        spec = ToolSpec(bin="rg", version_regex=r"ripgrep (\S+)")
        with patch("subprocess.check_output", return_value="ripgrep 14.1.0\n"):
            assert get_installed_version(spec) == "14.1.0"

    def test_returns_none_when_not_found(self):
        spec = ToolSpec(bin="nonexistent")
        with patch("subprocess.check_output", side_effect=FileNotFoundError):
            assert get_installed_version(spec) is None

    def test_returns_none_on_error(self):
        spec = ToolSpec(bin="rg")
        with patch(
            "subprocess.check_output",
            side_effect=subprocess.CalledProcessError(1, "rg"),
        ):
            assert get_installed_version(spec) is None

    def test_returns_unknown_when_regex_does_not_match(self):
        spec = ToolSpec(bin="rg", version_regex=r"version: (\S+)")
        with patch("subprocess.check_output", return_value="no version here"):
            assert get_installed_version(spec) == "unknown"


class TestGetLatestTagViaGh:
    def test_returns_tag_when_gh_succeeds(self):
        spec = ToolSpec(bin="rg", repo="BurntSushi/ripgrep")
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="14.1.0\n",
            stderr="",
        )
        with patch("subprocess.run", return_value=completed):
            assert _get_latest_tag_via_gh(spec) == "14.1.0"

    def test_returns_none_when_gh_is_missing(self):
        spec = ToolSpec(bin="rg", repo="BurntSushi/ripgrep")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert _get_latest_tag_via_gh(spec) is None

    def test_returns_none_when_gh_auth_fails(self):
        spec = ToolSpec(bin="rg", repo="BurntSushi/ripgrep")
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["gh", "api"]),
        ):
            assert _get_latest_tag_via_gh(spec) is None


class TestGetLatestTag:
    def test_returns_version_when_not_latest(self):
        spec = ToolSpec(bin="rg", version="v14.0.0")
        client = MagicMock()
        assert get_latest_tag(spec, client) == "v14.0.0"
        client.get.assert_not_called()

    def test_fetches_tag_from_gh_when_available(self):
        spec = ToolSpec(bin="rg", repo="BurntSushi/ripgrep", version="latest")
        client = MagicMock()
        with patch("ptm.resolver._get_latest_tag_via_gh", return_value="14.1.0"):
            assert get_latest_tag(spec, client) == "14.1.0"
        client.get.assert_not_called()

    def test_falls_back_to_api_when_gh_is_unavailable(self):
        spec = ToolSpec(bin="rg", repo="BurntSushi/ripgrep", version="latest")
        client = MagicMock()
        client.get.return_value.json.return_value = {"tag_name": "14.1.0"}
        with patch("ptm.resolver._get_latest_tag_via_gh", return_value=None):
            assert get_latest_tag(spec, client) == "14.1.0"


class TestGetUrlReleaseVersion:
    def test_returns_version_when_no_version_url(self):
        spec = ToolSpec(bin="node", version="lts")
        client = MagicMock()
        assert get_url_release_version(spec, client) == "lts"
        client.get.assert_not_called()

    def test_fetches_version_from_url(self):
        spec = ToolSpec(
            bin="node",
            version_url="https://nodejs.org/dist/index.json",
            version_url_regex=r'"version":"(v[\d.]+)"',
        )
        client = MagicMock()
        client.get.return_value.text = '"version":"v22.0.0","lts":"iron"'
        assert get_url_release_version(spec, client) == "v22.0.0"

    def test_raises_when_version_not_found(self):
        spec = ToolSpec(
            bin="node",
            version_url="https://example.com",
            version_url_regex=r"no_match_(\S+)",
        )
        client = MagicMock()
        client.get.return_value.text = "no version here"
        with pytest.raises(RuntimeError, match="Version not found"):
            get_url_release_version(spec, client)


class TestGetNpmLatestVersion:
    def test_fetches_version_from_npm(self):
        spec = ToolSpec(bin="markdownlint-cli2", type="npm")
        with patch("subprocess.check_output", return_value="0.15.0\n") as mock_check:
            assert get_npm_latest_version(spec) == "0.15.0"
        mock_check.assert_called_once_with(
            ["npm", "view", "markdownlint-cli2", "version"],
            stderr=subprocess.STDOUT,
            text=True,
        )


class TestGetComparableLatestVersion:
    def test_returns_none_for_installer(self):
        spec = ToolSpec(bin="uv", type="installer", command="install.sh")
        client = MagicMock()
        assert get_comparable_latest_version(spec, client) is None

    def test_fetches_installer_version_when_version_url_is_set(self):
        spec = ToolSpec(
            bin="uv",
            type="installer",
            command="install.sh",
            version_url="https://example.com/uv.json",
        )
        client = MagicMock()
        with patch("ptm.resolver.get_url_release_version", return_value="0.9.1"):
            assert get_comparable_latest_version(spec, client) == "0.9.1"

    def test_returns_none_for_nightly(self):
        spec = ToolSpec(bin="nvim", version="nightly")
        client = MagicMock()
        assert get_comparable_latest_version(spec, client) is None

    def test_fetches_github_release_version(self):
        spec = ToolSpec(bin="rg", repo="BurntSushi/ripgrep", version="latest")
        client = MagicMock()
        with patch("ptm.resolver.get_latest_tag", return_value="v14.1.0"):
            assert get_comparable_latest_version(spec, client) == "14.1.0"

    def test_fetches_url_release_version(self):
        spec = ToolSpec(
            bin="node", type="url_release", version_url="https://nodejs.org"
        )
        client = MagicMock()
        with patch("ptm.resolver.get_url_release_version", return_value="v22.0.0"):
            assert get_comparable_latest_version(spec, client) == "22.0.0"

    def test_fetches_npm_version(self):
        spec = ToolSpec(bin="markdownlint-cli2", type="npm")
        client = MagicMock()
        with patch("ptm.resolver.get_npm_latest_version", return_value="0.15.0"):
            assert get_comparable_latest_version(spec, client) == "0.15.0"


class TestResolveAssetUrl:
    def test_replaces_tag_and_version(self):
        spec = ToolSpec(
            bin="rg",
            repo="BurntSushi/ripgrep",
            platforms={"linux-x86_64": "ripgrep-{version}-x86_64.tar.gz"},
        )
        client = MagicMock()
        with patch("ptm.resolver.detect_platform", return_value="linux-x86_64"):
            url = resolve_asset_url(spec, "14.1.0", client)
        assert (
            url
            == "https://github.com/BurntSushi/ripgrep/releases/download/14.1.0/ripgrep-14.1.0-x86_64.tar.gz"
        )

    def test_strips_v_prefix_for_version(self):
        spec = ToolSpec(
            bin="rg",
            repo="BurntSushi/ripgrep",
            platforms={"linux-x86_64": "ripgrep-{version}-x86_64.tar.gz"},
        )
        client = MagicMock()
        with patch("ptm.resolver.detect_platform", return_value="linux-x86_64"):
            url = resolve_asset_url(spec, "v14.1.0", client)
        assert "ripgrep-14.1.0-x86_64.tar.gz" in url

    def test_raises_for_unsupported_platform(self):
        spec = ToolSpec(
            bin="rg",
            repo="BurntSushi/ripgrep",
            platforms={"linux-x86_64": "rg.tar.gz"},
        )
        client = MagicMock()
        with (
            patch("ptm.resolver.detect_platform", return_value="windows-x86_64"),
            pytest.raises(RuntimeError, match="no asset for platform"),
        ):
            resolve_asset_url(spec, "14.1.0", client)


class TestResolveGithubReleaseAssetAutomatically:
    def test_picks_matching_asset_when_platforms_are_omitted(self):
        spec = ToolSpec(bin="rg", repo="BurntSushi/ripgrep", type="github_release")
        client = MagicMock()
        client.get.return_value.json.return_value = {
            "assets": [
                {
                    "name": "ripgrep-14.1.0-aarch64-apple-darwin.tar.gz",
                    "browser_download_url": "https://example.com/darwin.tar.gz",
                },
                {
                    "name": "ripgrep-14.1.0-x86_64-unknown-linux-musl.tar.gz",
                    "browser_download_url": "https://example.com/linux.tar.gz",
                },
            ]
        }

        with patch("ptm.resolver.detect_platform", return_value="linux-x86_64"):
            asset = resolve_github_release_asset(spec, "14.1.0", client)

        assert asset.name == "ripgrep-14.1.0-x86_64-unknown-linux-musl.tar.gz"
        assert asset.url == "https://example.com/linux.tar.gz"
        assert asset.extract == "tar_binary"

    def test_uses_release_tag_endpoint_for_non_latest_versions(self):
        spec = ToolSpec(bin="nvim", repo="neovim/neovim", version="nightly")
        client = MagicMock()
        client.get.return_value.json.return_value = {
            "assets": [
                {
                    "name": "nvim-macos-arm64.tar.gz",
                    "browser_download_url": "https://example.com/nvim-macos-arm64.tar.gz",
                }
            ]
        }

        with patch("ptm.resolver.detect_platform", return_value="darwin-arm64"):
            asset = resolve_github_release_asset(spec, "nightly", client)

        assert asset.name == "nvim-macos-arm64.tar.gz"
        client.get.assert_called_once()
        assert client.get.call_args.args[0].endswith("/releases/tags/nightly")

    def test_raises_when_no_assets_match_platform(self):
        spec = ToolSpec(bin="rg", repo="BurntSushi/ripgrep", type="github_release")
        client = MagicMock()
        client.get.return_value.json.return_value = {
            "assets": [
                {
                    "name": "ripgrep-14.1.0-aarch64-apple-darwin.tar.gz",
                    "browser_download_url": "https://example.com/darwin.tar.gz",
                }
            ]
        }

        with (
            patch("ptm.resolver.detect_platform", return_value="linux-x86_64"),
            pytest.raises(RuntimeError, match="no release asset matched platform"),
        ):
            resolve_github_release_asset(spec, "14.1.0", client)

    def test_raises_when_multiple_assets_tie(self):
        spec = ToolSpec(bin="tool", repo="owner/repo", type="github_release")
        client = MagicMock()
        client.get.return_value.json.return_value = {
            "assets": [
                {
                    "name": "tool-linux-amd64.tar.gz",
                    "browser_download_url": "https://example.com/tool-linux-amd64.tar.gz",
                },
                {
                    "name": "tool-linux-x86_64.tar.gz",
                    "browser_download_url": "https://example.com/tool-linux-x86_64.tar.gz",
                },
            ]
        }

        with (
            patch("ptm.resolver.detect_platform", return_value="linux-x86_64"),
            pytest.raises(
                RuntimeError,
                match="multiple release assets matched platform",
            ),
        ):
            resolve_github_release_asset(spec, "1.0.0", client)


class TestScoreAssetName:
    def test_ignores_checksum_assets(self):
        spec = ToolSpec(bin="rg", repo="BurntSushi/ripgrep", type="github_release")
        with patch("ptm.resolver.detect_platform", return_value="linux-x86_64"):
            asset_name = "ripgrep-14.1.0-linux-x86_64.tar.gz.sha256"
            assert _score_asset_name(spec, asset_name) is None

    def test_matches_macos_and_aarch64_aliases(self):
        spec = ToolSpec(bin="gh", repo="cli/cli", type="github_release")
        with patch("ptm.resolver.detect_platform", return_value="darwin-arm64"):
            score = _score_asset_name(spec, "gh_2.90.0_macOS_aarch64.zip")
        assert score is not None


class TestResolveUrlReleaseUrl:
    def test_replaces_version(self):
        spec = ToolSpec(
            bin="node",
            platforms={
                "linux-x86_64": "https://nodejs.org/dist/v{version}/node-v{version}-linux-x64.tar.xz"
            },
        )
        with patch("ptm.resolver.detect_platform", return_value="linux-x86_64"):
            url = resolve_url_release_url(spec, "v22.0.0")
        assert url == "https://nodejs.org/dist/v22.0.0/node-v22.0.0-linux-x64.tar.xz"

    def test_auto_resolves_node_dist_url_when_platforms_are_omitted(self):
        spec = ToolSpec(
            bin="node",
            type="url_release",
            version_url="https://nodejs.org/dist/index.json",
        )
        with patch("ptm.resolver.detect_platform", return_value="linux-x86_64"):
            url = resolve_url_release_url(spec, "v22.0.0")
        assert url == "https://nodejs.org/dist/v22.0.0/node-v22.0.0-linux-x64.tar.xz"

    def test_auto_resolves_node_dist_url_for_darwin_arm64(self):
        spec = ToolSpec(
            bin="node",
            type="url_release",
            version_url="https://nodejs.org/dist/index.json",
        )
        with patch("ptm.resolver.detect_platform", return_value="darwin-arm64"):
            url = resolve_url_release_url(spec, "v22.0.0")
        assert url == "https://nodejs.org/dist/v22.0.0/node-v22.0.0-darwin-arm64.tar.xz"

    def test_resolves_node_dist_asset_with_tar_extract(self):
        spec = ToolSpec(
            bin="node",
            type="url_release",
            version_url="https://nodejs.org/dist/index.json",
            opt_dir="~/.local/opt/node",
        )
        with patch("ptm.resolver.detect_platform", return_value="linux-x86_64"):
            asset = resolve_url_release_asset(spec, "v22.0.0")
        assert asset.name == "node-v22.0.0-linux-x64.tar.xz"
        assert asset.extract == "tar"

    def test_raises_for_unknown_url_release_without_platforms(self):
        spec = ToolSpec(
            bin="custom-tool",
            type="url_release",
            version_url="https://example.com/releases.json",
        )
        with pytest.raises(RuntimeError, match="no URL template for platform"):
            resolve_url_release_url(spec, "1.2.3")

    def test_raises_for_unsupported_node_platform(self):
        spec = ToolSpec(
            bin="node",
            type="url_release",
            version_url="https://nodejs.org/dist/index.json",
        )
        with (
            patch("ptm.resolver.detect_platform", return_value="windows-x86_64"),
            pytest.raises(RuntimeError, match=r"no Node\.js dist asset for platform"),
        ):
            resolve_url_release_url(spec, "v22.0.0")
