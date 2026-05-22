# ptm

[![CI](https://github.com/halkn/ptm/actions/workflows/ci.yml/badge.svg)](https://github.com/halkn/ptm/actions/workflows/ci.yml)

A tool manager for installing and managing CLI tools from GitHub Releases, official installers, npm, Bun, and direct release URLs.

## Installation

```bash
uv tool install git+https://github.com/halkn/ptm
```

## Development

Use `uv` for dependency management and `just` for common development tasks.
Install `just` separately if it is not already available.

```bash
just setup
just check
```

Available tasks:

| Task                | Description                                 |
| ------------------- | ------------------------------------------- |
| `just setup`        | Set up runtime and development dependencies |
| `just check`        | Run all local checks                        |
| `just lint`         | Check linting and import order              |
| `just format`       | Format source and test files                |
| `just format-check` | Check formatting without modifying files    |
| `just typecheck`    | Run type checks                             |
| `just test`         | Run tests with coverage enabled             |
| `just smoke`        | Run a quick CLI smoke test                  |

## Usage

```text
ptm [--config PATH] <command> [tool]
```

### Commands

| Command               | Description                                              |
| --------------------- | -------------------------------------------------------- |
| `ptm install [tool]`  | Install tools, skipping tools that are already installed |
| `ptm update [tool]`   | Update tools to the latest version                       |
| `ptm list`            | List managed tools and their current versions            |
| `ptm check`           | Compare installed versions with the latest versions      |
| `ptm clean [--apply]` | Remove ptm-managed tools that are no longer configured   |

If `[tool]` is omitted, the command runs for all configured tools.

```bash
# Install all tools
ptm install

# Install one tool
ptm install rg

# Update all tools
ptm update

# Check versions
ptm check

# Show tools that would be removed
ptm clean

# Remove tools that are no longer configured
ptm clean --apply
```

### Options

| Option          | Description                                                           |
| --------------- | --------------------------------------------------------------------- |
| `--config PATH` | Specify the config file path. Defaults to `~/.config/ptm/config.toml` |

```bash
ptm --config ~/dotfiles/config.toml install
```

### Environment Variables

| Variable        | Description                                                          |
| --------------- | -------------------------------------------------------------------- |
| `PTM_CONFIG`    | Override the default config file path                                |
| `XDG_BIN_HOME`  | Set the binary installation directory. Defaults to `~/.local/bin`    |
| `XDG_DATA_HOME` | Set the managed tool installation root. Defaults to `~/.local/share` |

When fetching GitHub Releases, `ptm` prefers the `gh` command. If you have already run `gh auth login`, `ptm` uses those credentials and fetches release information through `gh api`. If `gh` is not installed or is not authenticated, `ptm` falls back to the GitHub REST API.

## Managed Files and Cleaning

For `github_release`, `url_release`, `npm`, and `bun` tools, `ptm` stores the actual installed files under:

```text
${XDG_DATA_HOME:-~/.local/share}/ptm/tools/<bin>/current
```

`$XDG_BIN_HOME` contains symlinks to those managed files. This keeps `ptm` from deleting commands that were installed by other tools into the same bin directory.

`ptm clean` compares the managed tool directories with the current config and shows tools that are no longer configured. It is a dry-run by default; pass `--apply` to remove the managed tool directory and only the symlinks that point into it.

Tools installed before this managed-root layout are not adopted automatically. `installer` tools are not cleaned because their install locations are controlled outside `ptm`.

## Configuration

Define managed tools in `~/.config/ptm/config.toml`. Most tools fit on a single
line: the table key is the binary name and the value is a `backend:source`
string.

```toml
[tools]
rg = "github:BurntSushi/ripgrep"
fd = "github:sharkdp/fd"
nvim = "github:neovim/neovim@nightly"
prettier = "npm:prettier@3.2.0"
tsc = "npm:typescript"
markdownlint-cli2 = "bun:markdownlint-cli2"
```

The platform-specific release asset is detected automatically, so `platforms`,
`version_regex`, and the like are usually unnecessary.

### Source strings

A source is `backend:locator[@version]`.

| Backend     | Type             | Locator             | Example                              |
| ----------- | ---------------- | ------------------- | ------------------------------------ |
| `github`    | GitHub Releases  | `owner/repo`        | `github:BurntSushi/ripgrep`          |
| `npm`       | npm package      | package name        | `npm:prettier`, `npm:@angular/cli`   |
| `bun`       | Bun package      | package name        | `bun:markdownlint-cli2`              |
| `url`       | Any release URL  | _(use table form)_  | see below                            |
| `installer` | Custom installer | install script URL  | `installer:https://astral.sh/uv/install.sh` |

- The table key becomes both the logical name and the binary name, so renamed
  binaries (`rg` from `ripgrep`) need no extra field.
- `@version` pins a version and defaults to `latest`. `nightly` is also
  supported for GitHub releases. The leading `@` of a scoped npm package is not
  treated as a version (`npm:@angular/cli@18` pins `18`).
- For `npm` / `bun`, the locator defaults to the binary name when omitted
  (`tsc = "npm:typescript"` installs `typescript` and runs `tsc`).

### Table form for advanced options

When a tool needs more than a source string, use a `[tools.<name>]` table with a
`source` key plus any overrides. Explicit fields take precedence over the
source string.

```toml
# Full-archive extraction and extra binaries
[tools.nvim]
source = "github:neovim/neovim@nightly"
bin_path_in_archive = "bin/nvim"

# Node.js from the official dist server
[tools.node]
source = "url"
version = "lts"
version_url = "https://nodejs.org/dist/index.json"
version_url_regex = '"version":"(v[\d.]+)"[^}]*"lts":"'
bin_path_in_archive = "bin/node"
extra_bins = ["npm", "npx", "corepack"]
version_regex = 'v([\d.]+)'

[tools.node.platforms]
linux-x86_64 = "https://nodejs.org/dist/v{version}/node-v{version}-linux-x64.tar.xz"
darwin-arm64 = "https://nodejs.org/dist/v{version}/node-v{version}-darwin-arm64.tar.xz"

# Official installer script with a version endpoint for update checks
[tools.uv]
source = "installer:https://astral.sh/uv/install.sh"
update_command = "uv self update"
version_url = "https://pypi.org/pypi/uv/json"
version_url_regex = '"version":"([\d.]+)"'
version_regex = 'uv ([\d.]+)'
```

### Fields

| Field                 | Backends                 | Description                                                                              |
| --------------------- | ------------------------ | ---------------------------------------------------------------------------------------- |
| `source`              | all (table form)         | `backend:locator[@version]` string                                                       |
| `version`             | all                      | Version to install. Defaults to `latest`; `nightly` for GitHub releases                  |
| `version_cmd`         | all                      | Version check command. Defaults to `[bin, "--version"]`                                  |
| `version_regex`       | all                      | Regular expression (with one capture group) to extract the installed version from `version_cmd` output. Defaults to the first version-like token (e.g. `14.1.0` from `ripgrep 14.1.0`), so it is rarely needed |
| `platforms`           | `github`, `url`          | Override automatic asset selection. Maps platform keys to asset names (`github`) or full URLs (`url`) |
| `bin_path_in_archive` | `github`, `url`          | Binary path inside the archive when the full archive should be extracted                 |
| `strip_components`    | `github`, `url`          | Leading path components to strip when extracting tar archives. Defaults to `1`           |
| `extra_bins`          | `github`, `url`, `npm`, `bun` | Additional binary names to symlink                                                  |
| `version_url`         | `url`, `installer`       | URL used to fetch the latest version                                                     |
| `version_url_regex`   | `url`, `installer`       | Regular expression used to extract the version from the `version_url` response           |
| `command`             | `installer`              | Shell command to run during installation (alternative to the install script URL)        |
| `update_command`      | `installer`              | Command to run during updates. Uses `command` when omitted                               |

**Platform keys:** `linux-x86_64` / `linux-arm64` / `darwin-arm64` / `darwin-x86_64`

**Template variables** (in `platforms` values): `{tag}` (tag name, e.g. `v1.2.3`)
and `{version}` (without the leading `v`, e.g. `1.2.3`).

For `url` tools, `platforms` values must be full URLs. Automatic resolution
without `platforms` currently supports only the `node` configuration that uses
`https://nodejs.org/dist/index.json`.

`npm` / `bun` tools are installed into an isolated managed directory (not your
global package directory) and their binaries are linked into `$XDG_BIN_HOME`.
When the version is `latest`, both compare against the latest version through
the npm registry metadata API; pinned versions are installed and compared as-is.

An `installer` with `version_url` is included in latest-version comparisons,
which is useful for tools such as `uv` where the installer performs installation
but a public endpoint provides the latest version.

---

## Development

GitHub Actions runs `ruff`, `ty`, and `pytest` on `push` and `pull_request`.

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Lint
uv run ruff check src tests

# Format
uv run ruff format src tests

# Type check
uv run ty check src tests
```
