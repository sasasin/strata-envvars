# `STRATA_QSA_FUSE_GATE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

QSA 層の prompt prefill で、attention の出力 `O` と gate `sigmoid(gate)` の乗算を、対応する matrix-core attention kernel の epilogue にまとめます。融合経路では attention の中間出力を書き出さず、FP16 の gated 出力を直接作ります。変数が既定で ON でも、融合 kernel がその backend・GPU・KV 形式で使える場合に限って実際に選択されます。

## 値と判定

`src/prefill/prefill.cpp:559-562` の `qsa_fuse_gate()` は `std::getenv()` の結果を先頭文字だけで判定し、結果を関数内の `static const bool` に保存します。

| 環境値 | 判定 |
|---|---|
| 未設定 | ON |
| 空文字 | ON（変数は設定済みだが、先頭文字は `\0`） |
| 先頭文字が `0` | OFF（例: `0`, `0anything`） |
| その他 | ON（例: `1`, `true`, `false`, `anything`, 空白で始まる値） |

文字列全体、数値としての妥当性、大文字小文字、空白は検査されません。したがって `false` も ON です。環境をプロセス中に変更しても、`qsa_fuse_gate()` が最初に評価された後は反映されません。QSA prefill の呼び出し条件により関数が呼ばれない場合は、この変数もまだ評価されません。

## 有効になる条件

prefill の QSA attention で、次の条件がすべて成立する必要があります。

- `STRATA_PROMPT_ATTN_OLD` が未設定である（値が空でも設定されていれば旧経路を選ぶ）。
- `st.kv_rot` と `st.kv_hybrid` がどちらも false。これらの状態では attention 出力を回転してから gate を適用するため、融合経路を使いません。
- `STRATA_QSA_FUSE_GATE` の判定が ON。
- `qsa_prompt_attn_batch_gated()` が現在のビルド・GPU・データ形式を受け付ける。

融合 kernel の実装は `__HIPCC__` かつ `STRATA_HIP_GFX906` ではないビルドに限られます。CUDA ビルド、gfx906 互換 HIP ビルド、Metal では関数が false を返すため、環境値が ON でも融合されません（`src/kernels/cuda/qsa_prompt_attn.cu:2445-2457`、Metal stub は `metal/src/engine/stubs_0291.cpp:14-19`）。通常の HIP 実装でも、クエリ数が正、必要なポインタと page table が存在、通常の量子化 KV pool（`k_q` / `v_q` と scale があり、Q4 pool ではない）、head dimension が `HD`、head 数が `G * n_head_kv`、capacity が正であることが必要です。

さらに `hip_wmma_usable()` が true である必要があります。対応 GPU は gfx11 または gfx12 の matrix-core 対応機種です。`STRATA_HIP_WMMA=0`、未対応 GPU、または以前の WMMA launch failure があると false になります。gfx12 は Linux で既定有効、Windows では既定無効です。`STRATA_HIP_WMMA=1` は gfx11 / gfx12 で有効化し、`auto` は gfx12 で query 数と capacity の条件に従います（`src/kernels/cuda/qsa_prompt_attn.cu:2241-2295`、`include/strata/core/gfx12_platform_defaults.hpp:10-16`）。

## 実行時の詳細

prefill の通常経路と別の staged 経路の両方で同じ条件判定と gated kernel 呼び出しを行います（`src/prefill/prefill.cpp:4387-4391,7515-7518`）。呼び出しが成功すると attention epilogue が `O * sigmoid(gate)` を FP16 へ丸めて `attn_h` に書き込み、その後の `attn_output` projection に渡します（`src/kernels/cuda/qsa_prompt_attn.cu:2207-2218`）。この経路では後続の独立した `gate_attn()` は実行されません。

判定が OFF、条件不成立、または gated kernel が false を返した場合は通常経路へ戻ります。通常の prompt attention が使えない場合は、条件により PATTN 経路を試し、それも使えない場合は decode attention に進みます。最後に独立した `gate_attn()` で gate を適用します。`STRATA_PROMPT_ATTN_OLD` が設定されていれば旧 attention 経路を使います（`src/prefill/prefill.cpp:4400-4420,7519-7529`）。gated kernel が false を返しただけで終了や警告にはなりません。

通常の prefill 経路では、最初の該当箇所で stderr に一度、`strata prefill: QSA layers: norm + rope in one pass %s, attention gate in the attention epilogue %s` を出し、実際に gated kernel が受理されたかを `on` / `off` で示します（`src/prefill/prefill.cpp:4393-4398`）。staged 経路には同じ状態ログがありません。WMMA kernel の launch error は `qsa_prompt_attn_batch (wmma): %s; the FP32 prompt attention runs from here on` と stderr に出し、以後 WMMA を無効にします（`src/kernels/cuda/qsa_prompt_attn.cu:2365-2370`）。

## 根拠

- 値の読み取り、既定値、cache: `src/prefill/prefill.cpp:559-562`
- 通常 prefill の判定、状態ログ、通常経路への fallback: `src/prefill/prefill.cpp:4383-4420`
- staged prefill の判定と fallback: `src/prefill/prefill.cpp:7514-7529`
- HIP gated kernel のビルド条件と引数・pool 条件: `src/kernels/cuda/qsa_prompt_attn.cu:2445-2457`
- matrix-core の GPU / mode 条件と launch 失敗状態: `src/kernels/cuda/qsa_prompt_attn.cu:2241-2295,2365-2370`
- epilogue の gate 計算と出力: `src/kernels/cuda/qsa_prompt_attn.cu:2207-2218`
- gfx12 の platform default: `include/strata/core/gfx12_platform_defaults.hpp:10-16`
- Metal の未実装 stub: `metal/src/engine/stubs_0291.cpp:14-19`
