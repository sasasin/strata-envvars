# `STRATA_ADAPT_CALLBACK_WARMUP`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

Linux の `strata generate` 起動時に、CPU の `ExpertPool` を構築する前に CUDA の no-op host callback を一度キューへ送って完了を待ちます。ソースコメントと `docs/DETAILS.md` は、これにより CUDA ドライバーの host-callback thread を早期に作り、後で作成した thread が host 側の CPU affinity を引き継いで verifier の spin-wait と競合する状況を避ける意図だと説明しています。適応 swap の選択、layer callback、residency 更新を直接変更する処理ではありません。

## 値と判定

環境変数は `std::getenv()` で一度読み、文字列全体ではなく先頭文字だけを検査します。空文字は設定済みですが `e[0]` が `\0` のため warm-up を実行します。

| 値 | 判定 |
|---|---|
| 未設定 | 実行する（既定で有効） |
| 空文字 | 実行する |
| 先頭文字が `0`（例: `0`, `0abc`） | 実行しない |
| それ以外（例: `1`, `true`, `false`, `2`, ` abc`） | 実行する |

数値変換、空白除去、大文字小文字の正規化はありません。`false` も先頭が `0` ではないため実行します。

## 有効になる条件

- `src/program/generate.cpp` の Linux 条件付きブロック（`#if defined(__linux__)`）で処理されます。そこでは CUDA Runtime API を使います。
- 判定が実行でも、CUDA callback の起動または同期が失敗した場合は warm-up に成功しません。ただし、その場合も処理を続けます。
- Windows ではこの Linux ブロック自体がコンパイル対象にならず、この変数による warm-up はありません。

## 実行時の詳細

値は適応 overlap を使うかどうかとは独立して、expert arena の準備後、`ExpertPool` の構築直前に読み取られます。したがって、`strata generate` のこの初期化箇所で判断され、各リクエストで再評価する処理ではありません。環境変数を先頭文字 `0` にすると warm-up 呼び出し全体を飛ばします。

有効時は `cudaLaunchHostFunc(nullptr, [](void*) {}, nullptr)` で default stream に no-op callback を登録し、`cudaStreamSynchronize(nullptr)` で待ちます。いずれかの API が失敗すると `cudaGetLastError()` でエラー状態を取得し、stderr に `strata generate: could not warm up the GPU host-callback thread (continuing)` と出して続行します。両方が成功すると `strata generate: GPU host-callback thread started before host-core pinning` と出します。その直後に `ExpertPool` を作成し、pool worker は `pin_this_thread()` を呼びます。

## 文書との照合

`docs/DETAILS.md` は Linux で既定 ON、先頭値 `0` で無効と説明し、RTX 5090 / Ryzen 9 9950X の測定平均 142.82→207.75 tok/s を記載しています。この値は同資料の測定記載であり、本調査で再測定した値ではありません。関連する benchmark README は旧 revision `7695859aa13afb248bdb4d36f9b2e95707db079d` の実験条件を記録していますが、その中には warm-up の既定値を「on」とする記述と「off by default」とする記述が併存します。今回の対象 revision では、ソースの条件式が既定有効であることを確認しました。

## 根拠

- `src/program/generate.cpp:4795-4812` — Linux ガード、環境変数の先頭文字判定、callback の登録・同期、失敗時と成功時のログ、`ExpertPool` 構築順。
- `src/kernels/cpu/pool.cpp:437-465` — pool の worker thread を作成し、各 worker 内で `pin_this_thread()` を呼ぶ処理。
- `docs/DETAILS.md:1734-1739` — 設計意図と測定条件への案内。
- `bench/results/2026-10-11-rtx-5090-callback-affinity/README.md:44-51` — 旧 revision の実験記録と既定値に関する記述。
