# `FNX_PF_DMA_CHECK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

split engine の prompt 処理で、copy engine がホスト上の ring slot から device buffer へ DMA した値を、直後の device kernel がホスト側の現在値と比較する診断用スイッチです。値が非 0 なら `PfRing::dma_check` が有効になります。生成計算や ring の転送方式自体を選ぶ設定ではなく、比較は `FNX_PF_DMA` で DMA が有効な場合に限って一部の受信・gather 経路で追加されます。読み取りと状態設定は `Engine::prefill_alloc()` 内です（`engine/src/split/src/prefill.cu:301-314,1169-1223`）。

## 値と判定

`fnx::env_int("FNX_PF_DMA_CHECK", 0)` が共通 helper 経由で読みます。helper は `getenv` で未設定を判定し、設定値全体を符号付き base-10 `long long` として厳密に parse します。未設定は `0`、parse 後の値が `0` なら無効、それ以外（負値を含む）は有効です。範囲外の整数、空文字、空白、`true`、`0anything` など全体が整数でない値は `std::runtime_error` になります。`+1` や `-1` は有効な整数で、値の clamp はありません（`engine/src/split/src/env.hpp:15-22,33-40,51-52`; 呼び出し `engine/src/split/src/prefill.cu:1216`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| split engine の prompt ring 設定 | `0`（無効） | parse 可能な非 0 整数。例: `1`, `-1`, `+2` | `0`, `-0`, `00`。空文字・`true`・`0anything`・空白つきの値・整数範囲外は無効扱いに落ちず、helper の例外になる |

## 有効になる条件

- CUDA/HIP 共通の split engine prompt 実装で読みます。調査した checkout では名前の実読み取りは `prefill.cu` の一箇所のみで、Metal/SYCL 等に同名の読み取りはありません（`engine/src/split/src/prefill.cu:1211-1216`）。
- `FNX_PF_DMA` が非 0 で ring が DMA 経路を使う必要があります。`FNX_PF_DMA` 未設定時は HIP build で `0`、HIP 以外で `1` です。DMA が無効なら `dma_check` が true でも比較 kernel は起動しません（`engine/src/split/src/prefill.cu:1209-1216`; 判定箇所 `engine/src/split/src/pf_common.cuh:328-335,354-360,383-396`）。
- prompt の加算が copy-engine ring (`pf_ring_run`) を通る必要があります。`FNX_PF_RING_SM` による SM ring は呼び出し側で別経路です（`engine/src/split/src/prefill.cu:1694-1699,1762-1769`）。HIP で RCCL を使う場合は `pf_ring()` が RCCL の all-reduce 経路から先に return し、また `FNX_PF_A2A_ROWS` の範囲内の小 chunk は all-to-all 経路から return するため、いずれもこの checker を通りません（`engine/src/split/src/prefill.cu:723-755,1000-1009`）。
- 比較はすべての copy に適用されるわけではありません。`pf_ring_run()` の通常 `ADD`/`GADD` 受信 DMA と `OUT` gather DMA の後で実行されます。`SEND`/`PASS` 転送および `own_out` reduce-scatter 分岐内の DMA には検査呼び出しがありません（`engine/src/split/src/pf_common.cuh:298-317,325-397`）。
- CLI 引数や設定ファイルによる優先順位はなく、`FNX_PF_DMA_CHECK` の値だけで `dma_check` を決めます。DMA の有効・無効は別変数 `FNX_PF_DMA` が決めます（`engine/src/split/src/prefill.cu:1209-1216`）。

## 実行時の詳細

`Engine::prefill_alloc()` のカードごとの初期化ループで各カードの `PfRing` に対して読みます。読み取り値を `r.dma_check` に保持し、その後の各 prompt ring 呼び出しがその状態を参照します。関数内 `static` やリクエストごとの再読込ではありません。engine の prompt buffer を作成した後に環境を変更しても、既存 `PfRing` の値は変わりません。split engine の構築時に prompt buffer を割り当てる呼び出しは `engine.cu` にあります（`engine/src/split/src/prefill.cu:854-856,1169-1216`; `engine/src/split/src/engine.cu:317-318`）。

checker kernel は転送先 `dev` の各 `uint4` と、転送元 host slot を読み直した 4 個の `unsigned` を比較します。不一致を見つけた block は error word に receive 用 `64` または gather 用 `128` を `atomicOr` します（`engine/src/split/src/pf_common.cuh:222-238`）。prompt pass 後に engine は error word を回収し、非 0 なら `prefill: ring error <数値>` という例外を投げます（`engine/src/split/src/prefill.cu:1786-1803`）。このエラー word には他の ring 検査の bit も入り得るため、数値が 64/128 だけとは限りません。

## ログと測定値

checker 自身は不一致の詳細やカード番号を出力せず、error bit を立てます（kernel の `card` と `rows0` 引数は未使用: `engine/src/split/src/pf_common.cuh:224-238`）。このため観測できる結果は pass 後の `prefill: ring error <数値>` 例外です。`fnx_run` は stderr に `fnx_run: <例外内容>` を出して終了コード 1 になります（`engine/src/split/tools/fnx_run.cpp:1364-1373`）。`sfnx` では初期化・実行時例外を `fail()` が `ERR <理由>` の応答行と `sfnx: failed: <理由>` の stderr に出し、終了コード 1 で終了します（`engine/src/split/tools/sfnx.cpp:1094-1102,1123-1136,1160-1166`）。

`docs/SPLIT_ENGINE.md` は prompt 用 copy-engine ring の概要を説明していますが、この環境変数の比較結果に関する測定条件・数値は記載していません（`docs/SPLIT_ENGINE.md:90`）。現行ソースにも測定値はありません。

## 根拠

- `engine/src/split/src/env.hpp:15-22,33-40,51-52` — 整数の全体 parse、未設定時 fallback、非 0 判定。
- `engine/src/split/src/prefill.cu:301-314,1169-1223` — ring 状態、DMA の backend 別既定値、対象変数の読み取りと初期化。
- `engine/src/split/src/prefill.cu:723-755,1519-1526,1694-1699,1762-1769` — copy-engine ring 呼び出し、RCCL / HIP all-to-all の早期 return、prompt 経路。
- `engine/src/split/src/pf_common.cuh:222-238,298-399` — 比較内容、error bit、checker を実行する DMA 箇所と迂回箇所。
- `engine/src/split/src/prefill.cu:1786-1803` — pass 同期後の error word 回収と例外。
- `engine/src/split/tools/fnx_run.cpp:1364-1373`; `engine/src/split/tools/sfnx.cpp:1094-1102,1123-1136,1160-1166` — CLI / server 側で確認できる失敗表示。
