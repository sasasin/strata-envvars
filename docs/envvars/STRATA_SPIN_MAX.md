# `STRATA_SPIN_MAX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL エンジンがホスト側のフラグを待つ GPU カーネルに渡す、最大読み取り回数を上書きする。待ちが上限に達するとカーネルは待ちを打ち切り、記録領域があれば失敗記録を書いて呼び出し元へ進む。この値は GPU 待ちの読み取り回数であり、CPU 側の timeout 値ではない。SYCL の `spin_max()` から doorbell と verifier の待ちカーネルに渡される（`engine/sycl/include/strata/sycl_doorbell.hpp:153-179`、`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:390-419`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2740-2746, 2832-2844`）。

## 値と判定

`spin_max()` は呼ばれるたびに `std::getenv` で値を取得し、設定されていれば `std::atol` で `long` に変換する。変換結果が正の場合だけ環境変数の値を採用し、`uint32_t` にキャストして返す。`atol` の戻り値全体が 0 以下なら環境変数による上書きはありません。文字列全体の妥当性や末尾は検証せず、`errno` も確認しません（`engine/sycl/include/strata/sycl_doorbell.hpp:153-162, 164-172`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 通常の SYCL ビルド | ビルド固定値があればその値。なければ下記のデバイス条件による | `atol` が正になる値（例: `1`, `+12`, ` 12`, `12junk`）。正の結果は `uint32_t` にキャストされる | 空文字、`0`、`0anything`、`true`、`-1`、数値に変換できない文字列（いずれも `atol` 結果が 0 以下） |
| `STRATA_SYCL_SPIN_MAX` を定義したビルド | 定義値（環境変数が未設定の場合） | `atol` が正なら環境変数値がビルド固定値に優先 | `atol` が 0 以下ならビルド固定値 |

数値変換は先頭の空白と符号を許し、10 進数として読める先頭部分を使います。したがって `12junk` は 12、`1.5` は 1 となり、`0anything` は 0 です。大文字小文字の比較はありません。正の値も範囲チェックや上限 clamp はされず、`uint32_t` へのキャストで表現幅に縮小されます（`engine/sycl/include/strata/sycl_doorbell.hpp:169-172, 153-162`）。

## 有効になる条件

- この読み取りは `engine/sycl` の SYCL エンジン内です。CUDA/HIP など別 backend の同名変数の読み取りは確認できません。SYCL の CMake 設定では `STRATA_SYCL_SPIN_MAX` が空でなければその値を compile definition として加えます（`engine/sycl/CMakeLists.txt:59-70`）。
- 正の環境値は、デバイスや `STRATA_SYCL_SPIN_MAX` の有無にかかわらず、同一の `spin_max()` 呼び出しで選択される固定値より優先します（`engine/sycl/include/strata/sycl_doorbell.hpp:153-162`）。
- 有効な環境値がない場合、`STRATA_SYCL_SPIN_MAX` が定義されていれば全デバイスでその値を使います。未定義なら Linux の Intel `xe` ドライバーでは host wait が不要なとき 20,000、必要なとき 1,000,000 reads、sysfs driver 名がなく Battlemage と判定されたデバイスでは通常 20,000、`--spec` で MTP 層なしの draft 時は 2,000,000、その他は 2,000,000 reads です（`engine/sycl/include/strata/sycl_doorbell.hpp:134-162`）。
- verifier は非 resident expert がある場合、または host から問い合わせ可能な場合に process-wide の host-wait フラグを上げます。生成処理は `o.spec >= 2 && o.mtp.empty()` のとき long-drafts フラグを上げます。これらは環境値が無効または未設定で、かつビルド固定値もない場合の fallback 選択に使われます（`engine/sycl/src/core/verify.cpp:926-934`、`engine/sycl/src/program/generate.cpp:2559`）。
- 別の CLI 引数や設定値による環境値の上書きはありません。`--spec` と MTP の有無は上記 fallback の選択条件に関係しますが、正の環境値を無効化しません（`engine/sycl/include/strata/sycl_doorbell.hpp:153-162`）。

## 実行時の詳細

`spin_max(queue)` は待ちカーネルの起動前にホスト側で実行されます。doorbell wait、`wait_flag_ge`、`wait_flag_ge_or` の各 launcher がその戻り値を kernel 引数に渡します（`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:407-419`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2832-2844, 2891-2905`）。環境値は呼び出しごとに読み直されるため、プロセス中の環境変更は後続の呼び出しに反映されます。デバイスごとの map は直近の値を保持しますが、値の選択を cache する用途ではなく、値の初回設定・変更時ログを制御する用途です（`engine/sycl/include/strata/sycl_doorbell.hpp:164-179`）。

`bounded_wait` は指定回数まで flag を読み、上限後にも一度読み直します。それでも条件を満たさず記録領域があれば expiry record を書き、`false` を返します（`engine/sycl/include/strata/core/window_wait.hpp:54-71`）。session は失敗記録があれば token を破棄し、エラー文字列を返します。verifier も失敗記録を検出して window を破棄します（`engine/sycl/src/core/session.cpp:1447-1456`、`engine/sycl/src/core/verify.cpp:477-499`）。

## ログと測定値

通常、初回のデバイス bound 選択では `STRATA_SPIN_LOG` が未設定なら出力せず、空文字を含め設定されていれば stderr に `strata: GPU wait bound %u reads on a device` を出します。既に記録したデバイスの値が変わった場合は ` (changed)` を付けて出します。同じ値の再選択では出力しません（`engine/sycl/include/strata/sycl_doorbell.hpp:173-178`）。

host wait が期限切れになると、session では `session_run_token: the GPU stopped waiting for ...; the token was discarded`、verifier では `verify: the GPU stopped waiting for ...; the window was discarded` を含むエラーが設定されます。どちらも採用された上限を `reads` として表示します（`engine/sycl/src/core/session.cpp:1447-1456`、`engine/sycl/src/core/verify.cpp:477-499`）。

## 根拠

- 環境変数の唯一の実読み取り、数値判定、優先順位、fallback、ログ: `engine/sycl/include/strata/sycl_doorbell.hpp:153-179`
- build 固定値の CMake 定義: `engine/sycl/CMakeLists.txt:59-70`
- 上限到達時の記録動作: `engine/sycl/include/strata/core/window_wait.hpp:54-71`
- caller からの値の伝搬と失敗の観測: `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:390-419`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2740-2746, 2832-2844, 2891-2905`、`engine/sycl/src/core/session.cpp:1447-1456`、`engine/sycl/src/core/verify.cpp:477-499`
