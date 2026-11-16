# `STRATA_PRIVATE_GU_IQ1_PACKED`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の B60 private decode layout で、IQ1_M (`gu_type == 29`) の expert gate/up weight を 56-byte ブロックの packed 配置へ含め、対応する packed IQ1_M gate/up kernel を選べるようにする opt-in 変数です。設定だけでは有効にならず、B60 layout の構築・packed phase と、Battlemage 上の対応する main-actor decode 経路が必要です。未設定時の通常配置や別 kernel の挙動を変更しません。読み取りは SYCL の `b60_private::Layouts::add_experts` と SYCL kernel 側 `i1_enabled` / staging・mirror helper にあります（`sycl/include/b60_layout_host.hpp:38-54`, `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5088-5092`, `sycl/src/kernels/cuda/weight_permute.dp.cpp:295-330`）。

## 値と判定

各箇所とも C `getenv` の値ポインターが非 null で、先頭文字が ASCII `1` の場合だけ有効です。文字列全体の比較や数値変換はしません。空文字は無効、末尾の文字は無視されます。したがって `1`、`10`、`1abc` は有効、`0`、`01`、`true`、` 1`、空文字、未設定は無効です（`sycl/include/b60_layout_host.hpp:49-50`, `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5089-5091`, `sycl/src/kernels/cuda/weight_permute.dp.cpp:306-307,329-330`）。

| 読み取り箇所 | 未設定・無効値 | 有効値 | 判定と評価時期 |
|---|---|---|---|
| B60 layout の expert 登録 | IQ1_M gate/up を layout batch に追加しない | 先頭文字が `1` で `gu_type == 29` の場合に登録 | `add_experts` が expert slot ごとに `getenv` を呼ぶ。関数内 cache なし（`sycl/include/b60_layout_host.hpp:38-54`）。 |
| IQ1_M kernel 選択 | private kernel は選択しない | 先頭文字が `1` | `i1_enabled` の関数内 `static const bool` に初回呼び出し時 cache（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5089-5092`）。 |
| packed mirror / staging の byte mapping | `pack29` は false | 先頭文字が `1` | それぞれの関数呼び出し時に lambda で読み取り、関数内で値を保持（`sycl/src/kernels/cuda/weight_permute.dp.cpp:306-330`）。 |

CLI 引数・設定ファイル・他の環境変数からこの値を上書きする読み取りはありません。各読み取り箇所は同じ先頭文字判定をしますが、kernel 選択だけは初回呼び出し時に値を cache します。プロセス実行中に環境値を変更した場合、読み取り箇所間で結果が揃わない可能性があります。Strata によるこの変数の書き換えは見つかりません。

## 有効になる条件

- SYCL backend の build が必要です。対象 kernel は SYCL の `iq_kernels.dp.cpp` と `weight_permute.dp.cpp` を build 対象に含みます（`sycl/CMakeLists.txt:40,244,252`）。
- Expert weight の B60 layout 登録には `STRATA_PRIVATE_B60_DECODE_LAYOUT=1` が必要です。このゲートがない通常経路では `b60_layouts.add_device` / `bind_single` が呼ばれず、`b60_weights_packed()` も true になりません（`sycl/include/b60_layout_state.hpp:7-9`, `sycl/src/program/generate.cpp:7876-7887`, `sycl/include/b60_layout_host.hpp:117-135`）。
- 既定の B60 layout 候補経路では、`--serve`、native expert pack、2 stage pipeline、no-prefill-borrow、batch 無効、prompt cache 無効、spec 上限、および固定モデル形状などの条件が必要です。違反時は `B60 layout candidate requires the fixed all-resident two-stage decode scene` で例外になります。また `STRATA_PRIVATE_PACKED_REGISTER` の先頭文字が `1` でなければ `B60 packed weights require the packed register reader` で例外になります（`sycl/src/program/generate.cpp:7879-7887`）。
- single-actor 経路では `STRATA_PRIVATE_BMG_SINGLE_ACTOR=1` も必要で、さらに `--serve`、native pack、単一 GPU、no-host/device-plan 等の固定 scene 条件を満たす必要があります（`sycl/src/program/generate.cpp:4508-4515`, `sycl/include/b60_layout_state.hpp:8,14-20`）。
- IQ1_M packed kernel は `gu_type == 29` かつ `n_embd == 2560`, `n_ff == 640`、旧 kernel と split-multi が無効、main actor 中、weight が packed 状態、GPU 世代が Battlemage の場合だけ選ばれます。条件を満たさなければこの kernel の分岐を通らず、後続の kernel 選択へ進みます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5089-5092,5615-5623`）。
- B60 layout で IQ1_M expert を登録する場合、`gu_row == 560`, `up_off == 358400`, `down_off == 716800` である必要があります。形状が異なると `B60 IQ1_M offsets` の `invalid_argument` になります（`sycl/include/b60_layout_host.hpp:49-53`）。

## 実行時の詳細

layout 登録時、値が有効で expert の `gu_type` が 29 なら IQ1_M gate と up の各領域を type 29・640 rows・10 blocks として batch に加えます。各 batch の weight は B60 layout の packed phase で順列変換され、type 29 / 10-block は 56-byte block の変換ルーチンに渡されます（`sycl/include/b60_layout_host.hpp:49-53,126-135`, `sycl/src/kernels/cuda/weight_permute.dp.cpp:8-15,35-42,88-98`）。single-actor staging と mirror exchange も `pack29` を byte mapping に渡し、IQ1_M の gate/up byte 配置を選択します（`sycl/src/kernels/cuda/weight_permute.dp.cpp:271-280,295-342`）。

decode の gate/up dispatch では `i1_enabled` が true のとき `launch_gu_iq1` を呼び、IQ1_M の packed weights から gate/up dot product を計算します。値だけでは dispatch されず、Battlemage・packed weights・main actor・固定形状等の条件に依存します（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5088-5092,5171-5189,5605-5623`）。layout が prefill 等のため raw に戻る区間では `b60_weights_packed` が false となり、この条件も外れます（`sycl/include/b60_layout_host.hpp:126-135`, `sycl/src/program/generate.cpp:11074-11080`）。

## ログと測定値

変数自身の有効・無効を示す専用ログは見つかりません。B60 layout 経路が進む場合は `B60_LAYOUT phase=packed ...`、single-actor staging では `B60_SINGLE_LAYOUT ...` 等が stderr に出ますが、これらは B60 処理のログであり、この変数の検出ログではありません（`sycl/include/b60_layout_host.hpp:107,124-135`）。配置形状が合わない場合の例外文言は `B60 IQ1_M offsets` です（同 `:49-50`）。`docs/DETAILS.md` にこの変数固有の測定値や効果の計測条件は見つからず、性能値は記載しません。

## 根拠

- `sycl/include/b60_layout_host.hpp:38-54,111-137` — 値判定、IQ1_M expert の登録、packed phase、ログ。
- `sycl/src/kernels/cuda/weight_permute.dp.cpp:8-42,88-98,295-342` — 56-byte 配置変換と staging / mirror の値判定。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5088-5092,5171-5189,5605-5623` — cache、Battlemage 条件、packed IQ1_M kernel と dispatch。
- `sycl/include/b60_layout_state.hpp:7-20` — layout / single-actor gate と main actor 状態。
- `sycl/src/program/generate.cpp:4508-4515,7876-7887,11074-11080` — B60 layout の有効条件・構築・raw/packed phase。
