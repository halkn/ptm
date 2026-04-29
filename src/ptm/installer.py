import copy
import gzip
import shlex
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

import httpx

from ptm.config import BIN_DIR
from ptm.console import console
from ptm.models import InstallPlan, ToolSpec
from ptm.package_managers import get_package_manager, is_npm_registry_package_type
from ptm.resolver import get_installed_version, resolve_install_plan
from ptm.store import PTM_TOOLS_DIR, get_current_dir, get_tool_dir, write_tool_metadata


def _make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _prepare_managed_staging_dir(spec: ToolSpec) -> Path:
    staging_dir = get_tool_dir(spec.bin, PTM_TOOLS_DIR) / "next"
    if staging_dir.exists() or staging_dir.is_symlink():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    return staging_dir


def _activate_managed_current_dir(spec: ToolSpec, staging_dir: Path) -> Path:
    tool_dir = get_tool_dir(spec.bin, PTM_TOOLS_DIR)
    current_dir = tool_dir / "current"
    backup_dir = tool_dir / "previous"

    if backup_dir.exists() or backup_dir.is_symlink():
        shutil.rmtree(backup_dir)
    if current_dir.exists() or current_dir.is_symlink():
        current_dir.rename(backup_dir)

    try:
        staging_dir.rename(current_dir)
    except Exception:
        if backup_dir.exists():
            backup_dir.rename(current_dir)
        raise

    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    return current_dir


def _publish_release_links(spec: ToolSpec, current_dir: Path) -> list[Path]:
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    bin_path = Path(spec.bin_path_in_archive or spec.bin)
    bin_dir_in_archive = bin_path.parent
    link_targets = [(BIN_DIR / spec.bin, current_dir / bin_path)]
    link_targets.extend(
        (BIN_DIR / extra, current_dir / bin_dir_in_archive / extra)
        for extra in spec.extra_bins
    )

    for _link, target in link_targets:
        if not target.exists():
            raise FileNotFoundError(f"{target} not found")

    for link, _target in link_targets:
        link.unlink(missing_ok=True)

    for link, target in link_targets:
        link.symlink_to(target)
    return [link for link, _target in link_targets]


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
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "archive.tar"
        console.print(f"  Downloading {url}")
        _download(url, tmp_path, client)

        dest_dir = _prepare_managed_staging_dir(spec)

        try:
            with tarfile.open(tmp_path, "r:*") as tf:
                members = list(
                    _strip_components(tf.getmembers(), spec.strip_components)
                )
                tf.extractall(dest_dir, members=members, filter="data")
            _activate_managed_current_dir(spec, dest_dir)
        except Exception:
            shutil.rmtree(dest_dir, ignore_errors=True)
            raise


def _install_tar_binary(spec: ToolSpec, url: str, client: httpx.Client) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "archive.tar"
        console.print(f"  Downloading {url}")
        _download(url, tmp_path, client)

        staging_dir = _prepare_managed_staging_dir(spec)
        try:
            _extract_binary_from_tar(tmp_path, spec.bin, staging_dir)
            dest = staging_dir / spec.bin
            _make_executable(dest)
            _activate_managed_current_dir(spec, staging_dir)
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise


def _install_gz_binary(spec: ToolSpec, url: str, client: httpx.Client) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_gz = Path(tmpdir) / "archive.gz"
        console.print(f"  Downloading {url}")
        _download(url, tmp_gz, client)

        staging_dir = _prepare_managed_staging_dir(spec)
        try:
            dest = staging_dir / spec.bin
            with gzip.open(tmp_gz, "rb") as gz_in:
                dest.write_bytes(gz_in.read())
            _make_executable(dest)
            _activate_managed_current_dir(spec, staging_dir)
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise


def _install_zip_binary(spec: ToolSpec, url: str, client: httpx.Client) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_zip = Path(tmpdir) / "archive.zip"
        console.print(f"  Downloading {url}")
        _download(url, tmp_zip, client)

        staging_dir = _prepare_managed_staging_dir(spec)
        try:
            with zipfile.ZipFile(tmp_zip) as zf:
                for info in zf.infolist():
                    if Path(info.filename).name == spec.bin and not info.is_dir():
                        data = zf.read(info.filename)
                        dest = staging_dir / spec.bin
                        dest.write_bytes(data)
                        _make_executable(dest)
                        _activate_managed_current_dir(spec, staging_dir)
                        return
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise
        shutil.rmtree(staging_dir, ignore_errors=True)
    raise FileNotFoundError(f"{spec.bin} not found in zip archive")


def _install_raw_binary(spec: ToolSpec, url: str, client: httpx.Client) -> None:
    staging_dir = _prepare_managed_staging_dir(spec)
    dest = staging_dir / spec.bin
    console.print(f"  Downloading {url}")
    try:
        _download(url, dest, client)
        _make_executable(dest)
        _activate_managed_current_dir(spec, staging_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def _dispatch_extract(
    spec: ToolSpec, url: str, client: httpx.Client, extract: str | None = None
) -> None:
    resolved_extract = extract or spec.extract
    match resolved_extract:
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
            raise ValueError(f"Unknown extract type: {resolved_extract}")


def _install_release_plan(plan: InstallPlan, client: httpx.Client) -> None:
    if plan.url is None:
        raise ValueError(f"{plan.spec.bin}: install URL is not resolved")
    _dispatch_extract(plan.spec, plan.url, client, extract=plan.extract)
    current_dir = get_current_dir(plan.spec.bin, PTM_TOOLS_DIR)
    links = _publish_release_links(plan.spec, current_dir)
    tool_dir = get_tool_dir(plan.spec.bin, PTM_TOOLS_DIR)
    write_tool_metadata(plan.spec, tool_dir, links)


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


def _run_package_manager_install(
    spec: ToolSpec, manager: str, update: bool = False
) -> None:
    package_manager = get_package_manager(manager)
    action = (
        package_manager.update_command if update else package_manager.install_command
    )
    cmd = [manager, action, "-g", spec.package]
    console.print(f"  Running: {shlex.join(cmd)}")
    subprocess.run(cmd, check=True)


def do_install(
    spec: ToolSpec,
    client: httpx.Client,
    update: bool = False,
    plan: InstallPlan | None = None,
) -> bool:
    """Install or update a tool. Returns True on success, False on failure."""
    label = "Updating" if update else "Installing"
    console.print(f"[bold cyan]{label} {spec.bin}[/bold cyan]")
    try:
        match spec.type:
            case "github_release" | "url_release":
                resolved_plan = plan or resolve_install_plan(spec, client)
                _install_release_plan(resolved_plan, client)
            case "installer":
                _run_installer(spec, update=update)
            case _ if is_npm_registry_package_type(spec.type):
                _run_package_manager_install(spec, spec.type, update=update)
            case _:
                raise ValueError(f"Unknown type: {spec.type}")
        console.print(f"  [green]Done.[/green] {get_installed_version(spec) or ''}")
        return True
    except Exception as e:
        console.print(f"  [red]Failed: {e}[/red]")
        return False
