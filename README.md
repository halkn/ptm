# ptm

[![CI](https://github.com/halkn/ptm/actions/workflows/ci.yml/badge.svg)](https://github.com/halkn/ptm/actions/workflows/ci.yml)

A tool manager for installing and managing CLI tools from GitHub Releases, official installers, npm, Bun, and direct release URLs.

## Installation

```bash
uv tool install git+https://github.com/halkn/ptm
```

## Usage

```text
ptm [--config PATH] <command> [tool]
```

### Commands

| Command              | Description                                              |
| -------------------- | -------------------------------------------------------- |
| `ptm install [tool]` | Install tools, skipping tools that are already installed |
| `ptm update [tool]`  | Update tools to the latest version                       |
| `ptm list`           | List managed tools and their current versions            |
| `ptm check`          | Compare installed versions with the latest versions      |

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
```

### Options

| Option          | Description                                                           |
| --------------- | --------------------------------------------------------------------- |
| `--config PATH` | Specify the config file path. Defaults to `~/.config/ptm/config.toml` |

```bash
ptm --config ~/dotfiles/config.toml install
```

### Environment Variables

| Variable       | Description                                                       |
| -------------- | ----------------------------------------------------------------- |
| `PTM_CONFIG`   | Override the default config file path                             |
| `XDG_BIN_HOME` | Set the binary installation directory. Defaults to `~/.local/bin` |

When fetching GitHub Releases, `ptm` prefers the `gh` command. If you have already run `gh auth login`, `ptm` uses those credentials and fetches release information through `gh api`. If `gh` is not installed or is not authenticated, `ptm` falls back to the GitHub REST API.

## Configuration

Define managed tools in `~/.config/ptm/config.toml`.

Tools can be managed in four ways.

---

### `[tools.<name>]` - Define a Tool

```toml
[tools.rg]
type = "github_release"
repo = "BurntSushi/ripgrep"
version_regex = 'ripgrep ([\d.]+)'

[tools.rg.platforms]
linux-x86_64 = "ripgrep-{version}-x86_64-unknown-linux-musl.tar.gz"
darwin-arm64 = "ripgrep-{version}-aarch64-apple-darwin.tar.gz"
```

`<name>` is the logical tool name. If `bin` is omitted, `<name>` is used as the binary name.

### `type = "github_release"` - Install from GitHub Releases

| Field                 | Required | Description                                                                              |
| --------------------- | -------- | ---------------------------------------------------------------------------------------- |
| `bin`                 | yes      | Binary name                                                                              |
| `repo`                | yes      | GitHub repository in `owner/repo` format                                                 |
| `platforms`           | yes      | Mapping of platform keys to asset file names                                             |
| `version`             |          | Version to install. Defaults to `latest`; `nightly` is also supported                    |
| `version_regex`       |          | Regular expression used to extract the version string                                    |
| `version_cmd`         |          | Version check command. Defaults to `[bin, "--version"]`                                  |
| `opt_dir`             |          | Directory where the full archive is extracted. Tar archives only                         |
| `bin_path_in_archive` |          | Binary path inside the archive when `opt_dir` is set                                     |
| `strip_components`    |          | Number of leading path components to strip when extracting tar archives. Defaults to `1` |
| `extra_bins`          |          | Additional binary names to symlink                                                       |

**Platform keys:** `linux-x86_64` / `linux-arm64` / `darwin-arm64` / `darwin-x86_64`

**Template variables:**

- `{tag}` - Tag name, for example `v1.2.3`
- `{version}` - Version without the leading `v`, for example `1.2.3`

**Extracting a full archive with `opt_dir`:**

```toml
[tools.nvim]
type = "github_release"
repo = "neovim/neovim"
version = "nightly"
opt_dir = "~/.local/opt/neovim"
bin_path_in_archive = "bin/nvim"
version_regex = 'NVIM v([\d.]+-dev[^\s]*|[\d.]+)'

[tools.nvim.platforms]
linux-x86_64 = "nvim-linux-x86_64.tar.gz"
darwin-arm64 = "nvim-macos-arm64.tar.gz"
```

---

### `type = "url_release"` - Install from Any URL

Use this for hosting services other than GitHub, such as official Node.js releases.

```toml
[tools.node]
type = "url_release"
version = "lts"
version_url = "https://nodejs.org/dist/index.json"
version_url_regex = '"version":"(v[\d.]+)"[^}]*"lts":"'
opt_dir = "~/.local/opt/node"
bin_path_in_archive = "bin/node"
strip_components = 1
extra_bins = ["npm", "npx", "corepack"]
version_regex = 'v([\d.]+)'

[tools.node.platforms]
linux-x86_64 = "https://nodejs.org/dist/v{version}/node-v{version}-linux-x64.tar.xz"
darwin-arm64  = "https://nodejs.org/dist/v{version}/node-v{version}-darwin-arm64.tar.xz"
```

In addition to the fields shared with `github_release`, these fields are available.

| Field               | Required | Description                                                                    |
| ------------------- | -------- | ------------------------------------------------------------------------------ |
| `version_url`       |          | URL used to fetch the latest version                                           |
| `version_url_regex` |          | Regular expression used to extract the version from the `version_url` response |

Values in `platforms` must be **full URLs**, not asset file names.

If `platforms` is omitted, automatic resolution currently supports only the `node` configuration that uses `https://nodejs.org/dist/index.json`. Other `url_release` tools require explicit `platforms`.

---

### `type = "installer"` - Custom Installer

Use this for official installation scripts and similar installers.

```toml
[tools.uv]
type = "installer"
url = "https://astral.sh/uv/install.sh"
update_command = "uv self update"
version_url = "https://pypi.org/pypi/uv/json"
version_url_regex = '"version":"([\d.]+)"'
version_regex = 'uv ([\d.]+)'
```

| Field               | Required | Description                                                                           |
| ------------------- | -------- | ------------------------------------------------------------------------------------- |
| `bin`               | yes      | Binary name                                                                           |
| `url`               |          | Installation script URL, executed as `curl \| sh`                                     |
| `command`           |          | Shell command to run during installation                                              |
| `update_command`    |          | Command to run during updates. Uses `command` when omitted                            |
| `version_url`       |          | URL used by `ptm check` and `ptm update` to fetch the latest version                  |
| `version_url_regex` |          | Regular expression used to extract the latest version from the `version_url` response |

Specify either `url` or `command`.

An `installer` with `version_url` is included in latest-version comparisons, just like `url_release`. This is useful for tools such as `uv`, where the official installer performs installation but a public API or JSON endpoint can provide the latest version.

---

### `type = "npm"` / `type = "bun"` - npm / Bun Global Packages

Use this for tools managed as global npm or Bun packages.

```toml
[tools.markdownlint-cli2]
type = "npm"
version_regex = 'markdownlint-cli2 v([\d.]+)'

[tools.tsc]
type = "npm"
package = "typescript"
version_cmd = ["tsc", "--version"]
version_regex = 'Version ([\d.]+)'

[tools.prettier]
type = "bun"
```

| Field           | Required | Description                                             |
| --------------- | -------- | ------------------------------------------------------- |
| `bin`           | yes      | Binary name                                             |
| `package`       |          | npm / Bun package name. Defaults to `bin`               |
| `version_cmd`   |          | Version check command. Defaults to `[bin, "--version"]` |
| `version_regex` |          | Regular expression used to extract the version string   |

`type = "npm"` runs `npm install -g <package>` / `npm update -g <package>`.
`type = "bun"` runs `bun install -g <package>` / `bun update -g <package>`.
Both compare against the latest version through the npm registry metadata API.

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
