# `STRATA_GDN_KEYHEAD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GDN prefill の recurrence kernel を、従来の列分割 kernel `gdn_rec_cols_pipe_kernel` から key-head kernel `gdn_rec_kh_kernel` に切り替えるかを制御する。CUDA では適格性を満たせば通常 dispatch で key-head を使い、`STRATA_GDN_KEYHEAD=0` で抑止する。SYCL では `=1` の明示指定が必要で、それ以外は従来 kernel を使う。CUDA と SYCL で環境変数の既定判定が異なる（CUDA: `engine/src/prefill/kernels.cu:966-982`、SYCL: `engine/sycl/src/prefill/kernels.dp.cpp:1334-1339`）。

この切替は recurrence kernel の選択に限られる。通常経路では後続の出力正規化は引き続き実行され、両 kernel は同じ bit を保つ設計とソースコメントに記されている（CUDA: `engine/src/prefill/kernels.cu:826-835, 3254-3278`、SYCL: `engine/sycl/src/prefill/kernels.dp.cpp:1100-1109, 2893-2938`）。

## 値と判定

両実装とも `std::getenv` の文字列を `std::atoi` で変換し、関数内 `static` に一度だけ保存する。文字列全体の妥当性検査はなく、`atoi` が読む数値接頭辞で判定する。したがって `1tail` は 1、`0tail` は 0、空文字・`true`・数値で始まらない文字列は 0 になる。先頭の空白や符号も `atoi` の変換対象。未設定は `nullptr` として扱う（CUDA: `engine/src/prefill/kernels.cu:966-968`、SYCL: `engine/sycl/src/prefill/kernels.dp.cpp:1334-1338`）。

| backend / 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| CUDA、通常 dispatch | key-head を適格 GPU で許可 | `1`, `2`, `true`, `1tail`（変換結果が 0 以外） | `0`, 空文字, `false`, `0tail`（変換結果が 0） |
| SYCL、通常 dispatch | 無効 | `1`, `1tail`, `1.0`（変換結果がちょうど 1） | `0`, `2`, 空文字, `true`, `2tail`（変換結果が 1 でない） |

これは単独の CLI 引数や設定値ではない。該当コードに CLI 引数・設定ファイルによる上書きはない。`STRATA_GDN_PIPELINE` は別の条件として作用し、CUDA/SYCL とも unset または `atoi` 結果が非 0 の場合に pipeline 経路を許可する（CUDA: `engine/src/prefill/kernels.cu:3188`、SYCL: `engine/sycl/src/prefill/kernels.dp.cpp:2888`）。

## 有効になる条件

- **CUDA:** `__HIPCC__` ではない CUDA dispatch の通常経路であること。`STRATA_GDN_KEYHEAD` が unset または `atoi` 結果が非 0 で、実行中 GPU の compute capability major が 8 以上、occupancy API が成功し、`per_sm * SM数 >= HK * NCB`（全 64 block を同時に resident にできる）を満たす必要がある。GPU 属性取得・occupancy の失敗、CUDA device の取得失敗、device index が 0–63 の範囲外なら不適格となる（`engine/src/prefill/kernels.cu:969-982`）。
- **SYCL:** `__HIPCC__` ではない SYCL 実装で、`STRATA_GDN_KEYHEAD` の `atoi` 結果がちょうど 1、かつ `STRATA_GDN_PIPELINE` が有効であること。コード上、この opt-in に CUDA の occupancy 判定はない（`engine/sycl/src/prefill/kernels.dp.cpp:1334-1339, 2888-2907`）。
- **SYCL Xe (`xe`):** `detail::gdn_xe_launch` が key-head 判定より先に呼ばれるため、この環境変数では切り替わらない（`engine/sycl/src/prefill/kernels.dp.cpp:2887-2893`）。
- **両 backend:** fused / serial / 診断 variant など recurrence dispatch の別分岐に入る場合は key-head 判定に到達しない。CUDA の `STRATA_GDN_CHUNKED` や `STRATA_GDN_TC` が条件を満たして先に成功した場合も key-head を使わない。`STRATA_GDN_PIPELINE=0`（または CUDA/SYCL で `atoi` 結果 0）なら通常の key-head 分岐は通らない（CUDA: `engine/src/prefill/kernels.cu:3083-3110, 3164-3193, 3234-3268`、SYCL: `engine/sycl/src/prefill/kernels.dp.cpp:2887-2910`）。
- **AMD/HIP:** key-head kernel を選ぶ実装はこの dispatch に含まれない。該当する CUDA/SYCL 判定と SYCL 呼び出しは `!defined(__HIPCC__)` 側にある（`engine/src/prefill/kernels.cu:3190`、`engine/sycl/src/prefill/kernels.dp.cpp:1334-1341, 2892-2907`）。

