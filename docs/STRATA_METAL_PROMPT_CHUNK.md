# `STRATA_METAL_PROMPT_CHUNK`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal エンジンの高速 prompt 経路で、一度に処理する入力 token 行数（chunk size）を指定します。prompt の全体長ではなく、chunk ごとに繰り返す処理の行数です。SSD から expert をストリーミングする場合と、モデルが常駐している場合で読み取り箇所・既定値・上限が異なります。

## 値と判定

どちらの経路も `std::atoi` で先頭の整数部分を読みます。文字列全体の検証はしません。したがって空文字や数値で始まらない値は 0、`512tail` は 512、負数は後述の下限値になります。値は行数として使われます。

| 経路 | 未設定時 | 設定時の変換・制限 |
|---|---|---|
| 常駐モデルの prompt GEMM | 2048 | `max(64, min(8192, atoi(value)))`。範囲は64〜8192。64の倍数への丸めはしない |
| SSD ストリーミングの prompt GEMM | 物理メモリが96 GiB以上なら4096、それ未満なら1024 | `max(64, atoi(value))` の後、64の倍数へ切り下げる。明示値に8192の上限はない |

例として `0`、空文字、`abc`、負数はいずれも64行になります。常駐経路で `500` は500行、ストリーミング経路では448行です。ストリーミング経路で64未満も64行、常駐経路で8192超も8192行です。数値変換の範囲外入力の動作は文書化できる安全な範囲として扱わず、指定しません。

## 有効になる条件

- 対象は Metal エンジンです。
- `STRATA_METAL_PROMPT=window` なら prompt は decode window 経路へ固定され、この chunk 設定を使う GEMM 経路には入りません。
- 非ストリーミング時は、`STRATA_METAL_PROMPT_GEMM` が文字列全体として `0` でなく、prompt 長が `STRATA_METAL_PROMPT_GEMM_MIN` 以上で、GEMM 用状態が初期化できた場合に使われます。同じ値判定は常駐経路内にもあり、既定の最小長は64です。
- ストリーミング時も `STRATA_METAL_PROMPT=window` は GEMM prompt を無効にします。また `STRATA_METAL_PROMPT_GEMM=0` または prompt 長が `STRATA_METAL_PROMPT_GEMM_MIN` 未満なら従来の window 経路になります。既定の最小長は64です。
- `STRATA_METAL_PROMPT_GEMM` はストリーミング arena 初期化時にも参照されます。値が未設定または `0` 以外なら、arena の slot 数引数を576にして prompt GEMM 用領域を見込んだ後、chunk 値を読みます。`0` の場合は slot 数引数が64になり、prompt 実行時の分岐も window 経路になります。

## 実行時の詳細

常駐経路では、最初の `Window::prompt()` 呼び出し時に chunk 行数を `static const` として計算し、以後そのプロセス内では再評価しません。各 chunk について prompt chain を実行し、次の行群へ進みます。chunk の最終部分だけは指定行数より短くなります。

ストリーミング経路では `prompt_gemm_init()` で値を読み、`PromptGemm` の `MT` として保持します。ストリーミング arena の初期化中に作られるのが通常で、prompt 実行時に遅延初期化される場合も、一度 `pg_` が作られると再初期化しません。各 chunk で token を整数配列へコピーし、`prompt_chunk()` と任意の `on_chunk` 処理を順に実行します。prompt GEMM 用 arena 領域を確保できない場合は `metal prompt: no arena region for the prompt buffers` で失敗します。

初期化に成功すると stderr に `strata metal: prompts on the matrix units in chunks of %d ...` が出て、選択された行数、expert/QSA variant、layout、buffer size が表示されます。常駐経路では必要な Metal buffer を確保し、ストリーミング経路では prompt 実行中に expert arena 内の領域を使います。

`docs/MAC.md` は表で既定値を2048と記しますが、ソース上のストリーミング既定値は物理メモリによって1024または4096です。同ドキュメント本文には大容量ストリーミング Mac の4096と、小容量機の1024の説明もあります。本文にある M5 Max / UD-Q5 の測定値（4K promptで1024行=700、2048行=920、4096行=1100 tok/s、32Kでも同じ）は文書記載値であり、ここでは再測定していません。

## 根拠

- `metal/src/engine/prompt_chain.inc:394-415` — 常駐 prompt chain の `atoi`、64〜8192の clamp、chunk loop。
- `metal/src/engine/window.cpp:2019-2034` — ストリーミングを含む prompt GEMM 初期化、96 GiB 判定、既定行数、64行単位への切り下げ。
- `metal/src/engine/window.cpp:2093-2105` — streaming arena region の確保と stderr の初期化ログ。
- `metal/src/engine/window.cpp:1194-1209` — streaming arena 初期化前の `STRATA_METAL_PROMPT_GEMM` 判定と prompt GEMM 初期化。
- `metal/src/engine/window.cpp:2545-2587` — `STRATA_METAL_PROMPT=window`、prompt 長と prompt GEMM 設定に基づく経路選択、および window fallback。
- `docs/MAC.md:110,183-190` — ストリーミング時の既定値・測定値と環境変数表。
