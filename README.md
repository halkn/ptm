# ptm

GitHub Releases や公式インストーラー経由で CLI ツールをインストール・管理するツールマネージャー。

## インストール

```bash
uv tool install git+https://github.com/halkn/ptm
```

## 使い方

```text
ptm [--config PATH] <command> [tool]
```

### コマンド

| コマンド | 説明 |
| --- | --- |
| `ptm install [tool]` | ツールをインストール（インストール済みはスキップ） |
| `ptm update [tool]` | ツールを最新バージョンに更新 |
| `ptm list` | 管理対象ツールと現在のバージョンを一覧表示 |
| `ptm check` | インストール済みバージョンと最新バージョンを比較 |

`[tool]` を省略すると全ツールが対象になります。

```bash
# 全ツールをインストール
ptm install

# 特定ツールのみインストール
ptm install rg

# 全ツールを更新
ptm update

# バージョン確認
ptm check
```

### オプション

| オプション | 説明 |
| --- | --- |
| `--config PATH` | 設定ファイルのパスを指定（デフォルト: `~/.config/ptm/tools.toml`） |

```bash
ptm --config ~/dotfiles/tools.toml install
```

### 環境変数

| 変数名 | 説明 |
| --- | --- |
| `PTM_CONFIG` | 設定ファイルのデフォルトパスを変更 |
| `XDG_BIN_HOME` | バイナリのインストール先（デフォルト: `~/.local/bin`） |
| `GITHUB_TOKEN` | GitHub API のレート制限緩和用トークン |

## 設定ファイル

`~/.config/ptm/tools.toml` に管理するツールを定義します。

ツールは4種類の方法で管理できます。

---

### `[[github_release]]` — GitHub Releases からインストール

```toml
[[github_release]]
bin = "rg"
repo = "BurntSushi/ripgrep"
version_regex = 'ripgrep ([\d.]+)'

[github_release.platforms]
linux-x86_64 = "ripgrep-{version}-x86_64-unknown-linux-musl.tar.gz"
darwin-arm64 = "ripgrep-{version}-aarch64-apple-darwin.tar.gz"
```

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `bin` | ✓ | バイナリ名 |
| `repo` | ✓ | `owner/repo` 形式の GitHub リポジトリ |
| `platforms` | ✓ | プラットフォームとアセットファイル名のマッピング |
| `version` | | バージョン指定（デフォルト: `latest`、`nightly` も可） |
| `version_regex` | | バージョン文字列を抽出する正規表現 |
| `version_cmd` | | バージョン確認コマンド（デフォルト: `[bin, "--version"]`） |
| `opt_dir` | | アーカイブ全体を展開するディレクトリ（tar のみ） |
| `bin_path_in_archive` | | `opt_dir` 指定時のアーカイブ内バイナリパス |
| `strip_components` | | tar 展開時に除去するパス要素数（デフォルト: `1`） |
| `extra_bins` | | 追加でシンボリックリンクを作成するバイナリ名 |

**プラットフォームキー:** `linux-x86_64` / `linux-arm64` / `darwin-arm64` / `darwin-x86_64`

**テンプレート変数:**

- `{tag}` — タグ名（例: `v1.2.3`）
- `{version}` — `v` を除いたバージョン（例: `1.2.3`）

**アーカイブ全体を展開する場合（`opt_dir` 指定）:**

```toml
[[github_release]]
bin = "nvim"
repo = "neovim/neovim"
version = "nightly"
opt_dir = "~/.local/opt/neovim"
bin_path_in_archive = "bin/nvim"
version_regex = 'NVIM v([\d.]+-dev[^\s]*|[\d.]+)'

[github_release.platforms]
linux-x86_64 = "nvim-linux-x86_64.tar.gz"
darwin-arm64 = "nvim-macos-arm64.tar.gz"
```

---

### `[[url_release]]` — 任意の URL からインストール

GitHub 以外のホスティングサービス（Node.js 公式など）に使用します。

```toml
[[url_release]]
bin = "node"
version = "lts"
version_url = "https://nodejs.org/dist/index.json"
version_url_regex = '"version":"(v[\d.]+)"[^}]*"lts":"'
opt_dir = "~/.local/opt/node"
bin_path_in_archive = "bin/node"
strip_components = 1
extra_bins = ["npm", "npx", "corepack"]
version_regex = 'v([\d.]+)'

[url_release.platforms]
linux-x86_64 = "https://nodejs.org/dist/v{version}/node-v{version}-linux-x64.tar.xz"
darwin-arm64  = "https://nodejs.org/dist/v{version}/node-v{version}-darwin-arm64.tar.xz"
```

`github_release` と共通のフィールドに加え、以下が使えます。

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `version_url` | | 最新バージョンを取得する URL |
| `version_url_regex` | | `version_url` のレスポンスからバージョンを抽出する正規表現 |

`platforms` の値はアセットファイル名ではなく **完全な URL** を指定します。

---

### `[[installer]]` — カスタムインストーラー

公式インストールスクリプトを使う場合などに使用します。

```toml
[[installer]]
bin = "uv"
url = "https://astral.sh/uv/install.sh"
update_command = "uv self update"
version_regex = 'uv ([\d.]+)'
```

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `bin` | ✓ | バイナリ名 |
| `url` | | インストールスクリプトの URL（`curl \| sh` で実行） |
| `command` | | インストール時に実行するシェルコマンド |
| `update_command` | | 更新時に実行するコマンド（省略時は `command` を使用） |

`url` と `command` はいずれか一方を指定します。

---

### `[[npm]]` — npm グローバルパッケージ

`npm install -g` / `npm update -g` で管理したいツールに使用します。

```toml
[[npm]]
bin = "markdownlint-cli2"
version_regex = 'markdownlint-cli2 v([\d.]+)'

[[npm]]
bin = "tsc"
package = "typescript"
version_cmd = ["tsc", "--version"]
version_regex = 'Version ([\d.]+)'
```

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `bin` | ✓ | バイナリ名 |
| `package` | | npm パッケージ名（省略時は `bin` を使用） |
| `version_cmd` | | バージョン確認コマンド（デフォルト: `[bin, "--version"]`） |
| `version_regex` | | バージョン文字列を抽出する正規表現 |

---

## 開発

```bash
# 依存関係のインストール
uv sync

# テスト
uv run pytest

# Lint
uv run ruff check src/

# フォーマット
uv run ruff format src/

# 型チェック
uv run ty check src tests
```
