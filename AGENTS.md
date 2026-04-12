# Repository Guidelines

## プロジェクト構成
アプリケーション本体は `src/ptm/` 配下にあります。CLI の起点は `main.py`、コマンド実行は `commands.py`、インストール・更新処理は `installer.py`、設定読み込みは `config.py`、共通モデルや解決処理は `models.py` と `resolver.py` に配置します。テストは `tests/` にあり、`tests/test_installer.py` のように対象モジュールに対応させます。ルートには `pyproject.toml`、`README.md`、`uv.lock` があります。

## ビルド・テスト・開発コマンド
ローカル開発では `uv` を使います。

- `uv sync`: 実行時依存と開発依存をセットアップします。
- `uv run pytest`: カバレッジ付きでテストを実行します。
- `uv run ruff check src tests`: Lint と import 順序を検査します。
- `uv run ruff format src tests`: コードを整形します。
- `uv run ty check src tests`: 型チェックを実行します。
- `uv run ptm list`: CLI の簡易動作確認を行います。

## コーディング規約
Python `>=3.11` を前提とし、公開関数には型ヒントを付けます。インデントは 4 スペース、文字列はダブルクォートを基本とし、`ruff format` の結果に従ってください。関数・変数・モジュールは `snake_case`、クラスは `PascalCase`、定数は `UPPER_SNAKE_CASE` を使います。CLI 向けの分岐は `commands.py` に寄せ、`main.py` には起動処理以上の責務を持たせないでください。

## テスト方針
テストフレームワークは `pytest` です。ファイル名は `test_<module>.py`、テスト関数名は `test_<behavior>()` を基本にします。新機能や仕様変更では、対応する `tests/test_*.py` を追加または更新してください。`pyproject.toml` でカバレッジ計測が有効なので、特に installer、config、command dispatch 周りの網羅性を維持してください。

## コミットと Pull Request
最近の履歴では `docs:`、`test:`、`chore:`、`refactor:` のような短い接頭辞を使っています。コミットメッセージは命令形で簡潔にし、例として `fix: handle missing release asset` のように書きます。Pull Request には変更概要、実施した確認内容（例: `uv run pytest`、`uv run ruff check src tests`）、関連 Issue があればその参照を含めてください。CLI の出力や設定ファイルの挙動が変わる場合は、影響が分かる例も添えてください。

## セキュリティと設定
トークン、ローカル設定、認証情報はコミットしないでください。`PTM_CONFIG`、`XDG_BIN_HOME`、`GITHUB_TOKEN` は実行時入力として扱い、コードへ埋め込まないでください。ドキュメントやサンプルでは実在値ではなくプレースホルダーを使います。
