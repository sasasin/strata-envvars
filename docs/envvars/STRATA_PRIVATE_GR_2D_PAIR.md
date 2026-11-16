# `STRATA_PRIVATE_GR_2D_PAIR`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL 版の fused GR（hyper-connection read）で、Battlemage の main actor が実行する FP32-register 経路の down projection と、条件を満たす up projection に 2-D pair 実装を選ばせる private opt-in である。値を有効にしても、この変数だけで FP32-register 経路や fused GR は有効にならない。対象コードは `sycl/src/kernels/cuda/fused_gr.dp.cpp` にあり、通常の CUDA/HIP ソースにはこの変数の読み取りがない（`sycl/CMakeLists.txt:38-43`、`sycl/src/kernels/cuda/fused_gr.dp.cpp:2764,3103-3115`）。

## 値と判定

`gr_2d_pair_enabled()` の関数内 `static const bool` 初期化で `std::getenv` を一度呼び、値が存在し、かつ先頭文字 `p[0]` が文字 `'1'` のときだけ設定値を true とする。その後 `b60_main_actor()` も true の場合に有効となる。文字列全体の比較や数値変換はしない（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2764`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `gr_2d_pair_enabled()` が呼ばれる経路 | false | `1`, `10`, `1anything`（先頭が `1`） | 空文字、`0`, `01`, `true`, ` 1`（未設定または先頭が `1` 以外） |

不正値をエラーにしたり、別の値へ変換したりする処理はない。判定結果は最初にこの関数が呼ばれた時点で process 内に cache され、以後の環境変更は反映されない。既定値は off である（同 `:2764`）。

## 有効になる条件

- **SYCL backend の実行であること。** この実装ファイルは SYCL プロジェクトに含まれ、トップレベルでは `STRATA_ENABLE_SYCL` が既定 off。SYCL は CUDA/HIP と同時に構成できない（`CMakeLists.txt:23-32`、`sycl/CMakeLists.txt:38-43`）。
- **fused GR が選ばれること。** 起動時の設定では `o.gr_native_mmvf` が true で、`--no-fused-gr` がなく、GPU stages・layer dump・half dump・stage timing がない場合に fused GR を有効にする（`sycl/src/program/generate.cpp:3140-3150`）。レイヤー側でも fused GR 設定と対応 geometry が必要（`sycl/src/core/layer.cpp:1558-1559`）。
- **Battlemage 用 main actor 区間であること。** 判定 helper は `b60_main_actor()` を要求する。これは thread-local 状態で、`Verifier::record_window()` 内の `B60MainActorScope` が、`STRATA_PRIVATE_B60_DECODE_LAYOUT=1` または `STRATA_PRIVATE_BMG_SINGLE_ACTOR=1`（あるいは既に true の親 scope）であると main actor にする。scope 終了時に以前の状態へ戻る（`sycl/src/core/verify.cpp:940-942`、`sycl/include/b60_layout_state.hpp:7-20`、`sycl/src/kernels/cuda/weight_permute.dp.cpp:103-107`）。
- **FP32-register の fused GR 経路であること。** `STRATA_PRIVATE_GR_F32_REG` が `std::atoi` で 0 以外になり、token 数が 1〜4、down sliced、more-groups でなく、large-GRF でなく、norm split、up cols が 16、up ILP なし、GPU 世代が Battlemage という全条件が必要（`sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2689`）。`gf_phase()` による phase 選択も作用する（同 `:2690-2692`）。
- **2-D down は token 数が 4 のときだけ選択される。** また `STRATA_PRIVATE_GR_SOA_CACHE` が有効な場合は SoA down が先に選ばれ、この変数の 2-D down 分岐には進まない（同 `:3110-3115`）。down 分岐自体は sliced path で more-groups 経路に入らず、FP32-register が有効で phase が down の場合に限られる（同 `:3360-3370`）。
- **2-D up はより狭い条件を持つ。** `STRATA_PRIVATE_GR_UP_ROWS16=1` と `STRATA_PRIVATE_B60_DECODE_LAYOUT=1` が必要で、token 数が 4 のときだけ rows16 実装に入り、その中で SoA が無効ならこの変数が pair 実装を選ぶ。SoA が有効なら SoA 実装が優先される（同 `:2517,3103-3108`）。up phase または combo SiLU 経路からの dispatch でなければ適用されない（同 `:3466-3470`、`:2521-2526`）。

## 実行時の詳細

`fused_gr_read_multi()` は token 数を `m.T` に設定し、fused GR の途中で down/up kernel を dispatch する（`sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3159`）。FP32-register 経路の sliced down では、`gf_dispatch_down()` が SoA を優先し、次に本変数が有効かつ `m.T==4` なら `gf_launch_down_2d<4>` を起動する。それ以外は通常の sliced down kernel を使う（同 `:3110-3115,3365-3370`）。この 2-D kernel は GR down projection の値を partial buffer に書き、続く reduce/up 処理へ渡す（同 `:2766-2816`）。

up 側では `gr_up_rows16_enabled()` と `m.T==4` が成立した場合、SoA が無効で本変数が有効なら `gp_launch_compute_pair<4>`、そうでなければ rows16 の標準計算を選ぶ。SoA が有効なら `gp_launch_compute_soa<4>` が優先される。結果は `m.xn` に書かれ、後続の GR postop が実行される（同 `:2863-2880,3103-3109`）。down と up の選択は独立しており、down だけ、または up だけで pair 実装になる場合がある。変数から CLI や設定ファイルへの値の転送はなく、他の環境変数もこの分岐を上書きせず、上記の追加 gate と優先経路として作用する。

## ログと測定値

この変数の有効・無効を示す専用ログ、警告、終了処理は読み取り箇所と dispatch にない。`docs/DETAILS.md` にもこの変数や 2-D pair の測定値の記載は見つからなかった。したがって、この調査では速度・精度・token 同一性を主張しない。SYCL queue の kernel 実行エラー等はこの環境変数固有の処理ではなく、本変数の分岐からは個別のエラー文言を確認できない。

## 根拠

- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2764` — 環境値の判定と main actor gate。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2692` — FP32-register 経路と phase 判定。
- `sycl/src/kernels/cuda/fused_gr.dp.cpp:3103-3115,3360-3370,3466-3470` — down/up の適用条件と優先順位。
- `sycl/include/b60_layout_state.hpp:7-20`、`sycl/src/core/verify.cpp:940-942`、`sycl/src/kernels/cuda/weight_permute.dp.cpp:103-107` — main actor の条件と scope。
- `sycl/CMakeLists.txt:38-43`、`CMakeLists.txt:23-32` — SYCL build への所属と backend 条件。
- `sycl/src/program/generate.cpp:3140-3150`、`sycl/src/core/layer.cpp:1558-1559` — fused GR の有効化条件。
