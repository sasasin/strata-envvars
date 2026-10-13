# `STRATA_SYCL_A770_FAST`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

SYCL 実装で、実験的な高速 router と mapped memory 転送のペア化を選びます。変数名に A770 とありますが、実装は GPU の型を検査せず、SYCL の該当コード経路で値だけを見て分岐します。主な効果は次の3つです。

- router の入力条件が合うと、既定 kernel の代わりに SYCL fast router を使う。
- doorbell がホスト mapped memory に activation vector `x` を送る際、条件が合えば float を2個ずつ64-bit storeで書く。
- device-plan 検証で mapped memory から結果を読む際、条件が合えば `float4` を2つの64-bit loadで取得する。

## 値と判定

`sycl/include/strata/sycl_doorbell.hpp:22-25` の `a770_fast()` が `std::getenv()` の結果を見ます。文字列全体や数値としての parse はせず、先頭文字だけを検査します。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定値の先頭が `\0`） |
| 先頭文字が `1` | 有効。例: `1`, `10`, `1anything` |
| それ以外 | 無効。例: `0`, `true`, ` 1` |

判定結果は関数内の `static const bool` に保存されるため、最初の `a770_fast()` 呼び出し後にプロセス環境を書き換えても再評価されません。CLI 引数や設定ファイルによる上書きはこの判定箇所にはありません。

## 有効になる条件

### Fast router

`router_top10()` が呼ばれ、`n_tokens > 0`、`64 < n_expert <= 512`、`0 < k <= 32` のすべてを満たすと fast router を起動します。`stream == nullptr` の場合は起動後に queue を待ちます。条件に合わない場合は通常の `router_top10` 経路に進み、フラグが有効でも fast router は使われません（`sycl/src/kernels/cuda/router_top10.dp.cpp:679-686`）。

### Doorbell payload の paired store

`doorbell_publish()` と `doorbell_publish_value()` はフラグを kernel 引数に渡し、activation vector を公開する処理で使います。`dbx_publish_x()` は、paired store の指定があり、`STRATA_DOORBELL_PLAIN` 等による plain store モードが無効で、出力先アドレスが8-byte境界に揃っているときに、隣り合う float 2個を1回の64-bit mapped storeで書きます。端数が奇数個なら最後の1個は通常 store です。plain store モードまたは非整列アドレスでは全体が通常の要素単位 store に戻ります。チェックサムは従来と同じ32-bit word と位置の順で計算します（`sycl/src/kernels/cuda/elementwise.dp.cpp:591-613,735-788`）。

`doorbell_publish_res()` もフラグを渡しますが、resident miss の通常経路（`STRATA_DOORBELL_CHECK` が無効）では kernel が `x` を要素単位で書くため、この paired store は使われません。`STRATA_DOORBELL_CHECK` が有効な full-payload 経路では `dbx_publish_x()` を通ります（`sycl/src/kernels/cuda/elementwise.dp.cpp:666-709,790-816`）。

### Device-plan 結果の mapped read

`copy_or_zero_from_mapped()` はフラグを kernel に渡します。skip flag と `value` が一致すると出力をゼロにします。一致しない場合、フラグが有効なら mapped source の `float4` を `load_mapped_float4()` で読みます。この関数は `float4` を2個の64-bit wordとして読み、無効なら従来の `float4` load を使います。この関数は Verifier の device-plan 経路で、CPU miss 結果を mapped memory から取り込む箇所に呼ばれます（`sycl/src/kernels/cuda/verify_kernels.dp.cpp:2347-2360,2434-2456`; 呼び出し: `sycl/src/core/verify.cpp:1478-1481`）。

## 実行時の詳細

フラグを読むソース上の共通箇所は `a770_fast()` の1か所です。router の選択は `router_top10()` の呼び出しごとに cached 判定値を参照します。doorbell と mapped read では呼び出し元が cached 判定値を kernel 引数にコピーし、その kernel の実行中は同じ値を使います。router の fast 経路は `launch_sycl_fast<false>()` で、他の router 条件では通常 kernel に fallback します（`sycl/src/kernels/cuda/router_top10.dp.cpp:74-84,647-676,679-686`）。

値が未設定または無効なら、router、doorbell store、mapped read はそれぞれの従来経路を使います。フラグ専用のログ、警告、エラー出力は見つかりません。SYCL のテスト登録にはこの変数を有効にして router と payload pair のテストを実行する設定があります（`sycl/CMakeLists.txt:362-369`）。

## 資料との照合

`docs/A770_SPEED_SPEC.md:47-59` は「fast router plus borrowing and paired mapped transfers」を含む A770 構成で、warm decode 13.5、11.9、12.3 tok/s と記載し、router 単体では256 experts/top-10の時間が395.47 µsから118.62 µsになり、結果がbitwise一致したとしています。これは複数機能を含む構成の測定であり、この環境変数単独の速度効果としては切り分けられません。文書では測定条件を超えた性能保証はできません。

## 根拠

- 値の読み取りと cache: `sycl/include/strata/sycl_doorbell.hpp:20-25`
- fast router の条件と選択: `sycl/src/kernels/cuda/router_top10.dp.cpp:74-84,647-686`
- doorbell の paired store と checksum: `sycl/src/kernels/cuda/elementwise.dp.cpp:571-614,637-709,735-816`
- mapped `float4` read と device-plan 呼び出し: `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2347-2360,2434-2456`, `sycl/src/core/verify.cpp:1478-1481`
- テスト環境設定: `sycl/CMakeLists.txt:362-369`
- 測定資料: `docs/A770_SPEED_SPEC.md:47-59`
