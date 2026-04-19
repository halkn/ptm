import platform
import re
import subprocess
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from ptm.models import ToolSpec


@dataclass(frozen=True)
class ResolvedAsset:
    name: str
    url: str
    extract: str


_OS_TOKENS: dict[str, tuple[str, ...]] = {
    "linux": ("linux",),
    "darwin": ("darwin", "macos", "osx", "apple-darwin"),
}
_ARCH_TOKENS: dict[str, tuple[str, ...]] = {
    "x86_64": ("x86_64", "amd64", "x64"),
    "arm64": ("arm64", "aarch64"),
}
_NODE_DIST_PLATFORM_ALIASES: dict[str, str] = {
    "linux-x86_64": "linux-x64",
    "linux-arm64": "linux-arm64",
    "darwin-x86_64": "darwin-x64",
    "darwin-arm64": "darwin-arm64",
}
_EXCLUDED_ASSET_TOKENS = (
    "checksums",
    "checksum",
    "sha256",
    "sha512",
    "provenance",
    "sbom",
    ".sig",
    ".asc",
)


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
    except (FileNotFoundError, OSError, subprocess.CalledProcessError):
        return None


def version_status(installed: str | None, latest: str) -> str:
    if installed is None:
        return "[red]not installed[/red]"
    if installed == latest or installed.removeprefix("v") == latest:
        return "[green]up-to-date[/green]"
    return "[yellow]outdated[/yellow]"


def get_npm_latest_version(spec: ToolSpec) -> str:
    out = subprocess.check_output(
        ["npm", "view", spec.package, "version"],
        stderr=subprocess.STDOUT,
        text=True,
    )
    return out.strip().removeprefix("v")


def get_comparable_latest_version(spec: ToolSpec, client: httpx.Client) -> str | None:
    if spec.version == "nightly":
        return None
    if spec.type == "installer":
        if not spec.version_url:
            return None
        return get_url_release_version(spec, client).removeprefix("v")
    if spec.type == "npm":
        return get_npm_latest_version(spec)
    if spec.type == "url_release":
        return get_url_release_version(spec, client).removeprefix("v")
    return get_latest_tag(spec, client).removeprefix("v")


def _get_latest_tag_via_gh(spec: ToolSpec) -> str | None:
    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{spec.repo}/releases/latest",
                "--jq",
                ".tag_name",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    tag = result.stdout.strip()
    return tag or None


def get_latest_tag(spec: ToolSpec, client: httpx.Client) -> str:
    if spec.version != "latest":
        return spec.version
    gh_tag = _get_latest_tag_via_gh(spec)
    if gh_tag is not None:
        return gh_tag
    url = f"https://api.github.com/repos/{spec.repo}/releases/latest"
    resp = client.get(url, headers={"Accept": "application/vnd.github+json"})
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


def resolve_github_release_asset(
    spec: ToolSpec, tag: str, client: httpx.Client
) -> ResolvedAsset:
    if spec.platforms:
        template = _get_platform_template(spec)
        version = tag.removeprefix("v")
        asset = template.replace("{tag}", tag).replace("{version}", version)
        return ResolvedAsset(
            name=asset,
            url=f"https://github.com/{spec.repo}/releases/download/{tag}/{asset}",
            extract=_infer_extract_type(asset, spec.opt_dir),
        )
    return _resolve_github_release_asset_automatically(spec, tag, client)


def _resolve_github_release_asset_automatically(
    spec: ToolSpec, tag: str, client: httpx.Client
) -> ResolvedAsset:
    release = _get_github_release(spec, tag, client)
    raw_assets = release.get("assets", [])
    if not isinstance(raw_assets, list):
        raise RuntimeError(f"{spec.bin}: invalid release assets payload")

    scored_assets: list[tuple[int, ResolvedAsset]] = []
    for raw_asset in raw_assets:
        if not isinstance(raw_asset, dict):
            continue
        asset = {str(key): value for key, value in raw_asset.items()}
        name = asset.get("name")
        download_url = asset.get("browser_download_url")
        if not isinstance(name, str) or not isinstance(download_url, str):
            continue
        score = _score_asset_name(spec, name)
        if score is None:
            continue
        scored_assets.append(
            (
                score,
                ResolvedAsset(
                    name=name,
                    url=download_url,
                    extract=_infer_extract_type(name, spec.opt_dir),
                ),
            )
        )

    if not scored_assets:
        platform_key = detect_platform()
        raise RuntimeError(
            f"{spec.bin}: no release asset matched platform '{platform_key}'; "
            "set [tools.<name>.platforms] to override asset selection"
        )

    scored_assets.sort(key=lambda item: (-item[0], item[1].name))
    best_score, best_asset = scored_assets[0]
    tied_assets = [asset.name for score, asset in scored_assets if score == best_score]
    if len(tied_assets) > 1:
        platform_key = detect_platform()
        candidates = ", ".join(tied_assets)
        raise RuntimeError(
            f"{spec.bin}: multiple release assets matched platform '{platform_key}': "
            f"{candidates}; set [tools.<name>.platforms] to choose explicitly"
        )
    return best_asset


