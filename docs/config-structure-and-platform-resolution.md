# Config Structure And Platform Resolution

## 背景

現状の設定ファイルは `[[github_release]]` / `[[url_release]]` / `[[installer]]` / `[[npm]]` のように取得方式ごとの配列テーブルで構成されています。

この構造は実装側では扱いやすい一方で、利用者が設定を読む単位である「ツールごと」とズレています。特に以下の点で見通しが悪くなります。

- 特定ツールの設定を探しにくい
- 同じツールの差分比較より、取得方式の分類が前面に出る
- `platforms` の記述量が多い
- 型ごとの必須・任意項目が設定ファイル上で分かりにくい

加えて、`platforms` は現状「明示マッピング必須」のため、GitHub Releases のように asset 名がある程度規則的なケースでも設定量が減りません。

## 目的

- TOML を維持したまま設定の一覧性を上げる
- ツール単位で設定を把握しやすくする
- `platforms` の手書き量を減らす
- 構造変更と platform 自動判定の責務を切り分けて段階導入できるようにする

## 提案 1: ツール中心の TOML 構造

### 推奨構造

設定のルートを `[tools.<name>]` に統一し、取得方式は `type` で切り替えます。

```toml
[tools.rg]
type = "github_release"
repo = "BurntSushi/ripgrep"
version_regex = 'ripgrep ([\\d.]+)'

[tools.rg.platforms]
linux-x86_64 = "ripgrep-{version}-x86_64-unknown-linux-musl.tar.gz"
darwin-arm64 = "ripgrep-{version}-aarch64-apple-darwin.tar.gz"

[tools.node]
type = "url_release"
version = "lts"
version_url = "https://nodejs.org/dist/index.json"
version_url_regex = '"version":"(v[\\d.]+)"[^}]*"lts":"'
opt_dir = "~/.local/opt/node"
bin_path_in_archive = "bin/node"
strip_components = 1
extra_bins = ["npm", "npx", "corepack"]

[tools.node.platforms]
linux-x86_64 = "https://nodejs.org/dist/v{version}/node-v{version}-linux-x64.tar.xz"
darwin-arm64 = "https://nodejs.org/dist/v{version}/node-v{version}-darwin-arm64.tar.xz"

[tools.uv]
type = "installer"
url = "https://astral.sh/uv/install.sh"
update_command = "uv self update"

[tools.markdownlint]
type = "npm"
bin = "markdownlint-cli2"
package = "markdownlint-cli2"
version_regex = 'markdownlint-cli2 v([\\d.]+)'
```

### この構造の利点

- ツール単位でまとまるため、設定探索がしやすい
- `type` が変わっても骨格が変わらない
- TOML の標準機能だけで十分に表現できる
- 実装側も `tools` テーブルを一度なめればよく、ローダーが単純になる

### 補足ルール

- `[tools.<name>]` の `<name>` は論理名とする
- `bin` は省略可能とし、省略時は `<name>` をデフォルト値にする
- `platforms` は当面残す
- `platforms` は将来的に「override 用」の位置づけにする

## 提案 2: platform 自動判定

### 目標

GitHub Releases の asset 名がよくある命名規則に従う場合、設定ファイルに `platforms` を書かなくても対象 asset を選べるようにする。

### 期待する利用イメージ

```toml
[tools.rg]
type = "github_release"
repo = "BurntSushi/ripgrep"
version_regex = 'ripgrep ([\\d.]+)'
```

これだけで、実行環境に応じて適切な asset を選べる状態を目指します。

### 適用対象

第1段階では `github_release` のみを対象にします。

理由:

- GitHub API で release asset 一覧を取得しやすい
- asset 名に規則性があるツールが多い
- `url_release` は URL テンプレートの自由度が高く、自動判定ルールを一般化しにくい

### 判定方針

実行環境から以下の情報を正規化して使います。

- OS: `linux` / `darwin`
- CPU: `x86_64` / `arm64`

asset 名の候補スコアリングで選択します。

- OS トークン一致
- CPU トークン一致
- 圧縮形式の優先順位一致
- 不要語の除外

例:

- `linux`, `linux-x64`, `linux-x86_64`, `unknown-linux-musl`
- `darwin`, `macos`, `apple-darwin`
- `arm64`, `aarch64`
- `x86_64`, `amd64`, `x64`

### 自動判定の優先順位

1. `platforms` が定義されていればそれを使う
2. `platforms` がなければ release assets から自動判定する
3. 候補が 0 件ならエラー
4. 候補が複数件で優劣が付かなければエラー

この方針により、既存ユーザーは壊さず、新規設定だけ楽にできます。

### 失敗時のふるまい

fail-fast にします。曖昧な asset を適当に選ばないことを優先します。

エラーメッセージには以下を含めます。

- 対象ツール名
- 検出した実行環境
- 候補 asset 名
- `platforms` で明示指定できること

### 将来拡張候補

- `asset_pattern` による絞り込み
- `prefer_archive = "tar.gz"` のようなヒント
- `exclude_patterns` のような除外ルール
- `url_release` への限定的な自動化

## データモデルへの影響

### 設定ローダー

ローダーは次の流れに整理できます。

1. 新形式 `[tools.<name>]` を読む
2. `bin` がなければ `<name>` を補う
3. `type` ごとに必須項目を検証する
4. 既存の `ToolSpec` に詰め替える

### バリデーション

構造変更に合わせて、ローダーで最低限これを検証したいです。

- `type` が既知か
- `github_release` では `repo` があるか
- `github_release` で自動判定を使わない場合は `platforms` があるか
- `installer` では `url` または `command` のどちらかがあるか
- `npm` では `package` は省略可能だが、最終的に補完できるか

### 実装方針

当面は `ToolSpec` を維持し、ローダーと resolver の責務を整理して対応するのが妥当です。

- PR1 ではモデルの全面分割はしない
- PR2 で resolver に asset 自動判定ロジックを追加する
- 型ごとの dataclass 分割は将来の拡張余地として残す

## PR 分割案

### PR1: TOML 構造再設計

スコープ:

- `[tools.<name>]` 形式の追加
- 既存形式からの移行互換
- `bin` の省略補完
- README / サンプル更新
- テスト追加

この PR では installer / resolver の挙動は極力変えません。

### PR2: platform 自動判定

スコープ:

- GitHub release asset 一覧の取得
- asset 名の正規化とスコアリング
- `platforms` 未指定時の自動選択
- 曖昧時エラー
- テスト追加

この PR では設定構造の互換面には触れず、解決ロジックに集中します。

## 推奨判断

以下の順で進めるのが最も安全です。

1. PR1 で設定構造をツール中心に再設計する
2. 新構造で `platforms` を override として残す
3. PR2 で `github_release` の自動判定を追加する

この順番なら、設定 UX と解決ロジックをそれぞれ別観点でレビューできます。

## Open Questions

- `tools.<name>` の `<name>` を CLI の表示名と同一にするか
- `bin` を完全省略可能にするか、明示を残すか
- `platforms` 未指定時の自動判定を opt-in にするか、既定にするか
- 自動判定時に圧縮形式の優先ルールをどこまで固定するか
- Linux の `gnu` / `musl` 差分をどう扱うか
