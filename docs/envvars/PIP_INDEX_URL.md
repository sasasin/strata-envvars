# `PIP_INDEX_URL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata 本体の実行時設定として値を参照する箇所はありません。Strata Terminal 配布物を作る `packaging/package_terminal.py` は、ロック済み wheel を同梱 Python にインストールする際、親プロセスの環境変数を子プロセス用辞書へコピーした後、このキーを辞書から削除します。そのため、ビルド環境に設定されていても、当該インストール処理の pip 子プロセスには転送されません。

## 値と判定

値の内容は読み取って判定せず、文字列比較・数値変換・URL 検証もしません。`os.environ` のコピーにキーがあれば `env.pop(name, None)` で削除します。未設定なら辞書にキーはなく、`pop(..., None)` はそのまま通ります。空文字を含む設定値も、内容にかかわらず子プロセス環境から取り除かれます。

## 有効になる条件

- 対象経路は `packaging/package_terminal.py` の Terminal 配布物ビルド時に依存 wheel のインストールを行う場合です。`--skip-deps` の場合は `install_locked()` が呼ばれず、この削除処理も実行されません。
- `install_locked()` 内では、wheelhouse の有無やターゲット OS による分岐より前に環境辞書から削除します。pip の `install`、`check`、`list` の各子プロセスに同じ辞書を渡します。
- Strata の通常の CLI、サーバー、モデル処理がこの変数を読み取る実装は見つかりません。この名前の Strata 内参照は当該削除リストだけです。

## 実行時の詳細

`install_locked()` は呼び出された時点で `os.environ` を展開して環境辞書を作り、`PIP_INDEX_URL` を含む複数のキーを取り除いてから pip を `subprocess.run(..., env=env)` で起動します。値は Strata 内でキャッシュされず、各 `install_locked()` 呼び出し時点の環境が使われます。Strata はこの変数について専用ログや警告を出しません。pip の子プロセスが失敗した場合、`check=True` により `subprocess.run` が失敗を送出しますが、その内容や終了表示は pip 側の挙動であり、ここでは Strata のログ仕様として扱いません。

## 根拠

- `packaging/package_terminal.py:199-220` は環境辞書の生成、`PIP_INDEX_URL` の削除、辞書を渡す pip の各 subprocess 呼び出しを実装しています。
- `packaging/package_terminal.py:424-429` は `--skip-deps` でない場合だけ `install_locked()` を呼びます。
- `packaging/README.md:128-140` は Terminal archive が対象プラットフォーム向けに作られ、依存パッケージがビルド時にインストールされることを説明しています。

