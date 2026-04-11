import subprocess
from unittest.mock import MagicMock, patch

import pytest

from ptm.models import ToolSpec
from ptm.resolver import (
    _github_headers,
    detect_platform,
    get_installed_version,
    get_latest_tag,
    get_url_release_version,
    resolve_asset_url,
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


class TestGithubHeaders:
    def test_no_token(self):
        with patch.dict("os.environ", {}, clear=True):
            headers = _github_headers()
        assert "Authorization" not in headers
        assert headers["Accept"] == "application/vnd.github+json"

    def test_with_token(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": "mytoken"}):
            headers = _github_headers()
        assert headers["Authorization"] == "Bearer mytoken"


class TestGetLatestTag:
    def test_returns_version_when_not_latest(self):
        spec = ToolSpec(bin="rg", version="v14.0.0")
        client = MagicMock()
        assert get_latest_tag(spec, client) == "v14.0.0"
        client.get.assert_not_called()

    def test_fetches_tag_from_api(self):
        spec = ToolSpec(bin="rg", repo="BurntSushi/ripgrep", version="latest")
        client = MagicMock()
        client.get.return_value.json.return_value = {"tag_name": "14.1.0"}
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


class TestResolveAssetUrl:
    def test_replaces_tag_and_version(self):
        spec = ToolSpec(
            bin="rg",
            repo="BurntSushi/ripgrep",
            platforms={"linux-x86_64": "ripgrep-{version}-x86_64.tar.gz"},
        )
        with patch("ptm.resolver.detect_platform", return_value="linux-x86_64"):
            url = resolve_asset_url(spec, "14.1.0")
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
        with patch("ptm.resolver.detect_platform", return_value="linux-x86_64"):
            url = resolve_asset_url(spec, "v14.1.0")
        assert "ripgrep-14.1.0-x86_64.tar.gz" in url

    def test_raises_for_unsupported_platform(self):
        spec = ToolSpec(
            bin="rg",
            repo="BurntSushi/ripgrep",
            platforms={"linux-x86_64": "rg.tar.gz"},
        )
        with (
            patch("ptm.resolver.detect_platform", return_value="windows-x86_64"),
            pytest.raises(RuntimeError, match="no asset for platform"),
        ):
            resolve_asset_url(spec, "14.1.0")


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
