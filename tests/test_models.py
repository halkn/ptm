from ptm.models import ToolSpec


class TestToolSpecVersionCmd:
    def test_default_version_cmd(self):
        spec = ToolSpec(bin="rg")
        assert spec.version_cmd == ["rg", "--version"]

    def test_custom_version_cmd(self):
        spec = ToolSpec(bin="rg", version_cmd=["rg", "-V"])
        assert spec.version_cmd == ["rg", "-V"]


class TestToolSpecInferExtract:
    def test_no_platforms_returns_raw_binary(self):
        spec = ToolSpec(bin="tool")
        assert spec.extract == "raw_binary"

    def test_tar_gz_without_opt_dir_returns_tar_binary(self):
        spec = ToolSpec(bin="rg", platforms={"linux-x86_64": "rg.tar.gz"})
        assert spec.extract == "tar_binary"

    def test_tar_gz_with_opt_dir_returns_tar(self):
        spec = ToolSpec(
            bin="nvim",
            platforms={"linux-x86_64": "nvim.tar.gz"},
            opt_dir="~/.local/opt/neovim",
        )
        assert spec.extract == "tar"

    def test_tar_xz_returns_tar_binary(self):
        spec = ToolSpec(bin="tool", platforms={"linux-x86_64": "tool.tar.xz"})
        assert spec.extract == "tar_binary"

    def test_gz_returns_gz_binary(self):
        spec = ToolSpec(bin="tree-sitter", platforms={"linux-x86_64": "tree-sitter.gz"})
        assert spec.extract == "gz_binary"

    def test_zip_returns_zip_binary(self):
        spec = ToolSpec(bin="gh", platforms={"linux-x86_64": "gh.zip"})
        assert spec.extract == "zip_binary"

    def test_no_extension_returns_raw_binary(self):
        spec = ToolSpec(
            bin="shfmt", platforms={"linux-x86_64": "shfmt_v3.8.0_linux_amd64"}
        )
        assert spec.extract == "raw_binary"

    def test_explicit_extract_is_not_overridden(self):
        spec = ToolSpec(
            bin="tool",
            platforms={"linux-x86_64": "tool.tar.gz"},
            extract="raw_binary",
        )
        assert spec.extract == "raw_binary"


class TestToolSpecFromDict:
    def test_basic_fields(self):
        spec = ToolSpec.from_dict({"bin": "rg", "repo": "BurntSushi/ripgrep"})
        assert spec.bin == "rg"
        assert spec.repo == "BurntSushi/ripgrep"

    def test_unknown_keys_are_ignored(self):
        spec = ToolSpec.from_dict({"bin": "rg", "unknown_key": "value"})
        assert spec.bin == "rg"

    def test_type_field_is_set(self):
        spec = ToolSpec.from_dict({"bin": "rg", "type": "github_release"})
        assert spec.type == "github_release"
