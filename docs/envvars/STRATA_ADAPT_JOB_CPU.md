# `STRATA_ADAPT_JOB_CPU`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`--serve` の adaptive tier を非同期実行するときに作られるコピー用バックグラウンドスレッド `JobThread` の配置先論理 CPU を指定する。値が 0 以上なら `strata::kernels::cpu::pin_current_thread(cpu)` に渡す。これは adaptive tier の有効化や交換動作自体を切り替える設定ではなく、スレッドの CPU 配置だけを変える（`engine/src/program/generate.cpp:2454-2458,2503-2512,15598-15612`、SYCL 版は `engine/sycl/src/program/generate.cpp:1393-1398,1442-1448`）。

CUDA 系と SYCL 系の生成コードに読み取り箇所が一つずつある。CUDA 系では `--adapt-async`（または自動選択）が非同期 tier を選び、利用可能な適応対象がある場合に `JobThread` を生成する。CUDA 側の arena 経路も対象になる。SYCL 版は `--serve` と resident RAM mode などの条件を満たし、適応対象の使用量・交換領域がある場合に生成する（`engine/src/program/generate.cpp:11774-11811,15598-15612`、`engine/sycl/src/program/generate.cpp:7063-7081,9072-9080`）。

## 値と判定

両実装ともスレッドの `loop()` 開始時に `std::getenv` で値を読み、設定されていれば `std::atoi`、未設定なら OS 別の既定候補を使う。文字列全体の検査、変換失敗の検出、範囲検証はない。`atoi` の変換により、先頭空白と符号付き整数の後ろにある文字は無視される。空文字や整数として始まらない文字列は 0 相当になり、したがって CPU 0 を指定する。負値は pin 呼び出しをしない。

| 実装・条件 | unset | 設定時に有効になる値 | 設定時に pin しない値 |
|---|---|---|---|
| CUDA 系、Windows | `smt_spare_cpu()` が返す候補。複数論理 CPU を持つ物理 core のうち最後に見つかった core の2番目の論理 CPU。候補なしなら `-1` | `atoi` 結果が `0` 以上（例: `3`, `+3`, `3tail`, ` 3`） | `atoi` 結果が負（例: `-1`, `-2x`） |
| CUDA 系、Windows 以外 | 既定候補 `-1`。`--aux-cpus` が有効なら後述の補助 CPU 配置へ回る | 同上 | 同上 |
| SYCL、Windows | CUDA 系と同じ Windows 候補 | `atoi` 結果が `0` 以上 | `atoi` 結果が負 |
| SYCL、Windows 以外 | 既定候補 `-1`。このコードでは補助 CPU への代替 pin は行わない | `atoi` 結果が `0` 以上 | `atoi` 結果が負 |

空文字、`true`、`false`、`x`、`0anything` は `atoi` 結果が 0 となり、CPU 0 を要求する。`-1` と `-1tail` は pin しない。数値部分の桁あふれを含め、入力を安全な範囲か検査する処理はこの読み取り箇所にない（`engine/src/program/generate.cpp:2480-2501,2508-2512`、`engine/sycl/src/program/generate.cpp:1419-1440,1445-1448`）。

`--adapt-async` や `STRATA_ADAPT_ASYNC` は非同期 tier の選択に関係し、本変数の値を上書きしない。適応 tier を非同期にしない指定・条件では `JobThread` 自体が作られず、本変数は読まれない。`--aux-cpus` / `STRATA_AUX_CPUS` は CUDA 系で未設定時の補助配置に関係するが、明示した本変数の CPU 番号より優先しない（`engine/src/program/generate.cpp:4715-4725,2508-2512,15598-15612`）。

## 有効になる条件

