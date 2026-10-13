# `STRATA_DOORBELL_STORE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

HIP backend の verifier が MoE expert 用の payload を doorbell 経由で公開するとき、sequence word を GPU 側で read-modify-write（既存値を読み、1増やして書き戻す）する代わりに、現在の verifier step に対応する値を直接書くかを選びます。コメント上の目的は、doorbell の更新で PCIe 越しにホストメモリを読む処理をなくす A/B 切り替えです。

この名前は CUDA/HIP kernel と移植済み SYCL tree に記述がありますが、実際の読み取り・使用箇所は `STRATA_USE_HIP` のコンパイル条件内です。CUDA build と独立した SYCL build ではこの環境変数による切り替えは有効になりません。`STRATA_HIP_GFX906` は `STRATA_USE_HIP` とは別の build 条件なので、このコード上では対象外です。

## 値と判定

`src/core/verify.cpp` と `sycl/src/core/verify.cpp` の `env_on()` は、値を数値や文字列全体として parse せず、未設定でないこと、空文字でないこと、先頭文字が `'0'` でないことを判定します。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効 |
| それ以外の先頭文字（例: `1`, `true`, ` 1`, `-1`, `2abc`） | 有効 |

判定結果は HIP build のグローバル `const bool g_doorbell_store` に初期化時に保存されます。したがって、実行中に環境を書き換えても再評価されません。CLI 引数や設定ファイルとの優先順位はありません。

## 有効になる条件

- `STRATA_USE_HIP` を定義してビルドした HIP backend であることが必要です。CUDA build では `g_doorbell_store` と分岐の両方がコンパイルされません。
- verifier の MoE 処理で `ar_on()` が false となり、通常の plan / doorbell 分岐へ進む必要があります。`ar_on()` 側ではこの doorbell publish 分岐を通りません。
- 値が有効なときは、`remote_opt_` や `always_publish_` の状態にかかわらず `doorbell_publish_value()` が先に選ばれます。無効時はこれらの状態に応じて `doorbell_publish()` または residency-aware な `doorbell_publish_res()` が選ばれます。

## 実行時の詳細

verifier は各 layer/group の処理で `value = (l - lb_) * G + grp + 1` を作り、`doorbell_publish_value()` に渡します。この関数の kernel は activation `x`、expert ID、routing weight を出力先へコピーし、system fence と block/work-group 同期の後、sequence word にその `value` を書きます。通常の `doorbell_publish()` は同じ payload を公開した後、sequence word の現在値を読み、1を加えて書き戻します。値を直接書く経路は既知の step 値を使い、sequence word の読み戻しを省きます（CUDA/HIP kernel は `src/kernels/cuda/elementwise.cu:345-375`、SYCL移植版は `sycl/src/kernels/cuda/elementwise.dp.cpp:711-760`）。

通常経路で呼ばれる `doorbell_publish_res()` は residency-aware な公開処理です。有効時は full-payload の `doorbell_publish_value()` に置き換わるため、環境変数が無効の場合と payload 公開の条件も同一とは限りません。ここで確認できるコードでは、この変数による専用の警告やエラー出力はありません。`STRATA_VERIFY_TRACE` が有効なときに限り、HIP trace 初期化ログに `doorbell stored` または `doorbell incremented` として判定結果が表示されます。

## 文書との照合

`docs/DETAILS.md`、`docs/INTEL.md` を含む Strata の Markdown 文書に、この環境変数名の説明は見つかりませんでした。read-modify-write を省く意図はソースコメント（`src/core/verify.cpp:169-175`、`src/kernels/cuda/elementwise.cu:353-355`）にありますが、当該 commit の資料に測定条件や性能値は確認できないため、速度効果は記載しません。

## 根拠

- `src/core/verify.cpp:169-179` — `env_on()` の判定と HIP build に限定されたグローバル値。
- `src/core/verify.cpp:701-709` — `STRATA_VERIFY_TRACE` 有効時の `stored` / `incremented` 表示。
- `src/core/verify.cpp:1477-1502` — `ar_on()` での分岐、doorbell 選択、step 値。
- `src/kernels/cuda/elementwise.cu:345-375` — 通常の加算方式と値を直接書く方式、payload の公開。
- `sycl/src/core/verify.cpp:89-99,626-634,1335-1359` — 同様の移植コード。ただし変数の定義・利用は `STRATA_USE_HIP` 条件内。
- `sycl/src/kernels/cuda/elementwise.dp.cpp:711-760` — 移植版 `doorbell_publish_value()` kernel と launcher。
- `include/strata/kernels/elementwise.hpp:116-126` — publish API と `STRATA_DOORBELL_STORE` に関する宣言コメント。
- `CMakeLists.txt:59-72`、`cmake/hip_backend.cmake:89` — HIP build option と `STRATA_USE_HIP` compile definition。
