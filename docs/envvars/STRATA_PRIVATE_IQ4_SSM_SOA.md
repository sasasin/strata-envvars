# `STRATA_PRIVATE_IQ4_SSM_SOA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL 実装の private B60 weight cache で kind 23（IQ4 SSM）のキャッシュを要求し、対応条件を満たす Battlemage の native IQ4 MMVQ decode でそのキャッシュを使う。値を有効にしても cache layout 自体は有効化されず、別の `STRATA_PRIVATE_B60_DECODE_LAYOUT` が layout の準備を有効にする。読み取りと dispatch は `engine/sycl/include/b60_weight_cache.hpp` および `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp` にある。（`engine/sycl/include/b60_weight_cache.hpp:5-8`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3706`）

## 値と判定

`b60_cache_requested(kind)` は kind 23 のときこの名前を選び、`std::getenv` の戻り値が null でなく、かつ先頭文字 `p[0]` が文字 `'1'` の場合だけ true を返す。文字列全体の比較や数値変換はしない。未設定と空文字は false。`1`, `10`, `1anything` は true、`0`, `true`, ` 1`, `01` は false。大文字小文字は先頭文字判定に該当せず、空白除去もない。（`engine/sycl/include/b60_weight_cache.hpp:5-8`）

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL の B60 cache helper、kind 23 | false | 先頭が `1`（`1`, `10`, `1anything`） | 空文字、`0`, `true`, ` 1`, `01` |

既定値は cache 要求なし。値が false の場合、layout 準備時に kind 23 の SSM cache は登録されず、該当する cache decode 分岐にも入らない。（`engine/sycl/include/b60_layout_host.hpp:81-87`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3707`）

## 有効になる条件

- この読み取り経路は Strata の SYCL 実装にある。CUDA/HIP 実装で同じ環境変数を読む箇所は見つからなかった。（候補名の全参照は `engine/sycl/include/b60_weight_cache.hpp:6` のみ。）
- layout 構築時に `STRATA_PRIVATE_B60_DECODE_LAYOUT` が先頭文字 `1` であること。非 single-actor 経路では、さらに native pack、2-stage pipeline、`--serve`、prefill borrow 無効、batch なし、prompt cache なし、`spec <= 6`、48 layers / 512 experts / 2560 embedding / 640 FFN / hc 4 / hc_lr 320、および `STRATA_PRIVATE_PACKED_REGISTER` の先頭文字 `1` が必要。条件不足は `invalid_argument` で失敗する。（`engine/sycl/include/b60_layout_state.hpp:7-9`、`engine/sycl/src/program/generate.cpp:8035-8046`）
- single-actor layout 経路でも layout 要求が必要であり、`generate` が固定 single-device no-host decode 条件を検査する。この条件には `--serve`、native pack、single GPU、no-prefill-borrow、batch なし、prompt cache なし、speculation 上限、モデル geometry、`STRATA_VERIFY_NO_HOST=1`、`STRATA_VERIFY_DEVICE_PLAN=1`、`STRATA_PRIVATE_PACKED_REGISTER=1` などが含まれる。（`engine/sycl/src/program/generate.cpp:4590-4597`）
- cache 対象は選択された層の `native_type == 23` かつ `native_data != nullptr`、`ne0 == 2560`、`ne1` が `6144` または `12288` の WeightTable entry。各 device の layout 準備時に環境値を検査し、該当 entry を見つけたときだけ kind 23 cache を追加する。（`engine/sycl/include/b60_layout_host.hpp:81-87`）
- cache を使う decode 分岐には、環境値が有効であることに加えて `b60_main_actor()`、weight layout が packed 状態、`n_in == 2560`、`n_out` が `6144` または `12288`、`ncols` が `1`, `2`, `4` のいずれか、実行 device の世代が Battlemage であることが必要。満たさない場合はこの分岐を通らず、後続の通常経路判定へ進む。（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3735`）

## 実行時の詳細

layout 準備時、選択済み WeightTable の native IQ4 SSM 重みに kind 23 cache を追加し、`b60_make_weight_cache` が検証後に device allocation を作成して raw IQ4 byte を packed layout に並べ替え、queue を待って cache map に登録する。cache map は元ポインタと kind をキーに保持され、layout の破棄時に解放される。（`engine/sycl/include/b60_layout_host.hpp:32-36,81-87,104-107,137`、`engine/sycl/src/kernels/cuda/weight_permute.dp.cpp:131-173`）

`b60_cache_requested` 自体には `static` cache がなく、layout 構築時と native MMVQ 呼び出し時に都度 `getenv` を行う。対して layout 有効化用の `b60_layout_requested()` は関数内 `static` に一度だけ保存される。通常の外部プロセス環境変更は起動済みプロセスには反映されない。プログラム内で環境値が変わり、cache 準備後にこの変数だけを true にした場合、他の dispatch 条件も成立すると cache lookup が失敗し、`B60 missing SSM IQ4 decode cache` の `logic_error` を投げる。（`engine/sycl/include/b60_weight_cache.hpp:5-8`、`engine/sycl/include/b60_layout_state.hpp:7`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3706`）

該当 decode 分岐では `b60_iq4_ssm_soa_probe(true, cached, ...)` を呼び、成功するとその場で return する。値を無効にした場合や形状・GPU・actor・packed 条件が不一致の場合はこの cache kernel は選ばれず、後続の通常 dispatch を行う。（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3701-3735`）

## ログと測定値

この環境変数の設定値や有効・無効を直接示すログはない。cache 作成時は stderr に `B60_CACHE device=%d matrices=%zu cumulative_bytes=%llu`、packed layout の切替時は `B60_LAYOUT phase=%s matrices=%llu payload_bytes=%llu metadata_bytes=%llu wall_ms=%.6f` が出る。（`engine/sycl/include/b60_layout_host.hpp:104-107,126-135`）

cache 作成では未対応 geometry/kind、ordered queue でない場合に `invalid_argument`、allocation 失敗時に `std::bad_alloc`、kernel 実行時エラーは `q.wait_and_throw()` 経由で失敗し得る。Battlemage の cache dispatch 条件を満たす一方で lookup が空なら `B60 missing SSM IQ4 decode cache` の `logic_error` となる。変数固有の測定値は確認できなかった。（`engine/sycl/src/kernels/cuda/weight_permute.dp.cpp:136-173`、`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3704-3706`）

## 根拠

- `engine/sycl/include/b60_weight_cache.hpp:5-8` — kind と環境変数名の対応、値判定。
- `engine/sycl/include/b60_layout_host.hpp:81-107,126-137` — cache 対象の選別、作成、ログ、解放。
- `engine/sycl/src/kernels/cuda/weight_permute.dp.cpp:131-183` — cache lookup、shape 検査、device cache 生成・解放。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3692-3707` — IQ4 MMVQ の入力検査、適用条件、fallback 順序、missing-cache エラー。
- `engine/sycl/include/b60_layout_state.hpp:7-20`、`engine/sycl/src/program/generate.cpp:4590-4597,8035-8046` — layout の環境値 cache、生成時の有効条件。
