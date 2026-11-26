# `STRATA_QSA_FUSE_GATE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA の prompt attention 出力に適用する `sigmoid(gate) * attention` を、attention 行列コア kernel の epilogue に融合するかを選ぶ。既定では融合を許可し、無効にすると attention の結果を別途 `gate_attn` に渡す。融合経路は attention 結果を FP16 の投影入力へ直接書き、通常の attention 出力バッファと後段の gate kernel を使わない。適用箇所は `prefill.cpp` の二つの QSA prompt 処理経路である（`engine/src/prefill/prefill.cpp:1019-1025,5536-5574,9461-9477`）。

## 値と判定

`qsa_fuse_gate()` は `std::getenv` で値を取得し、設定値の先頭文字が `'0'` のときだけ `false` を返す。それ以外は `true`。整数や真偽値としての parse、文字列全体の比較はしない（`engine/src/prefill/prefill.cpp:1022-1025`）。

| ビルド | unset | 設定時に融合許可 | 設定時に融合を無効化 |
|---|---|---|---|
| 全ビルド（値判定） | 既定で許可 | 空文字を含む、先頭文字が `0` でない文字列（例: `1`、`true`、`false`、` 0`） | `0`、`0anything` など先頭文字が `0` の文字列 |

大文字小文字・空白・数値の妥当性は検査しない。たとえば `false` は先頭が `f` なので融合を許可し、先頭に空白がある ` 0` も許可する。空文字も設定ありの無効値ではなく、未設定時と同じく許可となる（`engine/src/prefill/prefill.cpp:1023`）。

## 有効になる条件

- QSA 層を含むモデルの prompt prefill 経路であること。値は生成時の decode attention の分岐には使われない（`engine/src/prefill/prefill.cpp:5533-5574,9459-9477`）。
- 呼び出し元が `STRATA_PROMPT_ATTN_OLD` を設定していないこと。この変数は値の内容ではなく設定有無で旧経路を選び、融合経路を飛ばす（`engine/src/prefill/prefill.cpp:5540-5544,9462-9465`）。
- KV が `kv_rot` / `kv_hybrid` でないこと。これらでは gate 融合を呼ばず、attention 後に必要な逆変換をしてから別の `gate_attn` を実行する（`engine/src/prefill/prefill.cpp:5542-5544,5571-5573,9463-9465,9474-9476`）。
- 実際の gated kernel は HIP ビルドかつ `STRATA_HIP_GFX906` ではない場合に限り実装される。CUDA 側と gfx906 build では関数が `false` を返すため、環境変数が融合許可でも融合しない（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2456-2469`）。
- HIP 側では matrix-core prompt attention が使えること。対象 device は gfx11 / gfx12 matrix-core device で、attention pool が INT8 K/V（`k_q`, `v_q`, scale があり、Q4 pool がない）、QSA geometry が 24 query heads / 2 KV heads / head dimension 256、selection / page table が有効である必要がある（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2459-2464,2286-2296`）。
- matrix-core の選択は `STRATA_HIP_WMMA` にも依存する。`0` など先頭文字が `1` でもなく `auto` 全体でもない値は off、`1` は gfx11 / gfx12 で有効化、`auto` は gfx12 のみで `STRATA_HIP_WMMA_MIN_Q` と `STRATA_HIP_WMMA_MIN_CAP` の閾値を満たす場合に有効。未設定時は gfx12 のみ `kGfx12PromptDefaultsOn` に従い、これは Linux で on、Windows で off（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2242-2249,2280-2296`; `engine/include/strata/core/gfx12_platform_defaults.hpp:10-16`）。
- matrix-core kernel が失敗していないこと。失敗後は process 内で WMMA を無効化し、gated 呼び出しは `false` となる（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2252,2286-2295,2438-2440,2459-2468`）。

## 実行時の詳細

環境値は `qsa_fuse_gate()` 内の関数ローカル `static const bool` で初回評価時に一度読み、その後の prefill 呼び出しでは cache 値を使う。実行中に環境を変更しても反映されない（`engine/src/prefill/prefill.cpp:1022-1025`）。

二つの QSA prefill 経路は、旧 attention でなく、KV rotation / hybrid でなく、このスイッチが許可し、さらに `qsa_prompt_attn_batch_gated()` が受理した場合に融合を実行する。kernel は各 query/head/dimension について正規化済み attention 値に `1 / (1 + expf(-gate))` を掛け、FP16 へ丸めて `attn_h` に書く。融合しない場合は通常の prompt attention（使えなければ decode attention）を実行し、別の `gate_attn` kernel が同じ gate 式で FP16 投影入力を作る（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2211-2218,2456-2469`; `engine/src/prefill/kernels.cu:2588-2594,3584-3587`; `engine/src/prefill/prefill.cpp:5542-5574,9463-9477`）。

融合 kernel が geometry / pool / device 条件を満たさないときは `false` を返し、呼び出し元は別経路に進む。通常 prompt attention も使えない場合は `qsa_decode_attn_batch` を使う（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2459-2469`; `engine/src/prefill/prefill.cpp:5556-5569,9466-9472`）。

## ログと測定値

一方の経路では最初の QSA attention chunk で一度、stderr に `strata prefill: QSA layers: norm + rope in one pass %s, attention gate in the attention epilogue %s` を出す。末尾の `on` / `off` は環境値の判定だけではなく、gated kernel が実際に受理されたかを示す（`engine/src/prefill/prefill.cpp:5546-5551`）。もう一方の経路 (`9461-9477`) には gated の成否を示す同様のログはない。

WMMA launch error 時は stderr に `qsa_prompt_attn_batch (wmma): %s; the FP32 prompt attention runs from here on` を出し、その後の gated 呼び出しは失敗扱いとなり fallback する（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2366-2371,2456-2468`）。この変数について `docs/DETAILS.md` に測定値は見つからず、本調査でも性能測定は行っていない。

## 根拠

- 値の読み取りと cache: `engine/src/prefill/prefill.cpp:1022-1025`
- host 側の条件、fallback、実行ログ: `engine/src/prefill/prefill.cpp:5540-5574,9462-9477`
- gated kernel のビルド / 引数条件: `engine/src/kernels/cuda/qsa_prompt_attn.cu:2456-2469`
- HIP matrix-core 条件と環境変数: `engine/src/kernels/cuda/qsa_prompt_attn.cu:2242-2296`
- gate の epilogue と別 kernel: `engine/src/kernels/cuda/qsa_prompt_attn.cu:2211-2218`; `engine/src/prefill/kernels.cu:2588-2594`
- gfx12 default の OS 条件: `engine/include/strata/core/gfx12_platform_defaults.hpp:10-16`
