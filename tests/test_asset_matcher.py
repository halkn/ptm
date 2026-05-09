from ptm.asset_matcher import score_asset_name
from ptm.models import ToolSpec


class TestScoreAssetName:
    def test_ignores_checksum_assets(self):
        spec = ToolSpec(bin="rg", repo="BurntSushi/ripgrep", type="github_release")
        asset_name = "ripgrep-14.1.0-linux-x86_64.tar.gz.sha256"

        assert score_asset_name(spec, asset_name, "linux-x86_64") is None

    def test_matches_macos_and_aarch64_aliases(self):
        spec = ToolSpec(bin="gh", repo="cli/cli", type="github_release")

        score = score_asset_name(spec, "gh_2.90.0_macOS_aarch64.zip", "darwin-arm64")

        assert score is not None
