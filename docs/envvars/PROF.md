# `PROF`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`PROF` は `tools/batch_test.py` のバッチ比較用テストスクリプトだけが読みます。設定が truthy なら、スクリプトは起動する `--serve` engine の環境に `STRATA_VERIFY_PROFILE=1` を追加し、Verifier の GPU stage 計測を有効にします。Strata engine、通常の CLI、server 実装が `PROF` を直接読む箇所はありません。

## 値と判定

Python の `os.environ.get("PROF")` を条件式に使い、値を parse しません（`tools/batch_test.py:118`）。

| `PROF` の状態 | 判定 | 子 engine に渡す値 |
|---|---|---|
| 未設定 | false | `STRATA_VERIFY_PROFILE` をこのスクリプトからは追加しない |
| 空文字 | false | 同上 |
| 空でない任意の文字列（`0`、`false` を含む） | true | `STRATA_VERIFY_PROFILE=1` |

設定時の値は engine にそのまま渡さず、固定値 `1` に置き換えます。スクリプトは常に `STRATA_DECODE_TIMING=1` も追加します。また、`--mt-min` が空でなければ `STRATA_IQ_MT_MIN` も設定します（同 `:118-120`）。

## 有効になる条件

- `tools/batch_test.py` を実行した場合に限ります。同スクリプトの docstring は、solo 実行と batch window 実行の token を比較するテスト用途と説明しています（`tools/batch_test.py:2-6`）。
- `PROF` は同スクリプトの Python プロセス起動時に参照されます。判定結果はローカルの `env` 辞書に一度反映され、`Engine` が `os.environ` を基に子プロセス用環境を作って engine を `--serve` で起動します（`tools/batch_test.py:118-121,47-62`）。
- engine 側は転送された `STRATA_VERIFY_PROFILE` の設定有無を verifier 初期化時に読みます。値の内容は見ず、設定されていれば `prof_on_` を有効にします（`src/core/verify.cpp:1022`）。この経路の計測結果は、serve の decode timing 集計に GPU stage 行として含められます（`src/program/generate.cpp:16055-16056,17170-17175`）。
- `PROF` を設定しない場合でも、このスクリプトは `STRATA_DECODE_TIMING=1` を渡します。従って `PROF` は per-request の decode timing 自体ではなく、子 engine に GPU verifier profile を要求するかを切り替えます。

## 実行時の詳細

`Engine` は追加環境を既存の `os.environ` に重ねて `subprocess.Popen` に渡し、`[exe, "--serve", ...]` を起動します。stderr は `BATCH_TEST_LOG` で指定されたファイル、または一時ディレクトリの `batch_test_engine.log` にリダイレクトされます。engine が `READY` を出さずに終了した場合、スクリプトはログファイルの場所を示して終了します（`tools/batch_test.py:55-66`）。

`PROF` 自体について、起動時に読み取る以外の再評価、数値変換、無効値エラー、専用ログはありません。profile buffer の確保失敗など、転送先 `STRATA_VERIFY_PROFILE` 側の挙動は `PROF` の判定ではなく verifier 実装によります。

## 根拠

- `PROF` の読み取り、truthiness 判定、`STRATA_VERIFY_PROFILE=1` と `STRATA_DECODE_TIMING=1` の設定: `tools/batch_test.py:118-121`。
- 子 engine 用環境の構築と `--serve` 起動、stderr ログ、`READY` 前終了時の失敗: `tools/batch_test.py:47-66`。
- engine が `STRATA_VERIFY_PROFILE` の設定有無を verifier 初期化時に保存: `src/core/verify.cpp:1022`。
- decode timing 設定の cache と GPU stage 行の出力: `src/program/generate.cpp:16055-16056,17170-17175`。
