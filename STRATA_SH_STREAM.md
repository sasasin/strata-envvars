# `STRATA_SH_STREAM`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Verifier の MoE layer で、shared expert の計算を routed expert の処理と別 GPU stream / SYCL queue へ分岐させるかを選びます。有効な場合、shared expert の入力準備と計算を `sh_cs_` へ送り、通常の verifier queue では routed expert の計画・処理を進めます。shared expert 側の完了 event を通常側の queue が待ってから combine へ進みます。無効の場合は shared expert も通常側の queue で処理します。実装は `src/core/verify.cpp` と SYCL 移植版 `sycl/src/core/verify.cpp` にあります。

## 値と判定

文字列全体や数値としての parse は行わず、`getenv()` が返す文字列の先頭文字だけを見ます。空文字が設定されている場合は `v[0] == '\0'` なので有効側になります。

| 状態 | CUDA | HIP | HIP gfx1151 (Strix Halo) |
|---|---|---|---|
| 変数 unset | 有効 | 無効 | 通常は有効。アーキテクチャ既定値が先に `1` を設定する |
| 設定値の先頭が `0` | 無効 | 無効 | 無効。明示設定は既定値より優先 |
| その他の設定値 | 有効 | 有効 | 有効 |

したがって `0`, `0anything` は無効、`1`, `true`, `false`, 空文字は有効です。大文字小文字、空白、後続文字列は検査されません。直接の判定箇所は両 backend とも `v[0] != '0'` です（`src/core/verify.cpp:192-202`, `sycl/src/core/verify.cpp:162-172`）。

HIP では gfx1151 のアーキテクチャ既定値表が `STRATA_SH_STREAM=1` を登録します。適用処理は変数が既に存在すれば値を問わず維持し、未設定の場合だけ設定します。空文字や `0` も「既に設定済み」として維持されます。既定値の適用を無効にする `STRATA_GFX1151_DEFAULTS` の先頭文字が `0` なら表そのものを適用しません（`src/core/arch_defaults.cpp:32-35,45-57,61-70`）。

## 有効になる条件

- CUDA build は unset で既定有効、HIP build は unset で既定無効です。HIP gfx1151 は上記のアーキテクチャ既定値で有効になります。既定値表は HIP の CLI 起動処理で GPU の `gcnArchName` を取得した後、engine が環境変数を初回評価する前に適用されます（`src/program/generate.cpp:2190-2196`; SYCL 側 `sycl/src/program/generate.cpp:1999-2005`）。
- 有効値でも、Verifier が profiling 中なら fork しません。CUDA は `STRATA_VERIFY_PROFILE` が設定されている場合に profiling と判定し、SYCL も同じ設定有無判定を使います。空文字も設定済みです（`src/core/verify.cpp:711-715`; `sycl/src/core/verify.cpp:636-648`）。
- CUDA は別 stream と fork/join event が存在する場合に限って fork します（`src/core/verify.cpp:1424-1426`）。SYCL はさらに stepped verifier ではなく、共有 queue が in-order queue ではないことを要求します（`sycl/src/core/verify.cpp:1293-1297`）。
- `STRATA_SH_FORK_LATE` は有効な fork を layer の早い位置で開始するか、routed-expert の doorbell を公開した後に開始するかを変えます。これは fork 自体の有効・無効を変える別の設定です（CUDA `src/core/verify.cpp:1418-1429,1503-1506`; SYCL `sycl/src/core/verify.cpp:1287-1300,1361-1364`）。

## 実行時の詳細

判定結果は `sh_stream_on()` 内の `static const bool` に初回呼び出し時に保存されます。後からプロセス環境を変更しても再判定されません。HIP gfx1151 の既定値はこの初回判定前に投入されます。

Verifier の各対象 layer/group で fork を使うと、shared expert 用入力の変換と `shared_expert_multi()` を別 stream/queue に発行します。routed expert 側の処理を続けた後、通常 stream/queue が join event を待ち、shared expert の結果を使う combine へ進みます。fork している間は shared expert 用に独立した q8_1 入力を使い、`STRATA_VERIFY_QDEDUP` による routed/shared 入力の重複排除は使いません（CUDA `src/core/verify.cpp:1424-1429,1521-1542,1647-1655`; SYCL `sycl/src/core/verify.cpp:1293-1300,1380-1400,1495-1505`）。

この変数自体による専用ログはありません。gfx1151 の既定値表が1個以上の switch を投入した場合は `strata: gfx1151 (Strix Halo): ... exact speed switches on by default ...` の一覧に `SH_STREAM` が含まれます（`src/core/arch_defaults.cpp:72-79`）。

## 文書との照合

`docs/AMD_HIP.md:213-217` は HIP で通常 off、gfx1151 を例外とし、RX 6900 XT Linux と RX 6800 Windows、R9700 の測定方向が異なることを記しています。`docs/STRIX_HALO.md:98` は gfx1151 で有効にする設定と decode 測定値を記します。これらは文書に記録された特定環境の測定であり、他の GPU での性能を保証するものではありません。現行コードの値判定と gfx1151 既定値は上記実装箇所を根拠としています。

## 根拠

- `src/core/verify.cpp:184-202,711-715,1418-1429,1521-1542,1647-1655`
- `sycl/src/core/verify.cpp:154-172,636-648,1287-1300,1380-1400,1495-1505`
- `src/core/arch_defaults.cpp:32-35,45-57,61-79`
- `src/program/generate.cpp:2190-2196`; `sycl/src/program/generate.cpp:1999-2005`
- `docs/AMD_HIP.md:213-217`; `docs/STRIX_HALO.md:98`
