# `E2E_MIN_FREE_GB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/scripts/context-e2e.mjs` の E2E 実行中に、空き物理 RAM がこの値を下回ったらメモリアラームを出し、実行を終了させます。通常の Strata エンジンやホストアプリの設定ではなく、実エンジンを使う context E2E スクリプト専用のしきい値です。同スクリプトの説明では、実エンジンを起動して4シナリオを実行する用途とされています（`apps/host/scripts/context-e2e.mjs:3-16`）。

## 値と判定

スクリプトのモジュール初期化時に `Number(env('E2E_MIN_FREE_GB', '7'))` として一度読みます。`env` helper は `process.env[name] ?? fallback` を返すため、環境変数が未設定なら文字列 `'7'` が渡され、既定値は `7` です（`apps/host/scripts/context-e2e.mjs:25-32`）。

JavaScript の `Number()` 変換後の値と、監視値 `free` の比較 `free < MIN_FREE_GB` で判定します。明示された空文字列は fallback されず `Number('')` により `0` になります。空白だけの値も `0`、数値に変換できない文字列は `NaN` です。変換できる数値に範囲制限や clamp はありません。しきい値と `free` が等しい場合は発火せず、厳密に下回った場合だけ発火します。したがって負数や `NaN` では通常の非負の空き RAM に対して発火せず、`Infinity` なら有限の空き RAM はしきい値を下回ります（`apps/host/scripts/context-e2e.mjs:32,84`）。

## 有効になる条件

- `E2E_BASE_URL` が空または未設定で、スクリプト自身がサーバーを起動する場合に限り監視します。`E2E_BASE_URL` が設定されている場合は既存サーバーを使い、サーバーを起動・停止しない経路として説明され、アラーム interval も作りません（`apps/host/scripts/context-e2e.mjs:36-37,78-85`）。
- 独自サーバー経路では、`STRATA_HARNESS_DIR` が必須です。さらに `E2E_ENGINE` とモデルファイルが存在しない場合は、監視開始前に終了します（`apps/host/scripts/context-e2e.mjs:47-49`）。
- `E2E_MIN_FREE_GB` は起動前の固定 RAM チェックには使われません。独自サーバー経路では、その時点の空き RAM が20 GB未満なら `only ... GB of RAM are free...` を stderr に出して終了コード2になります。ここは `E2E_MIN_FREE_GB` の値に関係しません（`apps/host/scripts/context-e2e.mjs:49`）。
- このスクリプトは Windows 固有の `powershell`、`taskkill`、Windows パスを使っています。ここに記載した値の判定・監視条件に CUDA/HIP/SYCL ビルド macro やエンジン CLI による上書きはありません（`apps/host/scripts/context-e2e.mjs:28-34,40-42,65`）。

## 実行時の詳細

監視間隔ごとに `freeGb()` を呼びます。これは PowerShell で `Win32_OperatingSystem.FreePhysicalMemory` を取得し、`1MB` で割って小数1桁に丸めた値を出力させ、Node.js 側で `Number()` に変換します。従って比較対象はディスク空き容量ではなく、PowerShell が返す空き物理 RAM の GB 相当値です（`apps/host/scripts/context-e2e.mjs:40-43`）。

独自サーバーを起動した後、3秒間隔の `setInterval` がしきい値を監視します。閾値を厳密に下回ると stderr に `ALARM: ${free} GB of RAM free, stopping the engine` を出し、`finish(3)` を呼びます。終了処理は interval を解除し、bridge を閉じ、サーバーが保持する PID に対して `taskkill /T /F` を実行してプロセスツリーを停止し、終了コード3でプロセスを終了します（`apps/host/scripts/context-e2e.mjs:63-74,83-85`）。

値はスクリプトの初期化時に定数へ読み込まれ、その後は再取得しません。実行中に環境変数を変更してもこのプロセスのしきい値は変わりません。CLI 引数や設定ファイルからの優先値もありません（`apps/host/scripts/context-e2e.mjs:25-32`）。

## 根拠

- 候補名は環境変数一覧にあります（`docs/envvars/000_envvers.md:351`）。Strata ソースでの完全一致参照は `apps/host/scripts/context-e2e.mjs:32` の1箇所で、`env` helper の動的な `process.env[name]` 参照とその呼び出しを確認しました（`apps/host/scripts/context-e2e.mjs:25-32`）。
- E2E スクリプトの実行用途は `apps/host/server/agent/README.md:155` にも記載されています。
