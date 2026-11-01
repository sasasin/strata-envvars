# `DSH_CLI`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`DSH_CLI` は DeepSeek Harness の `dsh` 実行ファイルのパスを指定します。Strata エンジンや API サーバーが読む設定ではなく、`integrations/harness/bridge_tests.py`、`integrations/harness/bridge_e2e.py`、`integrations/harness/revise_once.py` が Harness プロセスを起動するために読みます。実行時は選ばれたパスを `subprocess.Popen` の実行対象に渡します（`integrations/harness/bridge_tests.py:239,259-263,269-273`、`integrations/harness/bridge_e2e.py:165,172-179,202-204`、`integrations/harness/revise_once.py:73,94-99,112-115`）。

## 値と判定

3 スクリプトとも `argparse` の `--dsh` オプションの既定値を `os.environ.get("DSH_CLI", DEFAULT_DSH)` としています。`DEFAULT_DSH` は `/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh` です（`integrations/harness/_bridge.py:42`、`integrations/harness/bridge_e2e.py:42`）。

| 状態 | 選ばれる値と処理 |
|---|---|
| `DSH_CLI` 未設定 | 上記の `DEFAULT_DSH`。 |
| `DSH_CLI` 設定済み（空文字を含む） | その文字列。空文字も `os.environ.get` では既定値に置き換わらず、`Path("")` はカレントディレクトリ `.` になる。 |
| CLI に `--dsh PATH` を指定 | 環境変数の値を置き換えて `PATH` を使用する。 |

値を文字列として parse、正規化、環境変数内での展開はしません。3 スクリプトは `Path` に変換して `exists()` のみを確認し、実行可能ファイルかどうかは事前検証しません。したがって空文字やディレクトリなども存在すれば検査を通り、その後のプロセス起動で失敗し得ます。

## 有効になる条件

この変数を読むのは `integrations/harness/` の bridge テストと Time-skip の revision 補助スクリプトです。通常の Strata CLI、エンジン、サーバーの起動だけでは参照されません。各スクリプトの実行時にパスを決めるため、読み取り結果をプロセス間で共有する static cache はありません。

OS や GPU backend による分岐はありません。既定パスは macOS のアプリ配置を指しますが、コード上は任意のパスに差し替えられます。既定パスに対象がなくても `DSH_CLI` または `--dsh` で別の場所を指定できます。

## 実行時の詳細

- `bridge_tests.py` と `bridge_e2e.py` は選択したパス、Python 実行ファイル、profile の存在を検査し、欠落時は stderr に理由を出して終了コード `2` を返します。検査後、bridge fixture / E2E の開始処理から `dsh` を起動します（`integrations/harness/bridge_tests.py:259-263,269-273`、`integrations/harness/bridge_e2e.py:172-179,202-204`）。
- `revise_once.py` は選択したパスの存在を検査し、欠落時は stderr に `revise_once: the Harness CLI is not at ...; set DSH_CLI or --dsh` と出して終了コード `3` を返します。存在検査を通った後、指定パスを `Popen` に渡して Harness を起動します（`integrations/harness/revise_once.py:94-99,112-115`）。
- ディレクトリなど存在はするが起動できないパスでは、事前検査ではなく起動時に失敗します。`bridge_tests.py` は各ケースの例外を失敗として集計し、最終的に `1` を返します（`integrations/harness/bridge_tests.py:269-283`）。`bridge_e2e.py` は例外を失敗として表示し `1` を返し、`revise_once.py` は一般例外を stderr に報告して `1` を返します（`integrations/harness/bridge_e2e.py:271-309`、`integrations/harness/revise_once.py:168-173`）。
- `revise_once.py` は環境を複製して `DSH_HOME` を一時ホームに上書きしますが、`DSH_CLI` 自体は変更せず、選択した実行ファイルの起動後に子プロセスへ渡すための設定にも使いません（`integrations/harness/revise_once.py:109-115`）。他の 2 スクリプトの `Popen` 呼び出しも `env` を指定しないため、通常の環境を継承します（`integrations/harness/_bridge.py:98-106`）。

## 根拠

- `integrations/harness/_bridge.py:42` — `bridge_tests.py` と `revise_once.py` が import する既定 `dsh` パス。
- `integrations/harness/bridge_tests.py:239`、`integrations/harness/bridge_e2e.py:165`、`integrations/harness/revise_once.py:73` — 3 箇所の `DSH_CLI` 読み取りと `--dsh` 既定値。
- `integrations/harness/bridge_tests.py:259-283`、`integrations/harness/bridge_e2e.py:172-204,271-309`、`integrations/harness/revise_once.py:94-115,168-173` — パス検査、Harness 起動、失敗時の出力と終了経路。
