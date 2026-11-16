# `STRATA_PRIVATE_PACKED_REGISTER`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL エンジンの Battlemage 向け decode 経路で、IQ2_S gate/up と Q2_0 down の packed-register ESIMD kernel を選べるようにする private opt-in です。値を読むだけでなく kernel dispatch を変えます。対象は `sycl/src/kernels/cuda/iq_kernels.dp.cpp` の `ps_enabled()` とその呼び出し経路です。CUDA/HIP 実装でこの名前を読む箇所は見つかりませんでした。

この変数だけでは通常の実行で packed weights を有効にしません。kernel 側は B60 の main actor であり、weights が packed 状態で、実デバイスが Battlemage の場合に限って有効になります（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4466-4469`）。packed 状態は B60 layout の準備時に `Layouts::packed(true)` が設定します（`sycl/include/b60_layout_host.hpp:126-135`、`sycl/src/program/generate.cpp:7876-7887`）。

## 値と判定

kernel 側の `ps_enabled()` は `std::getenv` の結果の先頭 1 文字だけを `1` と比較し、その結果を関数内 `static const bool` に cache します。数値変換や文字列全体の比較はしません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4466-4469`）。

| 判定箇所 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `ps_enabled()` の kernel 選択 | off | `1`, `1anything` | 空文字、`0`, `true`, ` 1`, `01` |
| single-actor の起動時 layout 検査 | layout が要求されなければ検査しない | 文字列全体が `1` のみ | 空文字、`1anything`, `01`, `true` |
| 2-stage layout の起動時検査 | layout が要求され、single actor でない場合は失敗 | 先頭文字が `1`（例: `1anything`） | unset、空文字、`0`, `true` |

single-actor 検査は `std::strcmp(pr, "1")`、2-stage 検査は `pvr[0] != '1'` を使います（`sycl/src/program/generate.cpp:4509-4515, 7879-7887`）。値に空白を trim する処理はありません。kernel の cache は最初の `ps_enabled()` 呼び出しで固定され、プロセス実行中に環境を変えても反映されません。起動時検査は layout 初期化中に直接評価されます。

## 有効になる条件

- Strata の SYCL engine が実行され、対象の kernel dispatch に到達すること。`ps_enabled()` は Intel Battlemage 以外では false です（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4466-4469`）。
- B60 decode layout が要求され、layout 初期化で weights が packed になり、該当する実行スコープが main actor であること。layout 要求と single-actor 要求はそれぞれ `STRATA_PRIVATE_B60_DECODE_LAYOUT` と `STRATA_PRIVATE_BMG_SINGLE_ACTOR` の先頭文字 `1` で cache されます（`sycl/include/b60_layout_state.hpp:7-8, 14-20`）。
- IQ2_S gate/up の基本経路では、形状が `n_embd=2560`, `n_ff=640`、古い kernel と split-multi が無効で、`TG=22`, `LN=8`, `KM=true` であることが必要です（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:5605-5628`）。
- Q2_0 down の基本経路では、`TD=42`、古い kernel と split-multi が無効、`down_lanes()==8` が必要です。さらに `STRATA_SYCL_Q2_WORD_EXPAND` が `0` でなく（unset なら有効）、Battlemage である必要があります（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:3702-3714, 5862-5868`）。このフラグが無効なら本変数による down kernel 選択にも到達しません。
- single-actor layout では、これらに加えて `--serve`、native pack、単一 GPU、pipeline 無効、prefill borrow 無効、batch 無効、prompt cache 無効、`--spec <= 6`、async adapt 無効、および固定モデル形状が起動時に要求されます。`STRATA_VERIFY_NO_HOST` と `STRATA_VERIFY_DEVICE_PLAN` はともに文字列全体が `1` である必要があります。不一致時は `B60 single layout requires the fixed single-device no-host decode scene` の `std::invalid_argument` が投げられます（`sycl/src/program/generate.cpp:4509-4515`）。
- single actor でない B60 layout では native pack、2-stage pipeline、`n_stages==2`、prefill borrow 無効、batch 無効、prompt cache 無効、`--spec <= 6` と固定モデル形状が必要です。不一致時は `B60 layout candidate requires the fixed all-resident two-stage decode scene` が投げられます（`sycl/src/program/generate.cpp:7879-7887`）。
- `STRATA_PRIVATE_B60_NEXT_POOL` などの別フラグと route 条件が一致すると、IQ2_S gate/up は grid S4 系の専用 kernel に進む場合がありますが、その分岐も `ps_enabled()` を条件にします（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:7393-7411`）。down 側は `STRATA_PRIVATE_DOWN_S4` が有効なら `launch_ps_down()` 内で S4 kernel を選びます（同: `5598-5603`）。

## 実行時の詳細

起動時、B60 layout を要求した場合に single-actor 分岐では `prepare_single()`、後続の layout binding 時には `packed(true)` を実行します。2-stage layout では `STRATA_PRIVATE_PACKED_REGISTER` の存在と値を検査してから各 device の layout を組み、packed 状態にします（`sycl/src/program/generate.cpp:4508-4515, 7876-7887`）。`packed(true)` は重みを変換し、完了後に `b60_weights_packed` 状態を true にします（`sycl/include/b60_layout_host.hpp:126-135`）。

kernel dispatch では IQ2_S の gate/up が `launch_ps_gu()` を呼び、Q2_0 down が `launch_ps_down()` を呼びます。これらは `pvr_gu_packet` / `pvr_down_packet` を使う ESIMD kernel launchers です（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4482-4541, 4544-4595, 5593-5603, 5625-5628, 5727-5740`）。`ps_enabled()` の値は初回呼び出し時に cache されます。generate 側の直接検査は起動時の B60 layout 初期化時のみです。この変数を CLI 引数や別変数で上書きする処理、子プロセスへ転送する処理は見つかりませんでした。

## ログと測定値

本変数だけを理由に出す専用ログはありません。B60 layout 自体を使うと `Layouts::packed(true)` が `B60_LAYOUT phase=packed ...` を stderr に出しますが、これは layout の変換状況を示すログです（`sycl/include/b60_layout_host.hpp:126-135`）。資料 `docs/DETAILS.md` に本変数の説明や、この kernel 経路の測定値は見つかりませんでした。起動時の条件不一致では上記の `std::invalid_argument` が発生しますが、Strata の main function-try-block は SYCL exception の handler のみを持つため、この `std::invalid_argument` に対する Strata 固有の整形ログは確認できません（`sycl/src/program/generate.cpp:1779, 7880-7883`、同ファイル末尾の SYCL exception handler）。

## 根拠

- 全参照の検索結果: `data/settings-register.json:31581` は索引データ、実際の読み取りは `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4467` と `sycl/src/program/generate.cpp:4512, 7882-7883`。
- 値判定・デバイス条件: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4466-4469`。
- B60 layout flag と actor 状態: `sycl/include/b60_layout_state.hpp:7-20`、packed 状態の更新: `sycl/include/b60_layout_host.hpp:126-135`。
- 起動時制約と失敗条件: `sycl/src/program/generate.cpp:4508-4515, 7876-7887`。
- kernel の dispatch と関連条件: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3702-3714, 5593-5603, 5605-5628, 5727-5740, 5862-5868, 7393-7411`。
