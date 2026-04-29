import gzip
import io
import stat
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ptm.installer import (
    _dispatch_extract,
    _extract_binary_from_tar,
    _install_gz_binary,
    _install_raw_binary,
    _install_release_plan,
    _install_tar,
    _install_tar_binary,
    _install_zip_binary,
    _run_installer,
    _run_package_manager_install,
    _strip_components,
    do_install,
)
from ptm.models import InstallPlan, ToolSpec
from ptm.package_managers import NPM_REGISTRY_PACKAGE_MANAGERS

# ---- helpers ----------------------------------------------------------------


def _make_client_that_writes(
    content: bytes,
) -> tuple[MagicMock, Callable[[str, Path, MagicMock], None]]:
    """_download が呼ばれると dest にコンテンツを書き込む client を返す。"""

    def fake_download(url: str, dest: Path, client: MagicMock) -> None:
        dest.write_bytes(content)

    client = MagicMock()
    return client, fake_download


def _make_tar_gz(tmp_path: Path, bin_name: str, content: bytes = b"binary") -> Path:
    archive = tmp_path / "archive.tar.gz"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name=f"pkg/{bin_name}")
        info.size = len(content)
        tf.addfile(info, io.BytesIO(content))
    archive.write_bytes(buf.getvalue())
    return archive


def _make_zip(tmp_path: Path, bin_name: str, content: bytes = b"binary") -> Path:
    archive = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(f"pkg/{bin_name}", content)
    return archive


def _make_gz(tmp_path: Path, content: bytes = b"binary") -> Path:
    archive = tmp_path / "archive.gz"
    with gzip.open(archive, "wb") as f:
        f.write(content)
    return archive


