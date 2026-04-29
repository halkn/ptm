from dataclasses import dataclass


@dataclass(frozen=True)
class PackageManager:
    install_command: str
    update_command: str


NPM_REGISTRY_PACKAGE_MANAGERS: dict[str, PackageManager] = {
    "npm": PackageManager(install_command="install", update_command="update"),
    "bun": PackageManager(install_command="install", update_command="update"),
}


def is_npm_registry_package_type(tool_type: str) -> bool:
    return tool_type in NPM_REGISTRY_PACKAGE_MANAGERS


def get_package_manager(tool_type: str) -> PackageManager:
    try:
        return NPM_REGISTRY_PACKAGE_MANAGERS[tool_type]
    except KeyError as e:
        raise ValueError(f"Unknown package manager type: {tool_type}") from e
