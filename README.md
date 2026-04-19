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
| `--config PATH` | 設定ファイルのパスを指定（デフォルト: `~/.config/ptm/config.toml`） |

```bash
ptm --config ~/dotfiles/config.toml install
```

### 環境変数

| 変数名 | 説明 |
| --- | --- |
| `PTM_CONFIG` | 設定ファイルのデフォルトパスを変更 |
| `XDG_BIN_HOME` | バイナリのインストール先（デフォルト: `~/.local/bin`） |

GitHub Releases の取得では `gh` コマンドを優先します。`gh auth login` 済みであれば、その認証情報を使って `gh api` 経由で release 情報を取得します。`gh` が未インストール、または未ログインの場合は GitHub REST API へフォールバックします。

## 設定ファイル

`~/.config/ptm/config.toml` に管理するツールを定義します。

ツールは4種類の方法で管理できます。

---

### `[tools.<name>]` — ツール単位で定義

```toml
[tools.rg]
type = "github_release"
repo = "BurntSushi/ripgrep"
version_regex = 'ripgrep ([\d.]+)'

[tools.rg.platforms]
linux-x86_64 = "ripgrep-{version}-x86_64-unknown-linux-musl.tar.gz"
darwin-arm64 = "ripgrep-{version}-aarch64-apple-darwin.tar.gz"
```

`<name>` は論理名です。`bin` を省略した場合は `<name>` が使われます。

### `type = "github_release"` — GitHub Releases からインストール

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

### `type = "url_release"` — 任意の URL からインストール

GitHub 以外のホスティングサービス（Node.js 公式など）に使用します。

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

`github_release` と共通のフィールドに加え、以下が使えます。

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `version_url` | | 最新バージョンを取得する URL |
| `version_url_regex` | | `version_url` のレスポンスからバージョンを抽出する正規表現 |

`platforms` の値はアセットファイル名ではなく **完全な URL** を指定します。

---

### `type = "installer"` — カスタムインストーラー

公式インストールスクリプトを使う場合などに使用します。

```toml
[tools.uv]
type = "installer"
url = "https://astral.sh/uv/install.sh"
update_command = "uv self update"
version_url = "https://pypi.org/pypi/uv/json"
version_url_regex = '"version":"([\d.]+)"'
version_regex = 'uv ([\d.]+)'
```

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `bin` | ✓ | バイナリ名 |
| `url` | | インストールスクリプトの URL（`curl \| sh` で実行） |
| `command` | | インストール時に実行するシェルコマンド |
| `update_command` | | 更新時に実行するコマンド（省略時は `command` を使用） |
| `version_url` | | `ptm check` / `ptm update` 用の最新版取得 URL |
| `version_url_regex` | | `version_url` のレスポンスから最新版を抽出する正規表現 |

`url` と `command` はいずれか一方を指定します。

`version_url` を設定した `installer` は、`url_release` と同様に最新版比較の対象になります。`uv` のように公式インストーラーで導入しつつ、公開 API や JSON から最新バージョンを取得できるツール向けです。

---

### `type = "npm"` — npm グローバルパッケージ

`npm install -g` / `npm update -g` で管理したいツールに使用します。

```toml
[tools.markdownlint-cli2]
type = "npm"
version_regex = 'markdownlint-cli2 v([\d.]+)'

[tools.tsc]
type = "npm"
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

`ptm check` / `ptm update` では `npm view <package> version` を使って npm レジストリ上の最新版と比較します。

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
