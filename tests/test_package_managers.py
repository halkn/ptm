import pytest

from ptm.package_managers import (
    NPM_REGISTRY_PACKAGE_MANAGERS,
    get_package_manager,
    is_npm_registry_package_type,
)


def test_npm_registry_package_managers_define_commands() -> None:
    assert NPM_REGISTRY_PACKAGE_MANAGERS["npm"].executable == "npm"
    assert NPM_REGISTRY_PACKAGE_MANAGERS["bun"].executable == "bun"


@pytest.mark.parametrize("tool_type", NPM_REGISTRY_PACKAGE_MANAGERS)
def test_detects_npm_registry_package_type(tool_type: str) -> None:
    assert is_npm_registry_package_type(tool_type)


def test_rejects_unknown_package_manager_type() -> None:
    assert not is_npm_registry_package_type("pnpm")
    with pytest.raises(ValueError, match="Unknown package manager type"):
        get_package_manager("pnpm")
