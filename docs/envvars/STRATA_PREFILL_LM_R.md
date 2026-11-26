# `STRATA_PREFILL_LM_R`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

layer-major prefill が使う super-chunk の残差行 `R` を VRAM に置くか、pinned host memory に置くかを選ぶ。`vram` は super-chunk の残差行を device buffer に含め、`host` は pinned host 上に確保し、各 sub-chunk / layer の処理でコピーする配置を選ぶ。どちらも残差行以外の layer-major 用バッファや VRAM の空き要件は残る。変数は layer-major prefill 自体を有効にしない。layer-major 経路に入ったときだけ `lm_prepare()` の配置選択に使われる。`engine/src/prefill/prefill.cpp:8076-8080, 8102-8109, 8263-8327`。

## 値と判定

`lm_r_env()` が初回呼び出し時に `std::getenv` で読み、関数内 `static const int` に保存する。値全体を `std::string` として大文字小文字を区別して比較し、完全一致の `vram` を VRAM 指定、完全一致の `host` を pinned host 指定、それ以外を自動選択 (`0`) とする。数値変換や trim はしない。未設定は `0`。空文字は設定済みだが空文字列はどちらにも一致せず `0` になる。したがって `VRAM`、`host `、`1`、`0`、`true`、`false`、`0anything` もすべて自動選択に合流する。`engine/src/prefill/prefill.cpp:8102-8109`。

| 条件 | unset | 設定時に有効になる値 | 設定時に自動選択となる値 |
|---|---|---|---|
| 通常の layer-major stage (`stage_lb_ == 0`) | 自動選択 | `vram` / `host`（完全一致） | 空文字、`VRAM`、`host `、`1`、`0`、`true`、その他すべて |
| layer split の後段 (`stage_lb_ > 0`) | この変数を参照せず pinned host | 該当なし | 該当なし |

自動選択は、要求した super-chunk 全体が VRAM の空き領域と確保マージン内に収まる場合に限り VRAM を選び、そうでなければ pinned host 配置で収まる最大の super-chunk を探す。明示的な `vram` は `fit(true)`、明示的な `host` は `fit(false)` を使う。`engine/src/prefill/prefill.cpp:8254-8272`。

## 有効になる条件

- 呼び出し元で layer-major prefill が選ばれている必要がある。`STRATA_PREFILL_LAYER_MAJOR` が未設定なら現行既定は off。明示的な `STRATA_PREFILL_LAYER_MAJOR` や小容量 cache 向けの設定経路などで layer-major が選択された場合にのみ、この変数の値が使われる。`engine/src/prefill/prefill.cpp:9657-9662`; `engine/include/strata/core/sm120_series.hpp:176-191, 211-218`。
- AMD HIP build では `STRATA_LM_HIP` の初回値が先頭文字 `'1'` でなければ layer-major 準備が断られ、この変数による配置選択にも到達しない。CUDA build ではこの HIP opt-in 判定はない。`engine/src/prefill/prefill.cpp:8166-8179`。
- image prompt、peer GPU / helper、KVA 有効、chunk 境界で yield する batch read、`--prefill-pipe` による chunk 指定、ビルド済み nibble expert の使用、対応しない expert layout / 不足するバッファなどでは layer-major 準備が断られる。これらはこの変数の有効値より優先され、chunk-major 経路へ戻る。`engine/src/prefill/prefill.cpp:8180-8234`。
- layer split の後段 (`stage_lb_ > 0`) は前段から `R_host` で受け取るため、設定値によらず pinned host 配置を使う。layer split の stage 間で共通の super-chunk が作れない場合も準備失敗となる。`engine/src/prefill/prefill.cpp:8181-8187, 8263-8269, 8354-8393`。
- 明示的 `vram` で必要な super-chunk が VRAM に収まらない場合は host へ自動 fallback せず、layer-major 準備が失敗する。pinned host 配置でも残りの device buffer と margin が必要で、pinned RAM 不足や最終 `cudaMalloc` 失敗でも準備は失敗する。自動選択では全 target が VRAM に収まらない場合に host 側の fit を試す。`engine/src/prefill/prefill.cpp:8254-8285, 8299-8312`。

## 実行時の詳細

環境変数はプロセス起動時に必ず読むのではなく、layer-major 準備が配置モードを必要としたときの `lm_r_env()` 初回呼び出しで読み、`static` に保持する。同一プロセス内でその後環境を変更しても、この判定値は更新されない。layer-major 経路が選ばれない実行では、この getter は呼ばれない。`engine/src/prefill/prefill.cpp:8102-8109, 8263-8269`。

自動選択は `cudaMemGetInfo()` で得た空き容量から、既定または `STRATA_PREFILL_LM_MARGIN_MIB` のマージンを差し引いて、chunk 単位で super-chunk のサイズを試す。VRAM 配置では残差行領域 `R` を device buffer に置く。host 配置では `R_host` を pinned host memory に確保し、device 側には sub-chunk 分の `R2` を置く。layer split の後段は前段の pinned host 行を使う。`engine/src/prefill/prefill.cpp:8245-8272, 8287-8327`。

配置準備が失敗すると `lm_prepare_chain()` は理由を返し、呼び出し側は `strata prefill: layer-major off for this prompt: <理由>` を stderr に出して通常の `run_impl()` に進む。短い prompt は既定経路ではこの理由ログを抑制する。準備成功後の layer-major 実行自体が失敗した場合は `run_layer_major()` のエラーを返すため、通常経路への fallback ではない。`engine/src/prefill/prefill.cpp:8354-8393, 9677-9705`。

## ログと測定値

layer-major が実行されると stderr に `strata prefill: layer-major (layers ...): ... (R in VRAM, ... MiB VRAM free before), ...` または `R in pinned RAM` を含む実績行が出る。準備失敗時の理由ログと、既定の短い prompt で理由ログを抑制する条件は前節のとおり。`STRATA_PREFILL_LM_R` 単独の性能測定値は、確認したソースおよび関連設計コメントに記載がない。`engine/src/prefill/prefill.cpp:9566-9574, 9694-9702`。

## 根拠

- `engine/src/prefill/prefill.cpp:8102-8109` — 環境変数の唯一の読み取り箇所、値の厳密比較、static cache。
- `engine/src/prefill/prefill.cpp:8166-8234` — layer-major の backend gate と、この変数より前に判定される非対応条件。
- `engine/src/prefill/prefill.cpp:8254-8327` — 配置モード、VRAM fit / host fallback、バッファ配置と失敗条件。
- `engine/src/prefill/prefill.cpp:8354-8393, 9657-9705` — 準備の呼び出し、理由ログ、chunk-major fallback。
- `engine/src/prefill/prefill.cpp:9566-9574` — 実行時に出る配置の観測ログ。
- `engine/include/strata/core/sm120_series.hpp:176-191, 211-218` — layer-major の既定・明示値解決と、小容量 cache 向けに layer-major を選ぶ条件。
