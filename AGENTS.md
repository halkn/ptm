# Repository Guidelines

## Project Structure

The application code lives under `src/ptm/`. The CLI entry point is `main.py`, command execution is handled in `commands.py`, installation and update logic lives in `installer.py`, configuration loading is in `config.py`, and shared models and resolution logic live in `models.py` and `resolver.py`. Tests live under `tests/` and should correspond to the target module, such as `tests/test_installer.py`. The repository root contains `pyproject.toml`, `README.md`, and `uv.lock`.

## Build, Test, and Development Commands

Use `uv` for local development.

- `uv sync`: Set up runtime and development dependencies.
- `uv run pytest`: Run tests with coverage enabled.
- `uv run ruff check src tests`: Check linting and import order.
- `uv run ruff format src tests`: Format code.
- `uv run ty check src tests`: Run type checking.
- `uv run ptm list`: Run a quick CLI smoke test.

## Coding Style

Target Python `>=3.11`, and add type hints to public functions. Use 4-space indentation, prefer double quotes for strings, and follow the output of `ruff format`. Use `snake_case` for functions, variables, and modules; `PascalCase` for classes; and `UPPER_SNAKE_CASE` for constants. Keep CLI-specific branching in `commands.py`, and keep `main.py` limited to startup concerns.

## Testing Guidelines

The test framework is `pytest`. Test files should be named `test_<module>.py`, and test functions should generally be named `test_<behavior>()`. For new features or behavior changes, add or update the corresponding `tests/test_*.py` file. Coverage is enabled in `pyproject.toml`, so maintain good coverage especially around installer, config, and command dispatch behavior.

## Commits and Pull Requests

Recent history uses short prefixes such as `docs:`, `test:`, `chore:`, and `refactor:`. Write commit messages in the imperative mood and keep them concise, for example `fix: handle missing release asset`. Pull requests should include a change summary, verification performed such as `uv run pytest` or `uv run ruff check src tests`, and related issue references when applicable. If CLI output or configuration behavior changes, include examples that make the impact clear.

## Security and Configuration

Do not commit tokens, local settings, or credentials. Treat `PTM_CONFIG`, `XDG_BIN_HOME`, and `GITHUB_TOKEN` as runtime inputs, and do not embed them in code. Use placeholders instead of real values in documentation and examples.
