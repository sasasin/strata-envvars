# `IGC_EnableDPEmulation`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata の SYCL セットアップが、Intel Arc Alchemist と判定した構成の run config に `IGC_EnableDPEmulation=1` を追加し、サーバーがその値をエンジンの子プロセスへ渡します。Strata のコードはこの名前の値を読み取ったり解釈したりせず、エンジンにも参照箇所はありません。この変数を受け取る外部コンポーネントの挙動は、この調査の対象外です。

## 値と判定

Strata は `IGC_EnableDPEmulation` の値を parse しません。セットアップがこの変数を生成する経路では値を文字列 `1` に固定します（`sycl/setup_intel.py:369-386`）。Strata エンジン内の `getenv` 等による読み取りは、リポジトリ全体の完全一致検索で見つかりませんでした。

`strata launch` の Advanced 設定で任意の環境変数として指定した場合は、値を前後空白除去して設定に保存します。`off`、`unset`、`none`（大文字小文字を区別しない）はキーを削除し、それ以外は入力値をそのまま設定します。空値は空文字のまま渡されます。これは launcher の汎用環境設定処理であり、Strata エンジンがこの変数に適用する判定ではありません（`strata_cli/launch/settings.py:271-291,300-324`、`strata_control/tune_knobs.py:519-525`）。

## 有効になる条件

セットアップで自動的に追加する条件は、Intel GPU の driver が `i915` であるか、デバイス ID が `56a0`, `56a1`, `56a2`, `56a5`, `56a6`, `5690` のいずれかであることです。後者を含む判定は `ALCHEMIST_IDS` に基づきます（`sycl/setup_intel.py:57,344`）。条件外では、このセットアップ処理はこの変数を追加しません。

この条件は値の自動生成に対するものです。設定ファイルにこのキーがある場合、サーバーは backend による分岐をせず設定値を環境へコピーします（`serve/server.py:4054-4067`）。また、launcher の Advanced 設定は既存の config 環境値へ上書き・削除として適用されます（`strata_cli/launch/runner.py:566-574`）。

## 実行時の詳細

`to_sycl()` は Alchemist 条件で環境設定辞書にこの値を追加し、`out["env"]` として返します。Intel セットアップの run-script 生成処理は、変換後の config を JSON に書き込み、その config を使う起動スクリプトを生成します（`sycl/setup_intel.py:369-386,479-491,530-533`）。

サーバーの `child_env()` は親プロセスの環境を複製した後、config の `env` の各キーと値を文字列化して環境へ適用します。通常のエンジン起動はその環境を `StrataEngine` に渡します（`serve/server.py:4054-4067,9107-9115`）。この変数について Strata 独自の警告、値検証、fallback、終了条件は確認できません。未設定・空文字・`0` などの扱いや、GPU driver 側の動作は Strata ソースからは判定できません。

## 根拠

- `sycl/setup_intel.py:57,344,369-386` — Alchemist 判定、`1` の生成、config の `env` への設定。
- `sycl/setup_intel.py:479-491,530-533` — SYCL 用 config の変換と JSON 保存、起動スクリプト生成。
- `strata_cli/launch/settings.py:267-291,300-324`、`strata_control/tune_knobs.py:519-525` — Advanced 設定で環境名を受理し、値を保持・削除する汎用処理。
- `strata_cli/launch/runner.py:566-574` — Advanced 設定を launch config の環境へ適用。
- `serve/server.py:4054-4067,9107-9115` — config の環境をエンジン子プロセスへ渡す処理。

