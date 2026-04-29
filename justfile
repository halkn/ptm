set dotenv-load := false

default:
    @just --list

# Set up runtime and development dependencies.
setup:
    uv sync

# Run the full local verification suite.
check: lint format-check typecheck test

# Run Ruff lint checks.
lint:
    uv run ruff check src tests

# Format source and test files.
format:
    uv run ruff format src tests

# Check formatting without modifying files.
format-check:
    uv run ruff format --check src tests

# Run type checks.
typecheck:
    uv run ty check src tests

# Run tests with coverage enabled.
test:
    uv run pytest

# Run a quick CLI smoke test.
smoke:
    uv run ptm list