def _is_executable(path: Path) -> bool:
    return bool(path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


# ---- _strip_components ------------------------------------------------------


class TestStripComponents:
    def test_strips_n_leading_path_components(self):
        info = tarfile.TarInfo(name="a/b/c")
        result = list(_strip_components([info], 1))
        assert result[0].name == "b/c"

    def test_strips_two_components(self):
        info = tarfile.TarInfo(name="a/b/c")
        result = list(_strip_components([info], 2))
        assert result[0].name == "c"

    def test_skips_entries_shorter_than_n(self):
        info = tarfile.TarInfo(name="a/b")
        result = list(_strip_components([info], 2))
        assert result == []


# ---- _extract_binary_from_tar -----------------------------------------------


class TestExtractBinaryFromTar:
    def test_extracts_binary(self, tmp_path: Path):
        archive = _make_tar_gz(tmp_path, "rg", b"rg-binary")
        _extract_binary_from_tar(archive, "rg", tmp_path)
        assert (tmp_path / "rg").read_bytes() == b"rg-binary"

    def test_raises_when_binary_not_found(self, tmp_path: Path):
        archive = _make_tar_gz(tmp_path, "rg")
        with pytest.raises(FileNotFoundError, match="fd not found"):
            _extract_binary_from_tar(archive, "fd", tmp_path)


# ---- _install_raw_binary ----------------------------------------------------


class TestInstallRawBinary:
    def test_writes_file_and_sets_executable(self, tmp_path: Path):
        spec = ToolSpec(bin="shfmt", platforms={"linux-x86_64": "shfmt"})
        client = MagicMock()

        def _write_bin(url: str, dest: Path, c: MagicMock) -> None:
            dest.write_bytes(b"bin")

        with (
            patch("ptm.installer.BIN_DIR", tmp_path),
            patch("ptm.installer._download", side_effect=_write_bin),
        ):
            _install_raw_binary(spec, "https://example.com/shfmt", client)

        dest = tmp_path / "shfmt"
        assert dest.exists()
        assert _is_executable(dest)


# ---- _install_gz_binary -----------------------------------------------------


class TestInstallGzBinary:
    def test_decompresses_and_sets_executable(self, tmp_path: Path):
        spec = ToolSpec(bin="tree-sitter", platforms={"linux-x86_64": "tree-sitter.gz"})
        gz_path = _make_gz(tmp_path, b"ts-binary")
        client = MagicMock()

        with (
            patch("ptm.installer.BIN_DIR", tmp_path),
            patch(
                "ptm.installer._download",
                side_effect=lambda url, dest, c: dest.write_bytes(gz_path.read_bytes()),
            ),
        ):
            _install_gz_binary(spec, "https://example.com/tree-sitter.gz", client)

        dest = tmp_path / "tree-sitter"
        assert dest.read_bytes() == b"ts-binary"
        assert _is_executable(dest)


# ---- _install_tar_binary ----------------------------------------------------


class TestInstallTarBinary:
    def test_extracts_binary_and_sets_executable(self, tmp_path: Path):
        spec = ToolSpec(bin="rg", platforms={"linux-x86_64": "rg.tar.gz"})
        archive = _make_tar_gz(tmp_path, "rg", b"rg-binary")
        client = MagicMock()

        with (
            patch("ptm.installer.BIN_DIR", tmp_path),
            patch(
                "ptm.installer._download",
                side_effect=lambda url, dest, c: dest.write_bytes(archive.read_bytes()),
            ),
        ):
            _install_tar_binary(spec, "https://example.com/rg.tar.gz", client)

        dest = tmp_path / "rg"
        assert dest.read_bytes() == b"rg-binary"
        assert _is_executable(dest)


# ---- _install_zip_binary ----------------------------------------------------


class TestInstallZipBinary:
    def test_extracts_binary_and_sets_executable(self, tmp_path: Path):
        spec = ToolSpec(bin="gh", platforms={"linux-x86_64": "gh.zip"})
        archive = _make_zip(tmp_path, "gh", b"gh-binary")
        client = MagicMock()

        with (
            patch("ptm.installer.BIN_DIR", tmp_path),
            patch(
                "ptm.installer._download",
                side_effect=lambda url, dest, c: dest.write_bytes(archive.read_bytes()),
            ),
        ):
            _install_zip_binary(spec, "https://example.com/gh.zip", client)

        dest = tmp_path / "gh"
        assert dest.read_bytes() == b"gh-binary"
        assert _is_executable(dest)

    def test_raises_when_binary_not_in_zip(self, tmp_path: Path):
        spec = ToolSpec(bin="gh", platforms={"linux-x86_64": "gh.zip"})
        archive = _make_zip(tmp_path, "other-bin")
        client = MagicMock()

        with (
            patch("ptm.installer.BIN_DIR", tmp_path),
            patch(
                "ptm.installer._download",
                side_effect=lambda url, dest, c: dest.write_bytes(archive.read_bytes()),
            ),
            pytest.raises(FileNotFoundError, match="gh not found"),
        ):
            _install_zip_binary(spec, "https://example.com/gh.zip", client)


# ---- _install_tar (full directory extract) ----------------------------------


class TestInstallTar:
    def _make_dir_tar_gz(self, tmp_path: Path) -> Path:
        archive = tmp_path / "nvim.tar.gz"
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            # strip_components=1 を想定した構造: pkg/bin/nvim
            for name, content in [
                ("pkg/bin/nvim", b"nvim-binary"),
                ("pkg/share/nvim/runtime/init.vim", b""),
            ]:
                info = tarfile.TarInfo(name=name)
                info.size = len(content)
                tf.addfile(info, io.BytesIO(content))
        archive.write_bytes(buf.getvalue())
        return archive

    def test_extracts_to_opt_dir_and_creates_symlink(self, tmp_path: Path):
        opt_dir = tmp_path / "opt" / "neovim"
        bin_dir = tmp_path / "bin"
        spec = ToolSpec(
            bin="nvim",
            platforms={"linux-x86_64": "nvim.tar.gz"},
            opt_dir=str(opt_dir),
            bin_path_in_archive="bin/nvim",
            strip_components=1,
        )
        archive = self._make_dir_tar_gz(tmp_path)
        client = MagicMock()

        with (
            patch("ptm.installer.BIN_DIR", bin_dir),
            patch(
                "ptm.installer._download",
                side_effect=lambda url, dest, c: dest.write_bytes(archive.read_bytes()),
            ),
        ):
            _install_tar(spec, "https://example.com/nvim.tar.gz", client)

        symlink = bin_dir / "nvim"
        assert symlink.is_symlink()
        assert symlink.resolve() == (opt_dir / "bin" / "nvim").resolve()

    def test_restores_backup_on_failure(self, tmp_path: Path):
        opt_dir = tmp_path / "opt" / "neovim"
        opt_dir.mkdir(parents=True)
        (opt_dir / "old_file").write_text("original")
        bin_dir = tmp_path / "bin"
        spec = ToolSpec(
            bin="nvim",
            platforms={"linux-x86_64": "nvim.tar.gz"},
            opt_dir=str(opt_dir),
            bin_path_in_archive="bin/nvim",
        )
        client = MagicMock()

        def _write_invalid(url: str, dest: Path, c: MagicMock) -> None:
            dest.write_bytes(b"not a tar")

        with (
            patch("ptm.installer.BIN_DIR", bin_dir),
            patch("ptm.installer._download", side_effect=_write_invalid),
            pytest.raises(tarfile.TarError),
        ):
            _install_tar(spec, "https://example.com/nvim.tar.gz", client)

        assert opt_dir.exists()
        assert (opt_dir / "old_file").read_text() == "original"


# ---- _run_installer ---------------------------------------------------------


class TestRunInstaller:
    def test_runs_command_when_set(self):
        spec = ToolSpec(bin="uv", command="curl ... | sh")
        with patch("subprocess.run") as mock_run:
            _run_installer(spec)
        mock_run.assert_called_once_with("curl ... | sh", shell=True, check=True)

    def test_runs_update_command_when_updating(self):
        spec = ToolSpec(bin="uv", command="install.sh", update_command="uv self update")
        with patch("subprocess.run") as mock_run:
            _run_installer(spec, update=True)
        mock_run.assert_called_once_with("uv self update", shell=True, check=True)

    def test_falls_back_to_command_when_no_update_command(self):
        spec = ToolSpec(bin="uv", command="install.sh")
        with patch("subprocess.run") as mock_run:
            _run_installer(spec, update=True)
        mock_run.assert_called_once_with("install.sh", shell=True, check=True)

    def test_uses_url_when_no_command(self):
        spec = ToolSpec(bin="uv", url="https://astral.sh/uv/install.sh")
        with patch("subprocess.run") as mock_run:
            _run_installer(spec)
        args = mock_run.call_args[0][0]
        assert "https://astral.sh/uv/install.sh" in args


class TestRunPackageManagerInstall:
    @pytest.mark.parametrize("manager", NPM_REGISTRY_PACKAGE_MANAGERS)
    def test_runs_install(self, manager: str):
        spec = ToolSpec(bin="markdownlint-cli2", type=manager)
        with patch("subprocess.run") as mock_run:
            _run_package_manager_install(spec, manager)
        mock_run.assert_called_once_with(
            [
                manager,
                NPM_REGISTRY_PACKAGE_MANAGERS[manager].install_command,
                "-g",
                "markdownlint-cli2",
            ],
            check=True,
        )

    @pytest.mark.parametrize("manager", NPM_REGISTRY_PACKAGE_MANAGERS)
    def test_runs_update_when_updating(self, manager: str):
        spec = ToolSpec(bin="markdownlint-cli2", type=manager)
        with patch("subprocess.run") as mock_run:
            _run_package_manager_install(spec, manager, update=True)
        mock_run.assert_called_once_with(
            [
                manager,
                NPM_REGISTRY_PACKAGE_MANAGERS[manager].update_command,
                "-g",
                "markdownlint-cli2",
            ],
            check=True,
        )

    @pytest.mark.parametrize("manager", NPM_REGISTRY_PACKAGE_MANAGERS)
    def test_uses_package_name_when_set(self, manager: str):
        spec = ToolSpec(bin="tsc", type=manager, package="typescript")
        with patch("subprocess.run") as mock_run:
            _run_package_manager_install(spec, manager)
        mock_run.assert_called_once_with(
            [
                manager,
                NPM_REGISTRY_PACKAGE_MANAGERS[manager].install_command,
                "-g",
                "typescript",
            ],
            check=True,
        )


# ---- _dispatch_extract ------------------------------------------------------


class TestDispatchExtract:
    @pytest.mark.parametrize(
        "extract, expected_fn",
        [
            ("tar", "_install_tar"),
            ("tar_binary", "_install_tar_binary"),
            ("tar_xz_binary", "_install_tar_binary"),
            ("gz_binary", "_install_gz_binary"),
            ("zip_binary", "_install_zip_binary"),
            ("raw_binary", "_install_raw_binary"),
        ],
    )
    def test_dispatches_to_correct_function(self, extract: str, expected_fn: str):
        spec = ToolSpec(bin="tool", extract=extract)
        client = MagicMock()
        with patch(f"ptm.installer.{expected_fn}") as mock_fn:
            _dispatch_extract(spec, "https://example.com/tool", client)
        mock_fn.assert_called_once()

    def test_raises_on_unknown_extract_type(self):
        spec = ToolSpec(bin="tool", extract="unknown")
        with pytest.raises(ValueError, match="Unknown extract type"):
            _dispatch_extract(spec, "https://example.com", MagicMock())

    def test_override_extract_takes_precedence(self):
        spec = ToolSpec(bin="tool", extract="raw_binary")
        client = MagicMock()
        with patch("ptm.installer._install_zip_binary") as mock_fn:
            _dispatch_extract(
                spec,
                "https://example.com/tool.zip",
                client,
                extract="zip_binary",
            )
        mock_fn.assert_called_once()


# ---- do_install -------------------------------------------------------------


class TestDoInstall:
    def test_installs_github_release(self):
        spec = ToolSpec(bin="rg", type="github_release", repo="BurntSushi/ripgrep")
        client = MagicMock()
        plan = InstallPlan(
            spec=spec,
            version="v14.1.0",
            url="https://example.com/rg.tar.gz",
            extract="tar_binary",
        )
        with (
            patch("ptm.installer.resolve_install_plan", return_value=plan) as mock_plan,
            patch("ptm.installer._install_release_plan") as mock_install,
            patch("ptm.installer.get_installed_version", return_value="14.1.0"),
        ):
            do_install(spec, client)
        mock_plan.assert_called_once_with(spec, client)
        mock_install.assert_called_once_with(plan, client)

    def test_installs_url_release(self):
        spec = ToolSpec(bin="node", type="url_release")
        client = MagicMock()
        plan = InstallPlan(
            spec=spec,
            version="v22.0.0",
            url="https://example.com/node.tar.xz",
            extract="tar_binary",
        )
        with (
            patch("ptm.installer.resolve_install_plan", return_value=plan) as mock_plan,
            patch("ptm.installer._install_release_plan") as mock_install,
            patch("ptm.installer.get_installed_version", return_value="22.0.0"),
        ):
            do_install(spec, client)
        mock_plan.assert_called_once_with(spec, client)
        mock_install.assert_called_once_with(plan, client)

    def test_uses_provided_release_plan(self):
        spec = ToolSpec(bin="rg", type="github_release", repo="BurntSushi/ripgrep")
        client = MagicMock()
        plan = InstallPlan(
            spec=spec,
            version="v14.1.0",
            url="https://example.com/rg.tar.gz",
            extract="tar_binary",
        )
        with (
            patch("ptm.installer.resolve_install_plan") as mock_plan,
            patch("ptm.installer._install_release_plan") as mock_install,
            patch("ptm.installer.get_installed_version", return_value="14.1.0"),
        ):
            do_install(spec, client, plan=plan)
        mock_plan.assert_not_called()
        mock_install.assert_called_once_with(plan, client)

    def test_runs_installer(self):
        spec = ToolSpec(bin="uv", type="installer", command="install.sh")
        client = MagicMock()
        with (
            patch("ptm.installer._run_installer") as mock_run,
            patch("ptm.installer.get_installed_version", return_value="0.5.0"),
        ):
            do_install(spec, client)
        mock_run.assert_called_once_with(spec, update=False)

    def test_passes_update_flag(self):
        spec = ToolSpec(bin="uv", type="installer", command="install.sh")
        client = MagicMock()
        with (
            patch("ptm.installer._run_installer") as mock_run,
            patch("ptm.installer.get_installed_version", return_value="0.5.0"),
        ):
            do_install(spec, client, update=True)
        mock_run.assert_called_once_with(spec, update=True)

    @pytest.mark.parametrize("tool_type", NPM_REGISTRY_PACKAGE_MANAGERS)
    def test_runs_package_manager_installer(self, tool_type: str):
        spec = ToolSpec(bin="markdownlint-cli2", type=tool_type)
        client = MagicMock()
        with (
            patch("ptm.installer._run_package_manager_install") as mock_run,
            patch("ptm.installer.get_installed_version", return_value="0.15.0"),
        ):
            do_install(spec, client)
        mock_run.assert_called_once_with(spec, tool_type, update=False)

    def test_prints_error_on_failure(self, capsys: pytest.CaptureFixture):
        spec = ToolSpec(bin="rg", type="github_release")
        client = MagicMock()
        with (
            patch(
                "ptm.installer.resolve_install_plan",
                return_value=InstallPlan(spec=spec, url="https://example.com/rg"),
            ),
            patch(
                "ptm.installer._install_release_plan",
                side_effect=RuntimeError("network error"),
            ),
        ):
            do_install(spec, client)  # 例外が外に漏れないこと


class TestInstallReleasePlan:
    def test_dispatches_extract_from_plan(self):
        spec = ToolSpec(bin="rg", type="github_release", repo="BurntSushi/ripgrep")
        plan = InstallPlan(
            spec=spec,
            version="v14.1.0",
            url="https://example.com/rg.tar.gz",
            extract="tar_binary",
        )
        client = MagicMock()
        with patch("ptm.installer._dispatch_extract") as mock_dispatch:
            _install_release_plan(plan, client)
        mock_dispatch.assert_called_once_with(
            spec, "https://example.com/rg.tar.gz", client, extract="tar_binary"
        )
