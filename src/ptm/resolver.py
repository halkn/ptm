import os
import platform
import re
import subprocess

import httpx

from ptm.models import ToolSpec


def detect_platform() -> str:
    os_name = platform.system().lower()
    machine = platform.machine().lower()
    if machine == "aarch64":
        machine = "arm64"
    return f"{os_name}-{machine}"


def get_installed_version(spec: ToolSpec) -> str | None:
    try:
        out = subprocess.check_output(
            spec.version_cmd, stderr=subprocess.STDOUT, text=True
        )
        m = re.search(spec.version_regex, out)
        return m.group(1) if m else "unknown"
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def version_status(installed: str | None, latest: str) -> str:
    if installed is None:
        return "[red]not installed[/red]"
    if installed == latest or installed.removeprefix("v") == latest:
        return "[green]up-to-date[/green]"
    return "[yellow]outdated[/yellow]"


def _github_headers() -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def get_latest_tag(spec: ToolSpec, client: httpx.Client) -> str:
    if spec.version != "latest":
        return spec.version
    url = f"https://api.github.com/repos/{spec.repo}/releases/latest"
    resp = client.get(url, headers=_github_headers())
    resp.raise_for_status()
    return resp.json()["tag_name"]


def get_url_release_version(spec: ToolSpec, client: httpx.Client) -> str:
    if not spec.version_url:
        return spec.version
    resp = client.get(spec.version_url)
    resp.raise_for_status()
    pattern = spec.version_url_regex or spec.version_regex
    m = re.search(pattern, resp.text, re.DOTALL)
    if not m:
        raise RuntimeError(f"Version not found in {spec.version_url}")
    return m.group(1)


def _get_platform_template(spec: ToolSpec) -> str:
    plat = detect_platform()
    template = spec.platforms.get(plat)
    if template is None:
        raise RuntimeError(f"{spec.bin}: no asset for platform '{plat}'")
    return template


def resolve_asset_url(spec: ToolSpec, tag: str) -> str:
    template = _get_platform_template(spec)
    version = tag.removeprefix("v")
    asset = template.replace("{tag}", tag).replace("{version}", version)
    return f"https://github.com/{spec.repo}/releases/download/{tag}/{asset}"


def resolve_url_release_url(spec: ToolSpec, version: str) -> str:
    template = _get_platform_template(spec)
    v = version.removeprefix("v")
    return template.replace("{version}", v).replace("{tag}", version)
