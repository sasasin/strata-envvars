# `STRATA_UC_PROBE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL 版 `strata` の実行中に、同じ SYCL queue で小さな計測用 kernel 群を実行し、タグごとの時間と device allocation 数を stderr に出す診断スイッチです。通常の生成機能の設定値ではなく、コードコメントでも test-only とされています。プローブは空の device buffer を確保して独自 kernel を反復実行するため、設定時は生成処理に計測用の実行・待ち時間と追加メモリ確保が加わります。生成 token の選択やモデル設定を変える分岐はこの変数にはありません（`engine/sycl/include/strata/uc_probe.hpp:1-10,77-150`）。

## 値と判定

`std::getenv` の結果を `on()` 内の関数ローカル `static const bool` に一度保存し、値の先頭 byte が存在して `\0` でも `'0'` でもないとき有効にします。文字列全体の parse、数値検証、trim、大文字小文字変換はしません（`engine/sycl/include/strata/uc_probe.hpp:26,77-79`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL `strata` | 無効 | `1`、`true`、`false`、` 0`、`00` など先頭 byte が `'0'` 以外の非空文字列 | 空文字、`0`、`0anything`、`01` など先頭 byte が `'0'` の文字列 |

前後空白は除去されません。したがって空白だけの値は有効、` 0` も先頭が空白なので有効です。`false` も文字列比較をしないため有効です。SYCL 以外の実行ファイルでは、この読み取り箇所は確認できません（`engine/sycl/CMakeLists.txt:375-377`）。

## 有効になる条件

- `engine/sycl` の `strata` 実行ファイルを使う必要があります。ここでは `generate.cpp` が `strata` ターゲットの main としてリンクされ、同ファイルが `uc_probe.hpp` を include します（`engine/sycl/CMakeLists.txt:375-377`; `engine/sycl/src/program/generate.cpp:26-34`）。
- 最初の `strata::uc_probe` 呼び出し時に値が有効である必要があります。最初の呼び出しは `main` 内の `Options` 初期化と CLI 引数走査より前の `start` タグです。CLI 引数や別の環境変数による `STRATA_UC_PROBE` の上書き処理はありません（`engine/sycl/src/program/generate.cpp:1877-1889`）。
- 機種を Arc Alchemist に限定する実行時チェックはありません。SYCL queue と当該実行ファイルの計測コードが動く経路で呼び出されます。コメントは Arc Alchemist 上の uncached host memory の影響調査を目的として記していますが、条件分岐はありません（`engine/sycl/include/strata/uc_probe.hpp:1-10,77-82`）。
- server / stdin command 経路では `ready` や request 後にも呼び出します。通常の CLI 経路では起動、weights / native-dense 後、profile / head / fill / cache の後、prefill 前後、終了前などに呼びます。`captured` は別の `STRATA_WARM_GRAPHS` 判定が真のときだけ呼ばれます（`engine/sycl/src/program/generate.cpp:3206,3218,3821,4589,5419,6002,9573,13134,13304,13425,13961-13974,14388`）。

## 実行時の詳細

`on()` が最初に呼ばれた時点で環境値をキャッシュし、以後の各 probe 呼び出しはその値を再利用します。プロセス稼働中に環境値を変えても有効状態は変わりません。`uc_probe` は有効時、`dpct::get_in_order_queue()` を使い、device buffer を確保して初期化した後、Q8_1 量子化と Q8_0 / Q6_K MMVQ、FMA、短い加算 kernel の時間を測ります。各計測は warm-up 後に反復し、3 回中の最小値を表示します。また FMA / tiny の device event 計測と空 kernel 提出の host 時間、Strata の登録済み device allocation 数・総量も表示します（`engine/sycl/include/strata/uc_probe.hpp:28-50,77-150`）。

起動時の `start` が最初の有効な probe であるため、同時に `STRATA_UC_POISON` が非空で設定されていれば、その最初の probe 後に `poison()` を呼び、追加の `after-poison` 計測を行います。kernel を実行する値は `fp64`、`uc_read`、`uc_write`、`cached_read`、`shared_write` です。その他の非空値では poison kernel の分岐に入らず、`UCPROBE poisoned with <値>` の出力と追加 probe は行われます。これは別変数による診断用分岐で、`STRATA_UC_PROBE` が無効なら到達しません（`engine/sycl/include/strata/uc_probe.hpp:9-10,52-74,151-155`; `engine/sycl/src/program/generate.cpp:1877`）。

queue 操作・device allocation・kernel 実行に対する `uc_probe` 固有のエラー文字列や明示的な fallback はありません。GPU event profiling 部分だけは例外を握りつぶし、取得失敗時の `gpu-stamps` 欄は初期値 `-1.0` のままです。それ以外の SYCL 操作の失敗処理は呼び出し元に追加されていません（`engine/sycl/include/strata/uc_probe.hpp:34-40,114-149`）。

## ログと測定値

有効時は stderr に次の形式で計測行を出します（`tag` には呼び出し地点名が入ります）。

- `UCPROBE <tag>   registered device allocations: <件数> (<GiB> GiB)`
- `UCPROBE <tag>   gpu-stamps: fma <us>  tiny <us>   host cost of an empty launch <us>`
- `UCPROBE <tag> head <us>  q6k <us>  fma <us>  tiny <us>`
- poison が実行された場合: `UCPROBE poisoned with <値>`

無効時は `uc_probe` が直ちに戻るため、これらの行は出ません。調査対象の `docs` にこの probe の実測結果は見つからず、ここでは計測値を記載しません（`engine/sycl/include/strata/uc_probe.hpp:77-79,146-153`）。

## 根拠

- `engine/sycl/include/strata/uc_probe.hpp:1-26` — 用途コメント、追加の診断変数、判定と cache。
- `engine/sycl/include/strata/uc_probe.hpp:28-74,77-155` — buffer、kernel 計測、stderr 出力、例外捕捉、poison 呼び出し。
- `engine/sycl/src/program/generate.cpp:26-34,1877-1889,3206,3218,3821,4589,5419,6002,9573,13134,13304,13425,13961-13974,14388` — include、最初の呼び出しと CLI 前後、実行中の呼び出し位置。
- `engine/sycl/CMakeLists.txt:375-377` — SYCL `strata` 実行ファイルの main ソースとリンク先。