- 値を読むには、非同期 adaptive tier 用 `JobThread` が生成される必要がある。CUDA 系では `--serve`、適応周期と swap 数が有効、resident RAM mode または arena などの条件を満たし、実際に適応対象があり、必要な交換容量があることが関係する。CUDA 系の制約には peer device / remote expert optimization、複数 GPU arena などの除外がある（`engine/src/program/generate.cpp:11774-11811,15598-15612`）。
- SYCL 版では非同期 tier は resident RAM mode が必要で、`--batch`、pipeline windows、peer device、remote expert optimization などでは停止される。実際の `JobThread` 生成には適応対象と交換容量も必要（`engine/sycl/src/program/generate.cpp:7063-7081,9072-9080`）。
- 値は job thread の起動時に一度読む。以後の request ごとに再読込せず、スレッド稼働中にプロセス環境を変更してもそのスレッドには反映されない（`engine/src/program/generate.cpp:2458,2503-2512`、`engine/sycl/src/program/generate.cpp:1397,1442-1448`）。
- pin の失敗は機能全体を止める条件ではない。`pin_current_thread` は失敗を stderr に出して以前の配置を保ち、呼び出し側は戻り値を無視して job loop を続ける（`engine/src/kernels/cpu/pool.cpp:699-722`）。
- CUDA 系で変数が設定されていれば、CPU 値が負または pin に失敗した場合も `note_owned_thread()` を呼び、補助 CPU 管理にその thread を委ねない。変数が未設定で候補が負なら `strata::aux_cpus::pin_current_thread()` に委ねる。SYCL 系にはこの分岐がなく、設定値が負なら追加 pin をしない（`engine/src/program/generate.cpp:2508-2512`、`engine/sycl/src/program/generate.cpp:1445-1448`）。

## 実行時の詳細

`JobThread` のコンストラクターが `std::thread` を開始し、そのスレッドが `loop()` に入ると thread 名を設定（CUDA 系のみ）してから環境変数を読み取る。値が 0 以上なら `pin_current_thread` を呼び、その後は条件変数で job を待ち、受け取ったコピー処理を逐次実行する。この設定が変えるのはそのスレッドの CPU 配置であり、コード上、adaptive tier の選択結果やコピー内容を変更する処理ではない（`engine/src/program/generate.cpp:2456-2458,2503-2524`、`engine/sycl/src/program/generate.cpp:1395-1398,1442-1459`）。

読み取り箇所では CPU 番号の範囲や利用可否を検証しない。番号の変換後にプラットフォーム helper が配置を試み、そこで設定に失敗すると以前の配置を維持して、スレッドは job 処理を続ける。macOS を含め、OS ごとの pin 実装差は `pin_current_thread` に委譲される（`engine/src/kernels/cpu/pool.cpp:699-722`）。

## ログと測定値

本変数を読み取ったことや設定値そのものを知らせるログはない。pin に失敗した場合は `engine/src/kernels/cpu/pool.cpp:706-708,717-718` の helper が次の形式を stderr に出す。失敗しても呼び出し元は処理を続ける。

- Windows: `strata cpu pool: host CPU Set selection for processor %d failed: %lu; previous placement kept`
- その他の pin 対応実装: `strata cpu pool: host affinity for CPU %d failed: %d; previous affinity kept`

この環境変数に関する測定値は、参照した Strata 資料に記載がない。

## 根拠

- `engine/src/program/generate.cpp:2480-2512` — Windows 既定候補、変数読み取り、pin と CUDA 系の補助 CPU 管理分岐。
- `engine/sycl/src/program/generate.cpp:1419-1448` — SYCL 版の既定候補と変数読み取り・pin。
- `engine/src/program/generate.cpp:11774-11811,15598-15612` — CUDA 系の非同期 tier 適用条件と JobThread 生成。
- `engine/sycl/src/program/generate.cpp:7063-7081,9072-9080` — SYCL 版の適用条件と JobThread 生成。
- `engine/src/kernels/cpu/pool.cpp:699-722` — pin 失敗時のログと以前の配置の維持。
- `docs/DETAILS.md:1435-1444` — 補助 CPU 配置との関係を確認する設計資料。挙動の根拠は上記ソースコード。
