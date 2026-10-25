# `STRATA_MTP_HIP_PRIO`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

HIP バックエンドの MTP drafter が使う非同期ストリームを、可能なら最高優先度で作成するかを制御します。対象は `src/core/mtp.cpp` の `MtpDrafter::load()` にある HIP 分岐です。CUDA と Metal の経路ではこの変数を読みません。

MTP を使う生成経路では drafter の処理が `cs_` 上で実行されます。変数が有効で HIP の優先度ストリーム作成にも成功すると、その `cs_` を最高優先度指定で作ります。優先度のストリームを作れない場合は通常の非同期ストリーム作成へフォールバックします。

## 値と判定

環境変数が未設定または空文字なら、現在の HIP device のアーキテクチャを調べ、`gfx1200` または `gfx1201` なら有効、それ以外または device 情報を取得できない場合は無効です。アーキテクチャ名の後ろに `:...` が付く表記も、この2名称として認識します。

空でない値は `std::atoi()` で変換し、結果が 0 以外なら有効、0 なら無効です。文字列全体の数値 parse ではありません。

| 値 | 判定 |
|---|---|
| 未設定、空文字 | gfx1200/gfx1201 のとき有効。それ以外は無効 |
| `1`、`2`、`-1` | `atoi` の結果が非0なので有効 |
| `0`、`0suffix`、`nonnumeric` | `atoi` の結果が0なので無効 |
| `1suffix`、` 1tail` | 先頭から `atoi` が読む整数が非0なので有効 |

空文字は明示的な無効指定ではなく、自動判定に入ります。空白の扱い、整数部分の後ろの文字、大文字小文字は独自に検査せず、`atoi` の変換規則に従います。値の判定結果は関数内の `static const bool` に保存されます。最初の判定後にプロセス環境を変更しても再評価されません。

## 有効になる条件

- `STRATA_USE_HIP` でビルドされ、`STRATA_HIP_GFX906` ではないこと。GFX906 互換ビルド、CUDA、Metal ではこの変数による判定はありません。
- MTP drafter の `MtpDrafter::load()` が呼ばれること。生成側では `--mtp` の指定があり、`--spec` が2未満でない場合に MTP をロードします。`--mtp` がなければこのストリーム設定処理は通りません。
- 値が有効で、`hipDeviceGetStreamPriorityRange()` が成功し、`hipStreamCreateWithPriority()` も成功すること。優先度取得または優先度ストリーム作成が失敗すると、通常優先度の非同期ストリームを作成します。

## 実行時の詳細

`MtpDrafter::load()` は HIP 経路でまず現在の device id を保存し、バッファ確保後に `cs_` を作成します。変数の判定はこのストリーム作成処理内で行われ、初回は unset/空文字の場合に device property も取得します。有効なら `hipDeviceGetStreamPriorityRange(&lo, &hi)` で範囲を取得し、`hi` を `hipStreamCreateWithPriority(&cs_, hipStreamNonBlocking, hi)` に渡します。無効または優先度ストリームの作成失敗時は `cudaStreamCreateWithFlags(&cs_, cudaStreamNonBlocking)` を使います。通常ストリームも作成できなければ `load()` は `mtp: stream` エラーで失敗します。優先度 API の失敗自体は通常ストリームへの fallback となり、それ専用の警告ログはありません。

HIP 分岐は `!STRATA_HIP_GFX906` の条件付きコンパイルです。`gfx_arch_is_gfx12()` は `gfx1200` と `gfx1201` の完全なアーキテクチャ名（任意の `:feature` suffix 付き）だけを受け入れます。ソースコメントは、この設定の狙いを drafter stream の優先度引き上げとして説明していますが、コメントが参照する `notes-latency.md` は調査対象内に見つからず、`docs/DETAILS.md` にもこの変数の測定記載はありません。そのため性能値や他の ROCm スケジューリング動作はここでは主張しません。

## 根拠

- `src/core/mtp.cpp:249-264` — `MtpDrafter::load()` と対象デバイスの保存。
- `src/core/mtp.cpp:434-464` — CUDA の別判定、HIP 専用コンパイル条件、環境変数 parse、優先度指定ストリームと通常ストリームへの fallback。
- `include/strata/kernels/gfx_arch.hpp:15-20,35-36` — device 名の照合方法と gfx1200/gfx1201 判定。
- `src/program/generate.cpp:4611-4629` — `--mtp` が指定され、`--spec < 2` でない場合に drafter をロードする呼び出し。
- `include/strata/core/mtp.hpp:87-100` — drafter の stream と draft/prefill API。
- `CMakeLists.txt:64-67,128-143`、`cmake/hip_backend.cmake:89` — HIP と GFX906 互換ビルドの定義。
