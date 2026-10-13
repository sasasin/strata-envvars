# `STRATA_GDN_KEYHEAD`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

Gated DeltaNet (GDN) prefill recurrence で、1つの key head を共有する value head 群をまとめて計算する `gdn_rec_kh_kernel` を選ぶ制御です。対象コードは CUDA と SYCL にあります。CUDA では環境変数が未設定ならデバイスの compute capability と occupancy から自動選択し、この変数でその選択を抑止できます。SYCL では opt-in で、値が `1` と parse されたときだけ選びます。

このカーネルは GDN recurrence の代替実装です。環境変数を設定しても、GDN prefill が実行されない場合や、より優先される経路が選ばれた場合には影響しません。

## 値と判定

両 backend とも `std::atoi` を使い、文字列全体の比較や厳密な数値 parse はしません。先頭の空白と符号を含む `atoi` の変換規則に従い、数値以降の文字列は無視されます。未設定、空文字、数値に変換できない文字列は `atoi` の結果が 0 です。

| 設定値 | CUDA | SYCL |
| --- | --- | --- |
| 未設定、空文字、`abc`、`0`、`00`、`0tail` | 自動選択を許す | 選択しない |
| `1`、`01`、`1tail` | 自動選択を許す | 選択する |
| `2`、`-1`、`2tail` | 自動選択を許す | 選択しない |

CUDA は `atoi(v) == 0` のときだけ明示的な抑止フラグを立てます。したがって非ゼロ値はカーネルを強制する指定ではなく、ハードウェア適格性の自動判定を残す指定です。SYCL は `atoi(v) == 1` のときだけ有効にします。

## 有効になる条件

- **CUDA**: `STRATA_GDN_KEYHEAD` が 0 と parse されず、現在の GPU で compute capability major が 8 以上、かつ `cudaOccupancyMaxActiveBlocksPerMultiprocessor` が返す常駐可能 block 数と SM 数の積が `HK * NCB` 以上である必要があります。条件を満たさなければ、値が非ゼロでも key-head kernel は選ばれません。現在の device を取得できない場合や device index が 64 以上の場合も選択しません。
- **SYCL**: 値が `atoi(...) == 1` であることが必要です。SYCL 側では CUDA の SM 数・occupancy 判定は行いません。
- **両 backend**: `STRATA_GDN_REC_HEADS` が設定されると serial recurrence 経路が選ばれ、key-head の選択を通りません。値そのものは判定されず、空文字や `0` でも「設定済み」です。また `T <= 0` のときも通常の recurrence variant では serial 側の分岐を通ります。
- **CUDA**: `STRATA_GDN_CHUNKED` が非ゼロで、長さ条件と scratch allocation などを満たして chunked recurrence が成功した場合は、その経路が先に選ばれ、key-head kernel は使いません。chunked 経路が使われない場合、`STRATA_GDN_PIPELINE` が未設定または `atoi(...) != 0` なら pipeline 経路に入り、そこではじめて key-head 判定が行われます。pipeline が無効なら通常の column recurrence を選びます。
- **SYCL**: `STRATA_GDN_PIPELINE` が未設定または `atoi(...) != 0` のときに限り key-head 判定を行います。0 と parse される場合は key-head kernel を含む pipeline 経路を使いません。
- HIP 用ビルドでは `gdn_keyhead_ok` とその呼び出しが `!defined(__HIPCC__)` 側にあるため、この変数は HIP の recurrence variant を選びません。

## 実行時の詳細

CUDA は `gdn_keyhead_ok()` の初回呼び出し時に環境値を `static const bool off` へ保存します。値を 0 と parse した場合は直ちに false を返します。それ以外は GPU ごとの `known[64]` に適格性判定を保存し、以後同じプロセス内では再判定しません。したがって初回評価後に環境値を変更しても反映されません。選択時には grid `HK * NCB` で `gdn_rec_kh_kernel` を起動し、その後に通常の GDN output norm kernel を起動します。

SYCL は同関数内の `static const bool on` に `atoi(v) == 1` の結果を初回評価時に保存します。選択時は `HK * NCB` の work-group 配置で `gdn_rec_kh_kernel` を投入し、後続の output norm kernel を実行します。初回評価後の環境値変更は反映されません。

環境変数専用のログや警告はこれらの分岐にはありません。kernel 実行後には既存の `check("gdn_recurrence")` が呼ばれます。

`docs/INTEL.md` は SYCL の B70 で `STRATA_GDN_KEYHEAD=1` を opt-in のままにし、prompt throughput を 727 tok/s 対 788 tok/s と記しています。また同文書は上流 PR #413 の parity test は NVIDIA の SM-holding bench であり SYCL では実行されていないと説明しています。これらは文書に記録された特定環境の測定・検証結果であり、他の GPU やモデルへの性能・出力特性を保証するものではありません。

## 根拠

- `src/prefill/kernels.cu:696-713` — CUDA の設定値判定、device ごとの compute capability / occupancy 条件と cache。
- `src/prefill/kernels.cu:1927-1994` — CUDA recurrence の優先経路、pipeline 条件、key-head kernel と output norm の起動。
- `sycl/src/prefill/kernels.dp.cpp:1228-1233` — SYCL の `atoi(...) == 1` 判定と初回値の cache。
- `sycl/src/prefill/kernels.dp.cpp:2603-2735` — SYCL recurrence の serial / pipeline 分岐、key-head kernel と output norm の投入。
- `src/prefill/kernels.cu:596-688`, `sycl/src/prefill/kernels.dp.cpp:1070-1219` — key-head recurrence kernel 実装。
- `src/prefill/prefill.cpp:2623`, `sycl/src/prefill/prefill.cpp:2906` — prefill の GDN 経路から `gdn_recurrence` を呼ぶ箇所。
- `docs/INTEL.md:642-666` — SYCL B70 での opt-in 状態、記録された throughput、および上流 parity test の制約。