def _get_github_release(
    spec: ToolSpec, tag: str, client: httpx.Client
) -> dict[str, object]:
    if spec.version == "latest":
        url = f"https://api.github.com/repos/{spec.repo}/releases/latest"
    else:
        quoted_tag = quote(tag, safe="")
        url = f"https://api.github.com/repos/{spec.repo}/releases/tags/{quoted_tag}"
    resp = client.get(url, headers={"Accept": "application/vnd.github+json"})
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"{spec.bin}: invalid release metadata response")
    return data


def _score_asset_name(spec: ToolSpec, asset_name: str) -> int | None:
    platform_key = detect_platform()
    os_name, arch = platform_key.split("-", maxsplit=1)
    normalized = asset_name.lower()
    if any(token in normalized for token in _EXCLUDED_ASSET_TOKENS):
        return None

    os_tokens = _OS_TOKENS.get(os_name, (os_name,))
    arch_tokens = _ARCH_TOKENS.get(arch, (arch,))
    if not any(token in normalized for token in os_tokens):
        return None
    if not any(token in normalized for token in arch_tokens):
        return None

    score = 200
    if spec.bin.lower() in normalized:
        score += 20

    if normalized.endswith((".tar.gz", ".tar.xz")):
        score += 4
    elif normalized.endswith(".zip"):
        score += 3
    elif normalized.endswith(".gz"):
        score += 2
    else:
        score += 1

    return score


def _infer_extract_type(asset_name: str, opt_dir: str) -> str:
    if asset_name.endswith((".tar.gz", ".tar.xz")):
        return "tar" if opt_dir else "tar_binary"
    if asset_name.endswith(".gz"):
        return "gz_binary"
    if asset_name.endswith(".zip"):
        return "zip_binary"
    return "raw_binary"


def resolve_asset_url(spec: ToolSpec, tag: str, client: httpx.Client) -> str:
    return resolve_github_release_asset(spec, tag, client).url


def resolve_url_release_asset(spec: ToolSpec, version: str) -> ResolvedAsset:
    if not spec.platforms:
        return _resolve_known_url_release_asset(spec, version)
    template = _get_platform_template(spec)
    normalized_version = version.removeprefix("v")
    url = template.replace("{version}", normalized_version).replace("{tag}", version)
    return ResolvedAsset(
        name=url.rsplit("/", maxsplit=1)[-1],
        url=url,
        extract=_infer_extract_type(url, spec.opt_dir),
    )


def resolve_url_release_url(spec: ToolSpec, version: str) -> str:
    return resolve_url_release_asset(spec, version).url


def _resolve_known_url_release_asset(spec: ToolSpec, version: str) -> ResolvedAsset:
    if _uses_node_dist_index(spec):
        return _resolve_node_dist_asset(version, spec.opt_dir)
    raise RuntimeError(
        f"{spec.bin}: no URL template for platform '{detect_platform()}'; "
        "set [tools.<name>.platforms] to configure explicit download URLs"
    )


def _uses_node_dist_index(spec: ToolSpec) -> bool:
    return (
        spec.bin == "node" and spec.version_url == "https://nodejs.org/dist/index.json"
    )


def _resolve_node_dist_asset(version: str, opt_dir: str) -> ResolvedAsset:
    platform_key = detect_platform()
    platform_alias = _NODE_DIST_PLATFORM_ALIASES.get(platform_key)
    if platform_alias is None:
        raise RuntimeError(
            f"node: no Node.js dist asset for platform '{platform_key}'; "
            "set [tools.<name>.platforms] to configure explicit download URLs"
        )
    normalized_version = version.removeprefix("v")
    version_tag = f"v{normalized_version}"
    filename = f"node-{version_tag}-{platform_alias}.tar.xz"
    url = f"https://nodejs.org/dist/{version_tag}/{filename}"
    return ResolvedAsset(
        name=filename,
        url=url,
        extract=_infer_extract_type(filename, opt_dir),
    )
