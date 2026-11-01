# `E2E_CUDA_BIN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

これは通常の Strata engine 設定ではなく、実 engine を使う context E2E スクリプト `apps/host/scripts/context-e2e.mjs` 用の値です。スクリプトが Python の `serve/server.py` を子プロセスとして起動するとき、指定されたディレクトリをその子プロセスの `PATH` の先頭に加えます。スクリプト自身は CUDA 実行ファイルを探したり起動したりしません。

## 値と判定

共通 helper `env(name, fallback)` は `process.env[name] ?? fallback` を返します。`E2E_CUDA_BIN` は文字列としてそのまま使われ、数値変換、空白除去、存在確認、パス正規化、妥当性検査はありません。

| 状態 | `CUDA_BIN` の値 | 子サーバー起動時の `PATH` |
|---|---|---|
| 未設定 | `C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v13.0\\bin` | `<既定値>;<親プロセスの PATH>` |
| 空文字 | 空文字 | `;<親プロセスの PATH>` |
| その他の設定値 | 設定した文字列そのもの | `<設定値>;<親プロセスの PATH>` |

空文字は nullish coalescing の fallback 条件に該当しないため既定値になりません。値の境界や無効値用 fallback は実装されていません。CLI 引数による上書きもありません。

## 有効になる条件

- `E2E_BASE_URL` が空（未設定または空文字）のときに限り、スクリプトは自分で `serve/server.py` を起動し、`E2E_CUDA_BIN` を使った環境オブジェクトを渡します。`E2E_BASE_URL` が空でないときは既存サーバーへ接続し、Python サーバーを起動しないため、この設定値はどの子プロセスにも渡されません。
- 実装は Windows 用の既定パスを置き、`PATH` を `;` で連結し、PowerShell と `taskkill` を使っています。`E2E_CUDA_BIN` 自体に OS 判定はありません。
- スクリプトの先行チェックは `STRATA_HARNESS_DIR` と、既存サーバーモードでない場合の engine / GGUF ファイルを検査します。`E2E_CUDA_BIN` の値やディレクトリの存在はチェックしません。
- 子サーバーの `serve/server.py` は engine 用環境を `os.environ` のコピーから作り、設定された `lib_dirs` があれば Windows ではそれらをさらに `PATH` の先頭へ追加します。その環境を engine 起動時に `popen(..., env=env)` へ渡します。従って、E2E スクリプトの `PATH` は engine 用環境の基礎になりますが、`lib_dirs` がある場合はその値がさらに前へ追加されます。

## 実行時の詳細

値は ESM モジュール初期化時に `const CUDA_BIN` として一度読み取られます。起動後に Node プロセスの環境を書き換えても再評価されません。`E2E_BASE_URL` が空なら、行 79 で親の `process.env` を展開した環境オブジェクトを作り、`PATH` を `` `${CUDA_BIN};${process.env.PATH}` `` に置き換えて Python サーバーを起動します。子 server は `child_env()` で `os.environ` をコピーして engine 用の追加設定を行い、engine に渡します（`serve/server.py:3747-3781,9193`）。

`E2E_CUDA_BIN` 専用のログ、警告、終了分岐はありません。スクリプトは engine パスやモデルファイルがない場合に `missing: <path>` を出して終了コード 2 で終了し、サーバーが readiness check を通過しない場合は起動ログ末尾を表示して終了コード 4 になります。CUDA_BIN の値自体に起因する検出・エラー判定は実装されていません。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:347`。
- E2E 専用であること、共通 helper、既定値、モジュール初期化時の読み取り: `apps/host/scripts/context-e2e.mjs:3-10,25-37`。
- 既存サーバーモードの選択と設定値を使う子プロセス環境の構築: `apps/host/scripts/context-e2e.mjs:47-49,78-80,87`。
- 先行チェックと観測可能な終了経路: `apps/host/scripts/context-e2e.mjs:47-49,89-96`。
- engine 子環境のコピー、`lib_dirs` による PATH 追加、engine への渡し: `serve/server.py:3747-3781,9193`。実プロセスの起動箇所は `serve/server.py:1077-1079`。