## 実行時の詳細

CUDA では `gdn_keyhead_ok()` 初回呼び出し時に環境変数を読み、`static const bool off` に保持する。その後はプロセス実行中に環境を書き換えても反映されない。環境変数が無効化していなければ、現在 device の capability と occupancy を初回に検査して `known[dev]` に保存する。key-head kernel が不適格なら自動 dispatch は `gdn_rec_cols_pipe_kernel` に fallback する（`engine/src/prefill/kernels.cu:966-982, 3254-3262`）。

SYCL も `gdn_keyhead_ok()` の初回呼び出しで `static const bool on` を決め、そのプロセス内で cache する。pipeline が有効で key-head が on なら `gdn_rec_kh_kernel`、それ以外で pipeline が有効なら列分割 pipeline kernel を launch する（`engine/sycl/src/prefill/kernels.dp.cpp:1334-1339, 2888-2938`）。この変数が recurrence の呼び出しごとに再評価されるコードではない。

CUDA の probe が key-head を明示的に force した場合は適格ならその kernel を選び、不適格なら launch せず、probe の `reason` に `keyhead kernel not eligible here (needs sm_80+ with all 64 blocks resident, or STRATA_GDN_KEYHEAD=0 is set` を記録する。通常の自動 fallback ではこの理由文字列は設定されず、pipe kernel が選択される。dispatch 後の `check("gdn_recurrence")` は CUDA launch error を検出した場合 `exit_device_error` に渡す（`engine/src/prefill/kernels.cu:110-116, 3222-3229, 3269-3279`）。環境変数が不適格を生じさせるだけで通常経路が終了する処理はない。

## ログと測定値

通常の自動 fallback や key-head 選択そのものに対するログ出力は、この dispatch にはない。forced probe の不適格理由は上記 `reason` フィールドに記録される（`engine/src/prefill/kernels.cu:3222-3226, 3269`）。CUDA launch error があれば `check` が device error 経路へ渡す（`engine/src/prefill/kernels.cu:110-116, 3278-3279`）。

`docs/INTEL.md:541` は PR #413 の記録として「8% slower prompt: off (`STRATA_GDN_KEYHEAD=1`)」と記すが、同ファイルの該当行には測定機種・モデル・backend などの条件がない。ソースコメントの CUDA 測定値は CUDA kernel のベンチ記述であり、一般的な効果の保証としては扱わない（`engine/src/prefill/kernels.cu:959-965`）。

## 根拠

- `engine/src/prefill/kernels.cu:966-982` — CUDA の環境変数判定、GPU 適格性と per-device cache。
- `engine/src/prefill/kernels.cu:3083-3110, 3164-3193, 3222-3279` — 別分岐、優先経路、kernel 選択、probe と CUDA error 処理。
- `engine/sycl/src/prefill/kernels.dp.cpp:1334-1339, 2887-2938` — SYCL の opt-in 判定、Xe の bypass と kernel 選択。
- `engine/sycl/CMakeLists.txt:573-577` — SYCL では parity benchmark でなく engine 経由で検証する記述。
- `docs/INTEL.md:541` — 条件が不足する測定記録。
