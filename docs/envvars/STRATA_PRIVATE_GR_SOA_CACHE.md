# `STRATA_PRIVATE_GR_SOA_CACHE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の B60 private decode layout で、GR の `down` / `up` BF16 重み用に row-major 元データとは別の SoA 配置 cache を作り、GR の down / up ESIMD 経路から使う実験用スイッチである。通常の計算式を別の GR 制御経路へ切り替えるが、Strata のソースだけから token 出力の同一性や性能差は断定できない。読み取りは `gr_soa_enabled()`、cache の登録は `b60_cache_requested(30)`、作成は `b60_make_weight_cache()` が行う。【`sycl/src/kernels/cuda/fused_gr.dp.cpp:2969-2969`, `sycl/include/b60_weight_cache.hpp:5-8`, `sycl/include/b60_layout_host.hpp:88-93`, `sycl/src/kernels/cuda/weight_permute.dp.cpp:136-169`】

候補一覧ではなく実装上の環境変数であり、実際の `getenv` は SYCL の `sycl/src/kernels/cuda/fused_gr.dp.cpp` にある。ほかに `b60_weight_cache.hpp` の kind 30 名選択と `data/settings-register.json` の登録があるが、後者は設定 metadata で、追加の読み取り箇所ではない。【`sycl/src/kernels/cuda/fused_gr.dp.cpp:2969-2969`, `sycl/include/b60_weight_cache.hpp:5-8`, `data/settings-register.json:31056-31061`】

## 値と判定

`gr_soa_enabled()` は初回呼び出し時に `std::getenv` し、環境変数が存在し、かつ先頭文字が ASCII `'1'` のときだけ値判定を true とする。その後 `b60_main_actor()` も要求する。文字列全体の比較・数値変換・範囲検査はしないため、空文字は無効、`1`・`10`・`1anything` は値判定上有効、`0`・`true`・` 1`・`01`・`2` は無効。大文字小文字の概念は適用されない。`static const bool` に保存されるので、初回評価後に環境を変更してもこのプロセス内では再評価されない。【`sycl/src/kernels/cuda/fused_gr.dp.cpp:2969-2969`】

ただし、値判定が true でも main actor でなければ機能判定は false になる。main actor は B60 layout または single-actor scope が有効な処理中に設定される。【`sycl/src/kernels/cuda/fused_gr.dp.cpp:2969-2969`, `sycl/include/b60_layout_state.hpp:14-20`】

| 条件 | unset | 値判定が有効 | 値判定が無効 |
|---|---|---|---|
| SYCL `fused_gr.dp.cpp` の `gr_soa_enabled()` | false | 先頭文字が `'1'`（例: `1`, `10`, `1anything`） | 空文字、`0`, `true`, ` 1`, `01`, `2` |
| 値判定後の機能判定 | main actor でなければ false | 値判定 true かつ `b60_main_actor()` true | 値判定 false または main actor でない |

## 有効になる条件

- このコードは SYCL 実装の `sycl/src/kernels/cuda/fused_gr.dp.cpp` にある。通常の CUDA `.cu` 実装にはこの名前の参照がなく、他 backend での有効化は確認できない。【`sycl/src/kernels/cuda/fused_gr.dp.cpp:2969-2969`; `src/kernels/cuda/fused_gr.cu` は `rg` で候補名参照なし】
- B60 main actor scope が必要。scope は `STRATA_PRIVATE_B60_DECODE_LAYOUT` または `STRATA_PRIVATE_BMG_SINGLE_ACTOR` の要求時に main actor として動作し、layout 要求時は重みが packed でなければ `B60 main graph recorded while weights are raw` の `logic_error` を投げる。【`sycl/include/b60_layout_state.hpp:7-20`】
- cache 作成は B60 layout 構築時に、この変数の先頭文字判定が有効で、重みが GR の HC projection (`output`、`.hc_attn_`、`.hc_ffn_` 名かつ `down.weight` / `up.weight`) に該当し、`w.data` があり、`WeightKind::Bf16InF32` かつ `w.bytes == w.ne0 * w.ne1 * 2` の場合に限る。対象外なら cache に追加されない。【`sycl/include/b60_layout_host.hpp:81-93`】
- fused read で cache に切り替える箇所は `n_tok` が 1、2、4 のときだけである。その呼び出しには `STRATA_PRIVATE_GR_F32_REG` が `atoi` で非ゼロ、`STRATA_GR_DOWN_SLICED` が未設定または `atoi` で非ゼロ、`STRATA_GR_NORM_SPLIT` が未設定または `atoi` で非ゼロ、`STRATA_GR_MORE_GROUPS` と `STRATA_GR_LARGE_GRF` がそれぞれ明示値なら `atoi` で 0 であること（未設定時は Battlemage ではどちらも既定 false）、`STRATA_GR_UP_COLS` が未設定時の 16 であること（許可値 4/8/32/64 以外も fallback 16）、および `STRATA_GR_UP_ILP` の先頭文字が `1` でないことを要求する。さらに Battlemage、`STRATA_PRIVATE_GR_F32_PHASE` が未設定・`both`・`down` のいずれか、`STRATA_PRIVATE_GR_SILU_FROM_LO` が `atoi` で非ゼロ、`STRATA_PRIVATE_GR_UP_ROWS16` の先頭文字が `1`、`STRATA_PRIVATE_B60_DECODE_LAYOUT` が有効であることも必要。条件が揃わず、この変数自体が有効で `n_tok` が 1/2/4 の場合は `B60 GR cache requires the measured GR control combination` の `logic_error` になる。【`sycl/src/kernels/cuda/fused_gr.dp.cpp:574-576`, `812-837`, `1203-1210`, `2517-2517`, `2529-2532`, `2685-2688`, `2690-2693`, `3160-3162`】
- `n_tok == 3` では cache lookup / 上記 control-combination 検査を通らず、SOA down dispatch の token 数 switch にも該当しないため、この GR SoA dispatch は選ばれない。【`sycl/src/kernels/cuda/fused_gr.dp.cpp:3110-3115`, `3160-3162`】

