# `STRATA_TRACE`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata の起動・prompt 読み込み・serve/batch 処理の進行状況や所要時間、GPU 空きメモリなどを stderr に出す診断用スイッチです。通常の計算経路や CLI 設定を選ぶ変数ではありません。ただし CUDA/HIP 系の `mem_mark()` では値の先頭が `2` の場合、各メモリ計測地点で追加の device 同期とエラー状態の出力を行います。

読み取りは `src/program/generate.cpp` と `src/prefill/prefill.cpp`、および SYCL 版の同名ソースにあります。設定を CLI 引数で上書きする処理や、Strata がこの値を子プロセスへ渡す処理は見つかりませんでした。`STRATA_TRACE_ADAPT` は別の環境変数であり、適応層専用ログの切替です。

## 値と判定

| 状態・値 | Strata の判定 |
|---|---|
| 未設定 | 対象ログを出さない。`mem_mark()` は何もしない。 |
| 空文字 | 設定済みとして扱い、通常の trace ログを有効にする。 |
| 任意の非空文字列（例: `0`, `1`, `true`, `false`, `abc`） | 文字列全体の parse や数値検証はなく、存在するだけで通常の trace ログを有効にする。 |
| 先頭文字が `2`（例: `2`, `2abc`） | 同様にログを有効にし、CUDA/HIP 系 `mem_mark()` では追加同期と device 状態ログも有効にする。 |

SYCL 版も設定の有無だけでメモリ trace を有効にしますが、同版の `mem_mark()` に値 `2` による追加同期分岐はありません。参照: `src/program/generate.cpp:1951-1967`, `sycl/src/program/generate.cpp:1322-1334`。

## 有効になる条件

- **起動時のメモリ計測**: `mem_mark()` が呼ばれる起動経路で有効です。CUDA/HIP 系では重み、session、expert cache、profile fill、prompt path 等の確保後に呼び出され、各地点の MiB 空き容量を出力します（`src/program/generate.cpp:5168,5190,6724,7247,7805,8335,8452,9023,9145,11218,11285,11777,20034,20108,20384,20433`）。SYCL 版にも対応する計測地点があります（`sycl/src/program/generate.cpp:4703,5053,5245,5662,5785,7410,7763,13082,13121`）。
- **prompt 処理**: CUDA/HIP 系では batched prompt の各 chunk で stage と経過時間を記録し、routed stream が有効な場合はコピー数と未使用 ring entry 数を追加出力します（`src/prefill/prefill.cpp:3464-3479,6236-6247`）。SYCL 版も各 prompt chunk を記録します（`sycl/src/prefill/prefill.cpp:2548-2551`）。routed stream の集計ログは `rs_on` かつ issuer thread の join 時だけです。
- **serve/batch 処理**: CUDA/HIP 系は serve ループで一度環境を確認して trace 関数を作り、要求処理の区間、prompt read、cache slot lend、batch decode、admission の時間などを記録します（`src/program/generate.cpp:13760-13770,15335-15348,17086-17095,17751-17765,17940-17953,19702-19715`）。SYCL 版も serve ループで設定有無を取得し、slot lend、batch decode、read のログを出します（`sycl/src/program/generate.cpp:9032-9039,10952-10959,11040-11052,11145-11152`）。
- **個別の補助ログ**: HIP の大きな prompt chunk 起動 probe が通った時のログ、file tier の再判定時の RAM 状態、prompt buffer サイズも設定有無で出力されます（`src/program/generate.cpp:1932-1947,10495-10508,20033-20044`）。
- **checkpoint の詳細計時**: CUDA/HIP 系の serve 実装で checkpoint 処理が通る際、sync/save/eviction の時間を記録します。checkpoint が無効、またはその経路を通らない場合は該当ログはありません（`src/program/generate.cpp:12331-12338,12415-12430,12431-12460,12507-12512`）。

この変数は診断出力を追加するもので、ログが出ること自体が機能の実行条件を変えるわけではありません。例外は値先頭 `2` の CUDA/HIP `mem_mark()` 同期です。OS や model 状態による一般的な有効条件はなく、上記のコード経路が実行されるかどうかで各ログの有無が決まります。

## 実行時の詳細

`mem_mark()` は `STRATA_TRACE` の `getenv()` 結果を `static` 変数に保持します。設定されていれば `cudaMemGetInfo`（SYCL は device memory info）で空き容量を取得し、`strata trace: <MiB> MiB free after <地点>` を stderr に出します。CUDA/HIP 系で値の先頭文字が `2` なら、さらに `cudaDeviceSynchronize()` と `cudaGetLastError()` を呼び、`strata trace: device ok/ERROR after ... (sync: ..., last error: ...)` を出力します。この同期結果による明示的な終了・fallback 分岐はありませんが、同期自体は追加の診断処理です（`src/program/generate.cpp:1951-1967`）。

その他の読み取りのタイミングは一律ではありません。serve trace は serve ループに入る時点で bool にし、そのループ中の各 log site で使います（`src/program/generate.cpp:13760-13769`）。prompt chunk のログや routed-stream 集計、HIP launch-probe 成功ログ、file-tier 再判定ログ、prompt buffer summary はそれぞれの処理時に `getenv()` を呼びます（`src/prefill/prefill.cpp:3472,6242`; `src/program/generate.cpp:1940,10503,20035`）。checkpoint trace は該当 serve 実行内で bool にします（`src/program/generate.cpp:12331-12338`）。したがって、プロセス開始時に一度だけ全用途の値を読む実装ではありません。通常の OS 環境変数はプロセス外から実行中に書き換えられないため、実用上は起動前に設定します。

無効値による parse error、警告、終了経路はありません。追加出力先は stderr で、trace を設定しない場合も通常の進捗表示や処理エラー出力は別途行われます。serve loop の trace 行に steady-clock の時刻を付ける仕様は Strata docs に記載されています（`docs/DETAILS.md:1614`）。同資料は routed-stream の chunk ごとのコピー/破棄件数（`docs/DETAILS.md:1141-1144`）、`docs/BATCHING.md:126` は admission の段階別時間を説明しており、いずれも上記実装と一致します。

## 根拠

- 値の読み取り、cache、追加 device 同期: `src/program/generate.cpp:1951-1967`; SYCL: `sycl/src/program/generate.cpp:1322-1334`。
- prompt chunk と routed stream: `src/prefill/prefill.cpp:3464-3479,6236-6247`; SYCL: `sycl/src/prefill/prefill.cpp:2548-2551`。
- serve trace bool と timestamped trace helper: `src/program/generate.cpp:13760-13770`。
- admission / checkpoint / read / lend trace: `src/program/generate.cpp:12331-12338,12415-12430,12431-12460,12507-12512,15335-15348,17086-17095,17751-17765,17940-17953,19702-19715`。
- 起動 probe / file tier / prompt buffers: `src/program/generate.cpp:1932-1947,10495-10508,20033-20044`。
- SYCL serve trace: `sycl/src/program/generate.cpp:9032-9039,10952-10959,11040-11052,11145-11152`。
- Strata の記述との照合: `docs/DETAILS.md:1141-1144,1614`; `docs/BATCHING.md:126`。
