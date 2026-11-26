# `STRATA_SELECT_OLD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA prefill のブロックスコア計算で、通常の tensor-core / GEMM scorer を使わず、従来の warp scorer `qsa_block_scores` を選びます。スコア計算後の top-k 選択 `qsa_block_topk` は同じ呼び出しのままです。設定値の内容ではなく、変数が存在するかだけで切り替わります。CUDA/HIP 系 prefill の通常経路と layer-major 経路、SYCL prefill 経路に読み取りがあります（`engine/src/prefill/prefill.cpp:5377-5392, 9450-9457`; `engine/sycl/src/prefill/prefill.cpp:3674-3675, 3713-3719`）。

## 値と判定

3 箇所の判定はいずれも `std::getenv("STRATA_SELECT_OLD") != nullptr` で、各関数内 `static const bool` に保存されます。値の parse、数値範囲・文字列形式の検証、無効値の fallback はありません。

| 条件（build / 経路） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP 系 prefill の通常経路および layer-major 経路 | `old_sel == false`。新 scorer を試す | 任意の設定値。`1`、`0`、`false`、空文字も `old_sel == true` | なし（値が存在すれば有効） |
| SYCL prefill | `old_sel == false`。他の条件に応じて GEMM / tensor-core scorer を試す | 任意の設定値。`1`、`0`、`false`、空文字も `old_sel == true` | なし（値が存在すれば有効） |

大文字小文字、前後の空白、数値としての妥当性は判定しません。`docs/SETTINGS.md` の「on / off」表記とは異なり、実装は `0` や `false` を無効値として扱いません（`engine/src/prefill/prefill.cpp:5379, 9450`; `engine/sycl/src/prefill/prefill.cpp:3675`; `docs/SETTINGS.md:463`）。

## 有効になる条件

- QSA の selection を行う Strata の prefill 経路に到達すること。読み取りは selection バッチ内にあり、別の処理経路や QSA selection を行わない実行では、この変数による選択は発生しません（`engine/src/prefill/prefill.cpp:5371-5379, 9444-9451`; `engine/sycl/src/prefill/prefill.cpp:3665-3675`）。
- 値の設定は scorer の選択に作用します。CUDA/HIP 系通常経路では `old_sel` が true だと two-pass scorer 呼び出し条件を満たさず、続いて tensor-core scorer を短絡して warp scorer に進みます（`engine/src/prefill/prefill.cpp:5380-5392`）。layer-major 経路も tensor-core scorer を短絡して warp scorer を呼びます（同 `9450-9457`）。
- SYCL では GEMM scorer に必要な `sel_gemm && !old_sel` が false になるためその GEMM 経路を使わず、tensor-core scorer も短絡して warp scorer に進みます（`engine/sycl/src/prefill/prefill.cpp:3687-3693, 3713-3719`）。
- 変数専用の CLI 引数、モデル状態、GPU 世代による値判定はありません。新 scorer が未対応条件で `false` を返す場合にもコードは warp scorer に fallback するため、その場合は変数の有無で実行 scorer が変わらないことがあります（`engine/include/strata/kernels/qsa_select.hpp:71-76`; `engine/src/prefill/prefill.cpp:5387-5391`; `engine/sycl/src/prefill/prefill.cpp:3713-3717`）。

## 実行時の詳細

環境値は各読み取り箇所の `static const bool` が初めて実行される時に評価され、その後はプロセス内でキャッシュされます。該当する静的変数はソース上 3 箇所に別々にあるため、それぞれの経路で初回到達時に評価されます。初回評価後に環境を変更しても、その箇所の判定には反映されません（`engine/src/prefill/prefill.cpp:5379, 9450`; `engine/sycl/src/prefill/prefill.cpp:3675`）。

選ばれた scorer は各 query の QSA block scores を計算し、その結果を既存の `qsa_block_topk` に渡します。従って変数が直接切り替えるのはスコア計算経路であり、top-k の呼び出し自体ではありません。実装資料では tensor-core scorer を 3xTF32 の近似精度（bitwise 一致ではない）とし、warp scorer と区別しています。選択 ID やモデル出力が常に同一とは、このコードからは断定できません（`engine/include/strata/kernels/qsa_select.hpp:8-15, 71-76`; `engine/src/prefill/prefill.cpp:5387-5393, 9451-9457`; `engine/sycl/src/prefill/prefill.cpp:3713-3719`）。

SYCL で変数が未設定かつ GEMM 条件を満たす場合、GEMM の実行が例外になると stderr に `prefill: the GEMM block scores failed (%s); the warp kernel instead\n` を初回のみ出して warp scorer に fallback します。`STRATA_SELECT_OLD` を設定して GEMM 経路自体を選ばない場合、この GEMM 例外ログはその理由では発生しません（`engine/sycl/src/prefill/prefill.cpp:3691-3717`）。

## ログと測定値

この変数の設定・未設定そのものを通知するログは見つかりませんでした。SYCL の GEMM 例外時のログは上記のとおりです。比較測定値は現行ソースの根拠として確認できなかったため記載しません。

## 根拠

- `engine/src/prefill/prefill.cpp:5371-5393` — 通常 prefill での値の読み取り、two-pass / tensor-core scorer の抑止、warp scorer と top-k の呼び出し。
- `engine/src/prefill/prefill.cpp:9444-9457` — layer-major prefill の読み取りと scorer 分岐。
- `engine/sycl/src/prefill/prefill.cpp:3674-3719` — SYCL の読み取り、GEMM 条件、tensor-core scorer と warp fallback。
- `engine/include/strata/kernels/qsa_select.hpp:71-76` — tensor-core scorer の対応条件と warp scorer との精度特性。