## 実行時の詳細

B60 layout の構築中、条件に合う GR projection は cache の一覧に加えられ、`b60_make_weight_cache()` が元データを保持したまま別領域へ配置変換する。kind 30 は rows×cols の 16-bit 要素を `dst[(row/16)*16*cw + k*16 + row%16]` に書く。cache 領域の割り当てが失敗すれば `std::bad_alloc`、不正な kind/shape 等なら例外となる。layout の生成経路は単一 actor 用 `prepare_single()` または layout の `add_device()` で cache を準備する。【`sycl/include/b60_layout_host.hpp:32-36`, `69-106`, `111-115`; `sycl/src/kernels/cuda/weight_permute.dp.cpp:136-169`】

`fused_gr_read_multi()` が `gr_soa_enabled()` と token 数条件を満たすと、control 条件を検査した後に kind 30 の down/up cache を引く。どちらかが見つからなければ `B60 missing GR decode cache` の `logic_error`。見つかった down cache は全 token の `w_down` に設定され、up cache は `n_tok == 4` のときだけ `w_up` に設定される。その後 down dispatch は SoA kernel を選び、token 数 1/2/4 に対応するテンプレートを呼ぶ。up 側は `STRATA_PRIVATE_GR_UP_ROWS16` が有効で `m.T == 4` の場合に SoA compute を使う。【`sycl/src/kernels/cuda/fused_gr.dp.cpp:3103-3118`, `3139-3167`】

GR cache 自体は `gr_soa_enabled()` の `static` 判定とは別に B60 layout 構築時に生成され、その layout の寿命中に保持される。layout の破棄処理は ready な cache を解放する。【`sycl/include/b60_layout_host.hpp:21-23`, `104-107`, `137-137`】

## ログと測定値

この変数専用の有効・無効ログは確認できない。B60 layout の cache 準備では一般ログ `B60_CACHE device=%d matrices=%zu cumulative_bytes=%llu` が stderr に出る。GR cache を含む条件で VRAM reserve を下回る場合は `B60_CACHE_RESERVE device=%d free_bytes=%zu minimum_bytes=%zu` を出した後、`B60 decode cache would consume the configured VRAM reserve` の runtime error を投げる。cache 条件違反と欠落時の例外文言は上記「有効になる条件」「実行時の詳細」のとおり。【`sycl/include/b60_layout_host.hpp:58-63`, `104-107`; `sycl/src/kernels/cuda/fused_gr.dp.cpp:3161-3165`】

この変数の cache 経路について、条件付き性能測定値を示す Strata 資料は確認できなかった。

## 根拠

- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2969-2969` — 値の読み取り、static cache、main actor 条件。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:3103-3118`, `3160-3167` — down/up dispatch、適用条件、cache lookup と失敗。
- `sycl/include/b60_layout_host.hpp:81-107` — cache 対象と作成時の条件。
- `sycl/src/kernels/cuda/weight_permute.dp.cpp:136-169` — kind 30 SoA cache の shape 検査、割当てと配置変換。
- `sycl/include/b60_layout_state.hpp:7-20` — B60 layout / single actor scope。
- `data/settings-register.json:31056-31061` — SYCL backend と metadata 上の候補登録。
