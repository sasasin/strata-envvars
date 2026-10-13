# `STRATA_MTP_PRIORITY`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの内部動作は対象外。

## 役割

CUDA 版で MTP drafter の `cs_` stream を作るとき、通常の non-blocking stream の代わりにデバイスが報告する最高優先度を指定するかを制御します。対象コードのコメントでは、`--pipeline-windows 2` の forcing graphs で drafter の chain と別 stage の window が同じ GPU を使う場面を理由に挙げています。

## 値と判定

`std::getenv()` の結果を `std::atoi()` に渡し、結果が 0 以外なら有効です。文字列全体の検証はありません。`atoi` は先頭の空白と符号を許し、先頭から読める10進整数部分を変換して後続文字を無視します。数字で始まらない値や空文字は 0 になります。

| 設定 | `hi_prio` |
|---|---:|
| 未設定 | 有効（既定） |
| 空文字、`0`、`0suffix`、`true` | 無効 |
| `1`、`1suffix`、`-1`、` 2tail` | 有効 |

## 有効になる条件

- 通常の CUDA 実装では、変数の判定が有効で、`force_on_` が true、かつ `cudaDeviceGetStreamPriorityRange()` が成功したときに限り、`cudaStreamCreateWithPriority()` へデバイスの最高優先度 `prio_hi` を渡します。
- `force_on_` は呼び出し元が `--pipeline-windows` を 2 以上にしたときに設定します。通常 MTP をロードするには `--mtp` が必要です。`--mtp` は `--spec T` が 2 未満なら無視されます。
- 優先 stream の作成に失敗した場合、または条件が満たされない場合は通常の `cudaStreamCreateWithFlags(..., cudaStreamNonBlocking)` に進みます。これも失敗すると load は `mtp: stream` エラーで失敗します。
- `STRATA_USE_HIP` または `STRATA_HIP_GFX906` が定義された通常実装では、環境変数を読むコードがコンパイル対象から外れ、通常 stream が使われます。ソースコメントも HIP は既定優先度としています。
- SYCL 実装では `STRATA_USE_HIP` が未定義なら同じ値判定を行いますが、SYCL の queue は優先度オプションを無視すると実装コメントにあります。有効時と fallback のどちらも `create_queue(true)` を呼ぶため、優先度の指定としての実効性はありません。有効時の最初の queue 作成に失敗した場合だけ、同じ作成を再試行する経路差が残ります。

## 実行時の詳細

値は `MtpDrafter::load()` 内の関数ローカル `static const bool` で一度評価されます。そのため、同じ実行ファイル内で最初にこの行へ到達した後に環境を書き換えても再評価されません。`force_on_` が false の場合も、CUDA/SYCL の当該ビルドでこの行へ到達すれば値自体は評価されますが、優先度付き作成の条件には入りません。

CUDA では優先度付き stream の作成を試した後に `cudaGetLastError()` を呼び、優先度付き stream を得られなければ通常の non-blocking stream を作成します。変数判定や優先度付き作成の成功・失敗を報告する専用ログはありません。stream の失敗時は呼び出し元が load error を stderr に出します。

## 根拠

- `src/core/mtp.cpp:244-252` — `MtpDrafter::load()` の開始と初期検査。
- `src/core/mtp.cpp:422-440` — 変数の `atoi` 判定、CUDA の優先度付き stream と fallback、HIP の compile guard。
- `sycl/src/core/mtp.cpp:489-517` — SYCL 側の判定、queue 優先度非対応コメント、fallback。
- `src/program/generate.cpp:4436-4453` — `--mtp` の適用、`--pipeline-windows >= 2` による `set_force_capture(true)` と load。
- `include/strata/core/mtp.hpp:121-130` — forcing chain と既定優先度についての宣言コメント。
