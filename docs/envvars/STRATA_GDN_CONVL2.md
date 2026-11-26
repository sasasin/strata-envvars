# `STRATA_GDN_CONVL2`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GDN prefill の畳み込み処理で、畳み込み後の Q/K L2 正規化をどのカーネル経路で行うかを選びます。CUDA では `1` が畳み込みと正規化を融合する経路、`2` 以上が畳み込み・SiLU・Q/K 正規化を一つのカーネルにまとめる経路です。SYCL では設定値が非 0 なら融合経路、`0` なら分離経路を選びます。未設定時の Battlemage 自動選択は SYCL 固有です（`engine/src/prefill/kernels.cu:3053-3079`、`engine/sycl/src/prefill/kernels.dp.cpp:2773-2788`）。

この変数は GDN の畳み込みと正規化の実装経路を変えます。CUDA の mode 2 は Q/K の norm の加算順が別経路と異なるため、FP32 レベルの差があり得るとソースコメントにあります（`engine/src/prefill/kernels.cu:466-471`）。トークン選択や生成設定を直接変更する読み取り箇所は見つかりませんでした。

## 値と判定

CUDA は `std::getenv` の結果を `std::atoi` で整数化し、SYCL も `std::atoi` で整数化します。いずれも文字列全体の妥当性検証や範囲チェックはなく、`atoi` が変換できる先頭部分の整数を使います。空文字、先頭が数値でない文字列（例 `true`）、`0anything` は 0 になります。先頭空白の後の数字列は変換されます（例 ` 2x` → 2）。整数範囲外の文字列について、`atoi` の結果はこの文書では保証できません。読み取り箇所は次のように異なります（`engine/src/prefill/kernels.cu:3058-3060`、`engine/sycl/src/prefill/kernels.dp.cpp:2776-2783`）。

| backend / 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA、`STRATA_GDN_CONV_SERIAL` 未設定かつ `T > CONV_TILE` | mode 0 | `1`, `2`, `-1`, `2x`（atoi 結果が非 0） | 空文字、`0`, `0anything`, `true`, `x1`（atoi 結果が 0） |
| SYCL、`STRATA_GDN_CONV_SERIAL` 未設定かつ `rows > CONV_TILE` | 自動選択を許可 | `1`, `2`, `-1`, `2x`（atoi 結果が非 0） | 空文字、`0`, `0anything`, `true`, `x1`（atoi 結果が 0。ただし「未設定」ではない） |

CUDA では変換結果 0 は非融合、1 は `gdn_conv_l2_kernel`、2 以上は `gdn_conv_w_kernel` を選びます。負の非 0 値は `fused_mode >= 2` を満たさないため mode 1 と同じ経路です。未設定は読み取り地点で 0 です（ただし下記の起動時既定値設定が先に環境へ値を補う場合があります）。

SYCL では変数が未設定かどうかと、`atoi` 結果を別々に保持します。設定があり結果が非 0 なら融合、設定があり結果 0 なら分離です。したがって空文字は Battlemage 自動選択を許可しません（`engine/sycl/src/prefill/kernels.dp.cpp:2776-2783`）。

## 有効になる条件

- GDN prefill が実行され、`gdn_conv` が呼ばれる必要があります。通常の prefill 経路からの呼び出しは `engine/src/prefill/prefill.cpp:5203`、`engine/src/prefill/prefill.cpp:9339`、`engine/sycl/src/prefill/prefill.cpp:3546` にあります。
- `STRATA_GDN_CONV_SERIAL` が設定されていると、値が空でも値の内容にかかわらず serial 経路が先に選ばれ、本変数による分岐を通りません。CUDA は `T <= CONV_TILE`、SYCL は `rows <= CONV_TILE` でも serial 経路になります（CUDA `engine/src/prefill/kernels.cu:3054-3059`、SYCL `engine/sycl/src/prefill/kernels.dp.cpp:2775-2780`）。
- SYCL で Battlemage 自動選択が働くのは、本変数と `STRATA_GDN_CONV_SERIAL` が未設定で、`S == 128`、`C % 512 == 0`、かつ `use_bmg_gdn_tiles(queue, rows)` が真のときです。それ以外の未設定ケースは分離 L2 経路です（`engine/sycl/src/prefill/kernels.dp.cpp:2775-2783`）。
- 起動時既定値はユーザーが設定した値（空文字を含む）を優先します。Linux CUDA の `generate` は `apply_gdn_defaults_cuda(true)` を engine が変数を読む前に呼び、未設定なら `2` を設定します（`engine/src/program/generate.cpp:4410-4415`、`engine/src/core/arch_defaults.cpp:263-275`）。このため Linux CUDA の通常の `generate` では、明示指定がなければ mode 2 になります。
- HIP の AMD 既定値表では、gfx1200/1201 と gfx1151 で既定値 `1` が候補になります。gfx12 は `STRATA_GFX12_DEFAULTS=0`、gfx1151 は `STRATA_GFX1151_DEFAULTS=0` で該当表が無効になります（`engine/src/core/arch_defaults.cpp:30-49,64-76`）。gfx1100/1101/1102 の discrete RDNA3 でも既定値 `1` が候補で、`STRATA_GFX11_DEFAULTS=0` 等で表が無効になります（`engine/include/strata/core/gfx11_extra.hpp:39-51`、`engine/src/core/arch_defaults.cpp:312-323`）。これらは未設定時だけ適用され、明示値は保持されます。
- AMD 既定値の適用は HIP の起動処理で `apply_arch_defaults` を呼ぶ経路です。HIP のビルド条件と初期化位置は `engine/src/program/generate.cpp:4287-4320` にあります。CUDA の gfx12 AMD 用表は参照されず、Linux CUDA 用の mode 2 既定値は別の経路です（`engine/src/core/arch_defaults.cpp:39-40,263-275`）。
- 対象モデルが GDN prefill を使わない場合、本変数の読み取り・効果はありません。ソース上、本変数を CLI 引数から上書きする処理はありません。

