# `PYTHONDONTWRITEBYTECODE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

調査対象の Strata ソースには、この環境変数を読み取って値を判定したり、Strata の通常起動時の挙動を変えたりする箇所はありません。Strata が値を固定して子プロセスへ渡す箇所は、デスクトップアプリの `--self-test` が同梱 Python で Control を確認する経路と、Control のステージング確認スクリプトです。macOS の署名スクリプトも smoke test 中に値を export します。

## 値と判定

Strata は受け取った値を parse しません。該当するコードは子プロセスの環境に文字列 `1` を設定するか、シェルで `1` を export します。そのため Strata 側に未設定・空文字・無効値・境界値の判定や fallback はありません。CLI 引数や他の環境変数との優先順位もありません。

| 経路 | Strata が子プロセスへ渡す値 | 条件 |
|---|---|---|
| デスクトップ `--self-test` の Control 起動 | `1` | `--self-test` が指定され、Control コンポーネントが見つかると `strata.py --version` と `strata.py components engine ...` の各確認で設定 |
| Control ステージング確認 | `1` | `stage-control.py --check` が `check()` を実行し、同梱 Python を起動 |
| macOS 署名 smoke test | `1` | `smoke_app` または `smoke_terminal` を実行する間、スクリプトの環境に export |

## 有効になる条件

これは通常の Strata CLI・サーバー・モデル実行の設定ではありません。デスクトップアプリの自己診断、Control のステージング確認、または macOS パッケージ署名後の smoke test に限られます。OS/backend/build macro、モデル状態や別変数による Strata 内の有効化条件はありません。

候補一覧には、デスクトップ E2E 用スクリプトにもこの名前があります。`vision-e2e.mjs`、`installed-flow.mjs`、`pics-e2e.mjs`、`ui-flows.mjs`、`cards-e2e.mjs`、`local-gguf-e2e.mjs` はテスト子プロセス向け環境オブジェクトに `1` を含め、`app-close-matrix.py` も fake-engine 用環境辞書に `1` を含めます。これらはテスト専用の参照であり、製品実装の挙動の根拠にはしていません。

## 実行時の詳細

デスクトップ側では `--self-test` の分岐から `run_self_test()` が呼ばれます。Control が存在すれば `control_runs()` と `control_engine_notice()` を実行し、それぞれの Python `Command` に `PYTHONDONTWRITEBYTECODE=1` を設定します。結果は `control-runs-on-bundled-python` と `engine-missing-is-a-notice-not-a-download` の自己診断項目に記録されます。起動失敗・終了状態・期待した出力の有無が確認対象ですが、この環境変数自体について専用ログやエラー処理はありません。`--self-test` は報告コードでプロセスを終了させる経路です。

ステージング確認では同じ固定値を含む環境辞書を `strata.py --version` と installer probe の Python 子プロセスに渡します。前者が失敗すればその終了コードを返し、成功後に probe の終了コードを返します。macOS 署名スクリプトでは app と Terminal archive の smoke test 中に値を export し、アプリ自己診断、Python 起動確認などを行います。スクリプトの説明では、smoke test 時に署名済み bundle に書き込まない意図が示されています。Python 自体がこの値をどう解釈し、何を行うかは Strata の挙動としては記述しません。

プロセス内キャッシュやリクエストごとの再読込はありません。Strata はこの名前で現在の親プロセス環境を読むコードを持たず、記載した子プロセス起動時に固定値を渡します。

## 根拠

- `apps/desktop/src-tauri/src/main.rs:607-622,669-673,775-784,846-862` — `--self-test` の判定、自己診断経路と終了。
- `apps/desktop/src-tauri/src/main.rs:625-640,643-665` — Control の2つの確認で Python 子プロセスに値 `1` を設定し、その終了状態・出力を判定。
- `apps/desktop/scripts/stage-control.py:145-169` — ステージング確認の環境辞書と Python 子プロセス。
- `packaging/mac/sign-and-notarize.sh:387-395,466-477,526-527,681-682` — app / Terminal の smoke test での export と呼び出し。
- `apps/desktop/scripts/vision-e2e.mjs:29-36`、`installed-flow.mjs:57-62`、`pics-e2e.mjs:29-34`、`ui-flows.mjs:133`、`cards-e2e.mjs:23-29`、`local-gguf-e2e.mjs:28`、`app-close-matrix.py:82-90` — テスト専用の環境設定。

候補一覧 `docs/envvars/000_envvers.md:518` に名前がありますが、製品コードの設定値読み取りは確認できず、確認できた製品側参照は診断・パッケージ確認の子プロセスへの設定です。
