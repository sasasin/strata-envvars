# `--version`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（CUDA/HIP root CLI） |
| オプション | `--version` |
| 別名 | なし |
| 値 | 取らない |

## 役割

CUDA/HIP 版 Inkling-2-Mini エンジンのコンパイル時バージョン文字列を標準出力へ表示し、終了コード `0` で終了します。モデルや設定ファイルを指定せず、バージョンを確認するときに使います。`strata-inkling-metal` と `strata-inkling-sycl` は別の parser scope です。

## 使い方

```sh
strata-inkling --version
```

## 値と既定値

オプション値はありません。ソースでは `INKLING_VERSION` がビルド時に未定義なら `"0.1.66"` を既定値として定義します。ビルドで同マクロが上書きされる場合、表示値はその値になります。`--version` 自体の入力値検証はありません（`engine/src/inkling2/ink_main.cpp:28-30,385-387`）。

## 実行時の動作

引数を左から走査し、`--version` に到達すると `strata-inkling <バージョン>` を改行付きで stdout に出力して、その場で `main` から戻ります。後続の引数は解析されません。そのため、先行する未知オプションは先にエラーになりますが、`--version` の後ろに置いた未知オプションは検査されません（`engine/src/inkling2/ink_main.cpp:379-388,499-501`）。

この判定より前に、Linux かつ HIP ビルドでは NUMA policy の補助処理が実行され、必要な場合は stderr に情報または警告を出します（`engine/src/inkling2/ink_main.cpp:361-365`、`engine/include/strata/platform/numa_balancing.hpp:71-94`）。CUDA または CUDA EP のビルドでは、`CUDA_MODULE_LOADING` が未設定の場合に既定値をプロセス環境へ設定します。volta-forever が検出されて `LAZY` を設定した場合は stderr に通知します（`engine/src/inkling2/ink_main.cpp:366-370`、`engine/include/strata/core/volta_forever.hpp:74-94`）。これらの初期処理を除き、version 分岐後にモデル読込や生成処理は行いません。

## 適用条件と副作用

対象は索引上の `strata-inkling` CUDA/HIP root parser です。Metal と SYCL にも同名のフラグがありますが、別スコープです。索引はこの root option を登録しています（`docs/cli/README.md:1511-1514,1543-1545`）。

バージョン表示前の初期処理には、上記条件下でプロセス内 NUMA policy の変更や `CUDA_MODULE_LOADING` の設定があり得ます。ソース上では version 分岐からこれらの処理を避ける早期判定はありません。ファイル出力やネットワークアクセスはこの分岐にはありません。

## 出力とエラー

通常の出力は stdout の `strata-inkling <バージョン>` と改行、終了コード `0` です。NUMA 補助処理が診断を返した場合、および CUDA module loading の既定設定通知条件に該当する場合は、version 行より前に stderr 出力があり得ます。未知オプションが `--version` より前にあると `unknown option: <値>` を stderr に出し、コード `2` で終了します（`engine/src/inkling2/ink_main.cpp:362-369,385-387,499-501`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:28-30` — `INKLING_VERSION` のソース上の fallback。
- `engine/src/inkling2/ink_main.cpp:379-388` — 引数走査、値を取らない version 分岐、stdout 出力と即時終了。
- `engine/src/inkling2/ink_main.cpp:499-501` — 未知オプションの失敗経路。
- `engine/src/inkling2/ink_main.cpp:361-370` — parser より前の HIP/Linux NUMA 処理および CUDA module loading 処理。
- `engine/include/strata/platform/numa_balancing.hpp:71-94` — NUMA policy を適用する条件と診断文字列。
- `engine/include/strata/core/volta_forever.hpp:74-94` — CUDA module loading の環境変数設定条件。
- `docs/cli/README.md:1511-1545` — 対象コマンド階層と `--version` の索引リンク。
