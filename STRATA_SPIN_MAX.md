# `STRATA_SPIN_MAX`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。調査範囲は Strata 所有ソース。外部ライブラリやドライバー内部の動作は対象外。

## 役割

SYCL バックエンドで GPU カーネルがホスト共有フラグを待つときの、1回の spin ループの最大読み取り回数を指定します。無限 spin による待ち続けを防ぐ上限です。値は `spin_max(queue)` がホスト側で決め、待機カーネルへ引数として渡されます。

直接の読み取りは `sycl/include/strata/sycl_doorbell.hpp` の `spin_max()` 一か所です。適用先は、通常の doorbell flag 待ちと verifier の `wait_flag_ge` / `wait_flag_ge_or` の3種類です。CUDA/HIP 等、SYCL 以外のバックエンドにこの読み取りを適用する根拠は見つかりませんでした。

## 値と判定

`std::getenv("STRATA_SPIN_MAX")` で取得し、設定されていて `std::atol(e) > 0` の場合だけ値を採用します。文字列全体の厳密な数値 parse ではありません。`atol` が先頭から読める整数部分を使うため、例えば `12junk` は 12、`  +12` は 12、未設定・空文字・数値に変換できない文字列・`0`・負数は環境値として採用されず、後述のビルド値またはデバイス別既定値に進みます。正数を `uint32_t` にキャストし、追加の clamp はありません。`uint32_t` の範囲を超える正数はキャスト時に狭められます。

優先順位は次のとおりです。

| 条件 | 採用する spin 上限 |
|---|---:|
| `STRATA_SPIN_MAX` が正の整数に変換される | その値（`uint32_t` に変換） |
| 環境値を採用せず、`STRATA_SYCL_SPIN_MAX` がビルド時に定義済み | ビルド時定数 `STRATA_SYCL_SPIN_MAX` |
| 上記以外でドライバー名が `xe` | 20,000 |
| 上記以外でドライバー名が空、デバイス世代が Battlemage | 通常 20,000。後述の suffix draft 条件では 2,000,000 |
| その他 | 2,000,000 |

環境値が正ならビルド時定数より優先します。環境値が unset、空、0、負数などで、`STRATA_SYCL_SPIN_MAX` が定義されている場合は、ドライバー別の既定値判定には進みません。ビルド設定は `sycl/CMakeLists.txt:31-38` にあります。

## 有効になる条件

この変数を読むのは SYCL 側の共通ヘッダーです。値は SYCL queue のデバイスごとに決定されるため、GPU を使う経路で以下の待機カーネルが起動した場合に影響します。

- `doorbell_wait`: doorbell sequence が期待値になるまで待つ（`sycl/src/kernels/cuda/elementwise.dp.cpp:385-411`）。
- verifier の `wait_flag_ge` と `wait_flag_ge_or`: ホストが公開する計画・データの flag を待つ。後者は skip flag が対象値なら待たずに戻る（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:2053-2063,2320-2330,2399-2413,2458-2471`）。

SYCL デバイスの既定値を決める際、`intel_gpu_driver()` は Linux の `/sys/class/drm` にある Intel GPU の driver link 名を読みます。`xe` なら 20,000 回です。driver 名が取得できない場合（例えば sysfs がない環境）は `intel_gpu_gen()` でデバイスを識別し、Battlemage なら通常 20,000 回、その他は 2,000,000 回です（`sycl/include/strata/sycl_queue.hpp:101-115,119-155`）。driver 名が `i915` など `xe` 以外で空でもない場合は、2,000,000 回側になります。

Battlemage かつ driver 名が空の場合だけ、`generate` が `--spec` を2以上にし `--mtp` を指定しない実行で `spin_drafts_need_long_bound(true)` を呼び、suffix drafter 用の上限を 2,000,000 回にします。この設定は `spin_max()` が当該デバイスの値を初めて決める前に反映される必要があります。Linux `xe` の値はこの条件でも 20,000 のままです（`sycl/src/program/generate.cpp:2268-2281`, `sycl/include/strata/sycl_doorbell.hpp:127-149`）。

## 実行時の詳細

`spin_max(queue)` はデバイスをキーとする静的 map に結果を保存し、mutex で保護します。同じデバイスでは初回の呼び出し後に再計算しないため、その後プロセス内で環境変数を変更しても、そのデバイスの上限には反映されません。複数デバイスを使う場合は各デバイスの初回呼び出しごとに読み取られます。値を読み取ったりキャッシュしたりするだけの診断ログは、この関数にはありません。

device 側の各ループは `spin < spin_max` の間、フラグが目的の状態になるか読み取り回数に達するまで反復します。上限に達した場合、ループを抜けてカーネルを続行します。この変数自体がエラーを返したり、待機失敗をログ出力したりする処理はありません。したがって、上限を短くしすぎると、ホスト側のフラグ更新を待ち切れずに後続処理へ進む可能性があります。長い上限は待機を長く許し、短い上限は失敗時に早く待機を打ち切ります。

## 文書との照合・根拠

現行の既定値と分岐は `sycl/include/strata/sycl_doorbell.hpp:114-153` にあります。`docs/INTEL.md:708-717` は `STRATA_SYCL_SPIN_MAX` を通常の既定値決定手段として説明し、bmg AOT ビルドを例外としていますが、現行ソースにはその AOT 条件による分岐はなく、実行時の driver 名と GPU 世代で既定値を選びます。ここでは現行ソースの分岐を採用しました。同資料に記載された試行回数、実行結果、速度値はこのレポートで再測定・再確認していません。

根拠箇所:

- 読み取り、優先順位、既定値、デバイス単位キャッシュ: `sycl/include/strata/sycl_doorbell.hpp:114-153`
- Linux driver 名の取得と GPU 世代識別: `sycl/include/strata/sycl_queue.hpp:101-155`
- suffix draft 条件で長い上限を要求: `sycl/src/program/generate.cpp:2268-2281`
- 通常 doorbell 待ち: `sycl/src/kernels/cuda/elementwise.dp.cpp:385-411`
- verifier の待機ループと launcher: `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2053-2063,2320-2330,2399-2413,2458-2471`
- ビルド時上書きの定義: `sycl/CMakeLists.txt:31-38`
