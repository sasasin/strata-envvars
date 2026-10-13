# `STRATA_GDN_REC_HEADS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

プロンプト処理の GDN recurrence に、1 value head を1 CUDA/HIP/SYCL work-group（block）で処理し、出力 norm も同じ kernel 内で行う経路を選びます。通常の列分割 recurrence と別 norm kernel を使う経路との A/B 用スイッチです。GDN の decode step 全般や、外部ライブラリの設定を制御する変数ではありません。

## 値と判定

値は parse されず、環境変数が設定されているかだけを `getenv(...) != nullptr` で判定します。

| 状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字を含む任意の設定値（`0`、`false` なども含む） | 有効 |

値の大小文字、数値形式、前後の空白は関係しません。明示設定された値を無効扱いにする値はありません。

## 有効になる条件

CUDA/HIP/SYCL の prompt GDN recurrence 経路で有効です。CUDA/HIP 実装と SYCL 実装の双方に判定があります。プロンプトの GDN layer を処理すると `gdn_recurrence()` が呼ばれます。decode の GDN は `gdn_step()` / native GDN の別経路であり、この recurrence スイッチを通りません。

AMD では `STRATA_GDN_HEAD` が非ゼロとして読み取られる場合、既定の `variant 1`（4 lanes per column と grid-stride norm）を使いますが、この変数が設定されていると `variant 0` に切り替わり、さらに one-block-per-head kernel を選びます。gfx1151/gfx12 の起動時 arch defaults は、利用者が `STRATA_GDN_HEAD` を指定していない場合に `STRATA_GDN_HEAD=1` を設定します。`STRATA_GDN_REC_HEADS` はその既定を含む head 経路を抑止します。CUDA では通常 `STRATA_GDN_HEAD` による AMD 向け variant 選択はありませんが、本変数による one-block-per-head 選択は同じです。

通常の prompt 経路以外に、`gdn_recurrence_variant()` は `T <= 0` または明示 variant 2 の場合にも同じ one-block kernel を使います。これは本環境変数の値に関係しない分岐です。

## 実行時の詳細

環境変数を有効にすると、各 head の state を保持しながら token recurrence を実行する `gdn_rec_kernel` を `HV` work-groups で起動します。この kernel は recurrence 出力の norm、`gamma` と `sigmoid(z)` の適用、FP32 scratch `y` および後段 projection が読む FP16 `y16` への書き込みまで行います。通常の列分割経路は各 head の列を複数 work-group に分け、得られた値の norm を別 kernel で計算します。

ヘッダーは one-block-per-head の fused norm が別 norm kernel と異なる丸めになると記載しています。従ってこの変数は同一出力を保証するスイッチではありません。コード上で本変数の有効・無効を知らせるログはありません。判定は関数内の `static` 値に cache され、各判定が初期化された後に環境を書き換えてもその判定結果は更新されません。

## 根拠

- `src/prefill/kernels.cu:1927-1994,1996-2003`: CUDA/HIP recurrence の選択。設定有無を判定し、serial 経路では `gdn_rec_kernel` を起動。
- `src/prefill/kernels.cu:394-448`: one-block-per-head kernel の recurrence、fused norm と `y` / `y16` の出力。
- `src/prefill/kernels.cu:450-493`: 通常の列分割 kernel は中間出力を書き、norm は別 kernel で処理。
- `sycl/src/prefill/kernels.dp.cpp:2603-2735,2736-2744`: 同等の SYCL dispatch と環境判定。
- `src/prefill/prefill.cpp:2603-2626`、`sycl/src/prefill/prefill.cpp:2886-2909`: prompt の GDN layer から recurrence を呼び出す箇所。
- `include/strata/prefill/kernels.hpp:59-69`: variant の意味、one-block-per-head の fused norm は異なる丸めになるとの記載。
- `src/core/arch_defaults.cpp:12-30,61-79`、`src/program/generate.cpp:2152-2157`、`sycl/src/program/generate.cpp:1970-1976`: AMD gfx12/gfx1151 で `STRATA_GDN_HEAD=1` を既定設定し、利用者設定を優先する処理。
- `docs/STRIX_HALO.md:83-97`: gfx1151 の exact speed defaults に `STRATA_GDN_HEAD` を含める説明。本変数の個別動作や one-block-per-head 経路の性能値は記載されていないため、ここでは測定性能を主張しない。