## 実行時の詳細

CUDA の `gdn_conv` はまず `STRATA_GDN_CONV_SERIAL` の有無と token 数を判定します。融合分岐に入った最初の呼び出しで `static const int fused_mode` を初期化し、そのプロセス中はキャッシュします。mode 2 では `gdn_conv_w_kernel` と履歴更新カーネルを起動して戻り、mode 1 では `gdn_conv_l2_kernel` と履歴更新を起動して戻ります。mode 0 は tiled 畳み込み、履歴更新、別の `gdn_l2_kernel` の順です。カーネル起動後は `check("gdn_conv")` でエラー確認します（`engine/src/prefill/kernels.cu:3053-3079`）。

SYCL の `select_gdn_conv_path` は初回呼び出し時に serial の有無と環境文字列を `static` に保存します。その後は process 内の環境変更を反映しません。選んだ path を `gdn_conv_impl` に渡し、融合経路では畳み込み・Q/K norm のカーネルと履歴更新を行い、Battlemage path では `bmg_conv_normalize` を呼び、分離 path では tiled 畳み込み・履歴更新・L2 norm の順に処理します（`engine/sycl/src/prefill/kernels.dp.cpp:2668-2788`）。

起動時既定値を設定する処理は `setenv(..., 0)`（Windows は `_putenv_s`）を使い、既存値を上書きしません。Linux CUDA の既定値は `generate` 起動処理中に設定されるため、その後の初回カーネル呼び出しより前に反映されます（`engine/src/core/arch_defaults.cpp:218-224,268-275`、`engine/src/program/generate.cpp:4410-4415`）。AMD arch defaults も起動時に適用されます（`engine/src/program/generate.cpp:4287-4320`）。

## ログと測定値

CUDA の `apply_gdn_defaults_cuda` は変数を設定してもログを出しません。HIP の discrete RDNA3 既定値が新たに適用された場合は `strata: gfx11 (RDNA3): ... exact speed switches on by default ...` の行に、接頭辞を除いた `GDN_CONVL2` 名が含まれます。ユーザーが値を設定済みの場合はこの既定値一覧に含まれません（`engine/src/core/arch_defaults.cpp:318-332`）。選択値だけを報告する専用ログや、変数値の不正を示す専用警告は確認できません。カーネル実行時の失敗は `check("gdn_conv")` の確認経路に進みます（`engine/src/prefill/kernels.cu:3061-3079`、SYCL `engine/sycl/src/prefill/kernels.dp.cpp:2721,2771`）。

## 根拠

- CUDA の値読み取り、分岐、kernel dispatch: `engine/src/prefill/kernels.cu:3053-3079`
- CUDA mode 1 / mode 2 の計算経路: `engine/src/prefill/kernels.cu:426-471,473-517`
- SYCL の値読み取りと path 選択: `engine/sycl/src/prefill/kernels.dp.cpp:2773-2788`
- SYCL path 実装と別 L2 norm: `engine/sycl/src/prefill/kernels.dp.cpp:2668-2771`
- Linux CUDA の既定値と未設定時のみの設定: `engine/src/core/arch_defaults.cpp:218-224,263-275`、呼び出し `engine/src/program/generate.cpp:4410-4415`
- HIP の AMD 既定値と条件: `engine/src/core/arch_defaults.cpp:28-76,302-323`、`engine/include/strata/core/gfx11_extra.hpp:39-51`、呼び出し `engine/src/program/generate.cpp:4287-4320`
- GDN prefill からの呼び出し: `engine/src/prefill/prefill.cpp:5203,9339`、`engine/sycl/src/prefill/prefill.cpp:3546`
