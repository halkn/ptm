import copy
import gzip
import shlex
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Iterator

import httpx

from ptm.config import BIN_DIR, console
from ptm.models import ToolSpec
from ptm.resolver import (
    get_latest_tag,
    get_installed_version,
    get_url_release_version,
    resolve_asset_url,
    resolve_url_release_url,
)


def _download(url: str, dest: Path, client: httpx.Client) -> None:
    with client.stream("GET", url) as resp:
        resp.raise_for_status()
        dest.write_bytes(resp.read())


def _strip_components(
    members: list[tarfile.TarInfo], n: int
) -> Iterator[tarfile.TarInfo]:
    for m in members:
        parts = Path(m.name).parts
        if len(parts) <= n:
            continue
        m2 = copy.copy(m)
        m2.name = str(Path(*parts[n:]))
        yield m2


def _extract_binary_from_tar(archive: Path, bin_name: str, dest: Path) -> None:
    with tarfile.open(archive, "r:*") as tf:
        for member in tf.getmembers():
            if Path(member.name).name == bin_name and member.isfile():
                member_copy = copy.copy(member)
                member_copy.name = bin_name
                tf.extract(member_copy, dest, filter="data")
                return
    raise FileNotFoundError(f"{bin_name} not found in {archive}")


def _install_tar(spec: ToolSpec, url: str, client: httpx.Client) -> None:
    opt_dir = Path(spec.opt_dir).expanduser()
    backup = opt_dir.with_name(opt_dir.name + ".bak")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "archive.tar"
        console.print(f"  Downloading {url}")
        _download(url, tmp_path, client)

        if opt_dir.exists():
            opt_dir.rename(backup)
        opt_dir.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(tmp_path, "r:*") as tf:
                members = list(
                    _strip_components(tf.getmembers(), spec.strip_components)
                )
                tf.extractall(opt_dir, members=members, filter="data")
        except Exception:
            if backup.exists():
                shutil.rmtree(opt_dir, ignore_errors=True)
                backup.rename(opt_dir)
            raise

        if backup.exists():
            shutil.rmtree(backup)

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    bin_link = BIN_DIR / spec.bin
    bin_link.unlink(missing_ok=True)
    bin_link.symlink_to(opt_dir / spec.bin_path_in_archive)

    bin_dir_in_archive = Path(spec.bin_path_in_archive).parent
    for extra in spec.extra_bins:
        link = BIN_DIR / extra
        link.unlink(missing_ok=True)
        link.symlink_to(opt_dir / bin_dir_in_archive / extra)


def _install_tar_binary(spec: ToolSpec, url: str, client: httpx.Client) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "archive.tar"
        console.print(f"  Downloading {url}")
        _download(url, tmp_path, client)

        BIN_DIR.mkdir(parents=True, exist_ok=True)
        _extract_binary_from_tar(tmp_path, spec.bin, BIN_DIR)

    dest = BIN_DIR / spec.bin
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _install_gz_binary(spec: ToolSpec, url: str, client: httpx.Client) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_gz = Path(tmpdir) / "archive.gz"
        console.print(f"  Downloading {url}")
        _download(url, tmp_gz, client)

        BIN_DIR.mkdir(parents=True, exist_ok=True)
        dest = BIN_DIR / spec.bin
        with gzip.open(tmp_gz, "rb") as gz_in:
            dest.write_bytes(gz_in.read())

    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _install_zip_binary(spec: ToolSpec, url: str, client: httpx.Client) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_zip = Path(tmpdir) / "archive.zip"
        console.print(f"  Downloading {url}")
        _download(url, tmp_zip, client)

        BIN_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(tmp_zip) as zf:
            for info in zf.infolist():
                if Path(info.filename).name == spec.bin and not info.is_dir():
                    data = zf.read(info.filename)
                    dest = BIN_DIR / spec.bin
                    dest.write_bytes(data)
                    dest.chmod(
                        dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
                    )
                    return
    raise FileNotFoundError(f"{spec.bin} not found in zip archive")


def _install_raw_binary(spec: ToolSpec, url: str, client: httpx.Client) -> None:
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    dest = BIN_DIR / spec.bin
    console.print(f"  Downloading {url}")
    _download(url, dest, client)
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _dispatch_extract(spec: ToolSpec, url: str, client: httpx.Client) -> None:
    match spec.extract:
        case "tar":
            _install_tar(spec, url, client)
        case "tar_binary" | "tar_xz_binary":
            _install_tar_binary(spec, url, client)
        case "gz_binary":
            _install_gz_binary(spec, url, client)
        case "zip_binary":
            _install_zip_binary(spec, url, client)
        case "raw_binary":
            _install_raw_binary(spec, url, client)
        case _:
            raise ValueError(f"Unknown extract type: {spec.extract}")


def _install_github_release(spec: ToolSpec, client: httpx.Client) -> None:
    tag = get_latest_tag(spec, client)
    url = resolve_asset_url(spec, tag)
    _dispatch_extract(spec, url, client)


def _install_url_release(spec: ToolSpec, client: httpx.Client) -> None:
    version = get_url_release_version(spec, client)
    url = resolve_url_release_url(spec, version)
    _dispatch_extract(spec, url, client)


def _run_installer(spec: ToolSpec, update: bool = False) -> None:
    cmd = spec.update_command if (update and spec.update_command) else spec.command
    if cmd:
        console.print(f"  Running: {cmd}")
        subprocess.run(cmd, shell=True, check=True)
    else:
        console.print(f"  Running installer from {spec.url}")
        subprocess.run(
            f"curl -fsSL {shlex.quote(spec.url)} | sh",
            shell=True,
            check=True,
        )


def do_install(spec: ToolSpec, client: httpx.Client, update: bool = False) -> None:
    label = "Updating" if update else "Installing"
    console.print(f"[bold cyan]{label} {spec.bin}[/bold cyan]")
    try:
        match spec.type:
            case "github_release":
                _install_github_release(spec, client)
            case "url_release":
                _install_url_release(spec, client)
            case "installer":
                _run_installer(spec, update=update)
            case _:
                raise ValueError(f"Unknown type: {spec.type}")
        console.print(f"  [green]Done.[/green] {get_installed_version(spec) or ''}")
    except Exception as e:
        console.print(f"  [red]Failed: {e}[/red]")
