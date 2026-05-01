from dataclasses import dataclass


@dataclass(frozen=True)
class PackageManager:
    executable: str


NPM_REGISTRY_PACKAGE_MANAGERS: dict[str, PackageManager] = {
    "npm": PackageManager(executable="npm"),
    "bun": PackageManager(executable="bun"),
}


def is_npm_registry_package_type(tool_type: str) -> bool:
    return tool_type in NPM_REGISTRY_PACKAGE_MANAGERS


def get_package_manager(tool_type: str) -> PackageManager:
    try:
        return NPM_REGISTRY_PACKAGE_MANAGERS[tool_type]
    except KeyError as e:
        raise ValueError(f"Unknown package manager type: {tool_type}") from e
