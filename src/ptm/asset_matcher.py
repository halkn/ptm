from ptm.models import ToolSpec

_OS_TOKENS: dict[str, tuple[str, ...]] = {
    "linux": ("linux",),
    "darwin": ("darwin", "macos", "osx", "apple-darwin"),
}
_ARCH_TOKENS: dict[str, tuple[str, ...]] = {
    "x86_64": ("x86_64", "amd64", "x64"),
    "arm64": ("arm64", "aarch64"),
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
_LIGHTWEIGHT_VARIANT_TOKENS = ("light", "lite", "minimal", "slim")


def score_asset_name(
    spec: ToolSpec, asset_name: str, platform_key: str
) -> int | None:
    os_name, arch = platform_key.split("-", maxsplit=1)
    normalized = asset_name.lower()
    if any(token in normalized for token in _EXCLUDED_ASSET_TOKENS):
        return None

    os_tokens = _OS_TOKENS.get(os_name, (os_name,))
    arch_tokens = _ARCH_TOKENS.get(arch, (arch,))
    if not any(token in normalized for token in os_tokens):
        return None

    all_arch_tokens = {
        token
        for known_arch, tokens in _ARCH_TOKENS.items()
        if known_arch != arch
        for token in tokens
    }
    has_matching_arch = any(token in normalized for token in arch_tokens)
    has_other_arch = any(token in normalized for token in all_arch_tokens)
    if has_other_arch or (not has_matching_arch and _has_arch_token(normalized)):
        return None

    score = 200
    if spec.bin.lower() in normalized:
        score += 20
    if has_matching_arch:
        score += 12
    if any(token in normalized for token in _LIGHTWEIGHT_VARIANT_TOKENS):
        score -= 6

    if os_name == "linux":
        if "musl" in normalized:
            score += 8
        elif "gnu" in normalized:
            score += 4

    if normalized.endswith(".tar.xz"):
        score += 5
    elif normalized.endswith(".tar.gz"):
        score += 4
    elif normalized.endswith(".zip"):
        score += 3
    elif normalized.endswith(".gz"):
        score += 2
    else:
        score += 1

    return score


def _has_arch_token(asset_name: str) -> bool:
    return any(
        token in asset_name
        for arch_tokens in _ARCH_TOKENS.values()
        for token in arch_tokens
    )
