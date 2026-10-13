# `STRATA_WINDOW_SYNC`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

SYCL 版 verifier が各 verification window を GPU キューへ投入する直前に、デバイスの全キューを待つかを選ぶ内部調整用環境変数。i915 ドライバーで、他の GPU 作業が残っている状態から window を開始すると開始しない事象への回避策として使われる。CUDA/HIP 側の `src/core/verify.cpp` にはこの変数の読み取りはない。

## 値と判定

最初の `Verifier::run` で `std::atoi` により整数化し、その結果が次のように判定される。

| 設定値 | 動作 |
|---|---|
| `1` | 各 window の投入前に全キューを待つ。 |
| `0` | この箇所では待たない。 |
| `2` | 初回 window、または直前 window の完了から今回の投入までが20 msを超えた場合に待つ。 |
| 未設定 | i915 なら `1`、それ以外なら `0`。 |
| その他の整数 | 上記いずれの分岐にも一致しないため、この箇所では待たない。 |

判定は parse 後の整数との完全一致で行う。`atoi` のため、空文字や先頭が数値でない文字列は `0` になり、`1abc` は `1`、`2abc` は `2` として扱われる。`atoi` の結果が同じなら、後続の文字列部分は判定に影響しない。空文字は「未設定」扱いではなく、明示設定の `0` と同様に待たない。

## 有効になる条件

- この読み取りと制御は `sycl/src/core/verify.cpp` の `Verifier::run` にあるため、SYCL verifier の実行経路でのみ適用される。
- 未設定時の既定値判定は `strata::intel_gpu_driver() == "i915"`。この helper は `/sys/class/drm` 以下の Intel (`0x8086`) GPU デバイスの driver symlink を調べ、結果を static string に保持する。i915 として検出できない環境（例: driver 名が `xe`、または検出結果が空）では既定値は `0`。
- `2` の「初回」はこの `Verifier::run` 関数内の static `t_prev_end` が未初期化のとき。以後は直前の run 完了時刻から投入開始時刻までの差が厳密に20 msを超えるかで決まる。ちょうど20 msでは待たない。

## 実行時の詳細

window 入力を staging し `t_launch` を記録した直後、window を実行する通常経路や stepped 経路へ進む前にモードを評価する。`wmode == 1`、または `wmode == 2 && first_or_gap` の場合に `dpct::get_current_device().queues_wait_and_throw()` を呼び、その後 window の処理を続ける。待つ場合は他キューの処理が完了するまで window 投入前の重なりを失う。`wmode` は関数内 static なので、環境変数と i915 判定に基づくモードは最初の `Verifier::run` 時に一度だけ決まり、プロセス実行中に環境変数を変更しても再評価されない。

この箇所に `STRATA_WINDOW_SYNC` 専用のログ出力はない。待ち API の失敗は `Verifier::run` 内の既存 SYCL error handling 経路へ進み得るが、変数別のエラーメッセージは実装されていない。ソースコメントは Arc A750 での window 開始失敗について説明し、常時 wait がそれを避けたこと、gap 条件だけでは解決しなかったことを記す。これはコメントに記された観測であり、この調査で再測定した性能・成功率ではない。

## 文書との照合

`docs/INTEL.md` の Arc A750 節には i915 環境での GPU window hang や `Fence expiration time out` などの背景説明があるが、`STRATA_WINDOW_SYNC` の記載はない。具体的な値・既定値・適用条件は現行ソースから確認した。

## 根拠

- `sycl/src/core/verify.cpp:203-204` — i915 判定 helper。
- `sycl/src/core/verify.cpp:1996-2008,2028-2039` — verifier window の入口、static 時刻、環境変数 parse、wait 条件と呼び出し。
- `sycl/src/core/verify.cpp:2307-2317` — window 完了時刻を記録し、次回の gap 判定へ使う流れ。
- `sycl/include/strata/sycl_queue.hpp:94-115` — Intel driver 名の検出と static cache。
- `docs/INTEL.md:700-703,708-717` — i915 環境の関連背景。`STRATA_WINDOW_SYNC` 自体の説明ではない。
