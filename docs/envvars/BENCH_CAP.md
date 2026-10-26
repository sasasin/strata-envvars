# `BENCH_CAP`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

`native_expert_bench` が GPU grouped-expert カーネルへ渡すグループ容量を、実データのグループ数 `G` より大きくできます。実データがない余分なグループ行を含めた launch のコストを測るためのベンチマーク用調整値です。通常の Strata 推論エンジンからこの名前を読む箇所はありません。

## 値と判定

値は `std::atoi` で整数に変換され、実グループ数 `G` との大きい方が `CAP` になります。

| 状態・値 | `atoi` の結果 | `CAP` |
|---|---:|---:|
| unset | 変換しない | `G` |
| 空文字 | 0 | `G` |
| 整数として 0 以下 | 0 以下 | `G`（`G >= 1`）|
| 整数として `G` より大きい値 | その値 | その値 |
| 数字で始まらない文字列 | 0 | `G` |
| 数字の後ろに文字が続く文字列 | 数字部分 | `max(G, 数字部分)` |

`atoi` は先頭の空白と符号を許し、数値部分の後ろは検査しません。たとえば `"  +12tail"` は 12、`"tail12"` は 0 として扱われます。大文字小文字の比較はありません。変換可能な `int` の範囲を超える入力の結果は移植可能な値として保証されません。

## 有効になる条件

- CUDA または HIP を有効にしてビルドしたとき、CMake は `native_expert_bench` 実行ファイルを定義します。環境変数を読むのはこの実行ファイル内だけです。
- `native_expert_bench` を起動し、引数検査を通って GGUF の各 layer を処理するときに参照されます。通常の Strata engine や他のベンチマークには適用されません。
- ソースでは CUDA/HIP の有効時に同じ `src/kernels/native_expert_bench.cpp` をターゲットへ追加します。別の SYCL 実装 `sycl/src/kernels/native_expert_bench.cpp` には `BENCH_CAP` の読み取りがありません。

## 実行時の詳細

引数から `G`（実グループ数）と `T`（各グループの token 数）を読み、`G >= 1` などの検査を通った後、各 layer の処理で環境変数を読みます。判定は `static` にキャッシュされないため、layer ごとに評価式が実行されます。プロセス内に環境変数を書き換える処理はありません。

`NE = G * T` に対し、実行コードは次の容量を使います。

- `CAP = max(G, BENCH_CAP の atoi 結果)`（unset 時は `G`）
- `CAPE = max(NE, CAP)`

scratch 領域を `CAPE` に応じて確保し、`native_expert_grouped` には `CAP` と `CAPE` を渡します。したがって `BENCH_CAP` は実データの `G`、`NE`、入力テンソルや出力エントリ数を増やさず、カーネルに渡すグループ容量と scratch 容量を広げます。`G` より大きい値では、grouped kernel の一部 launch が `cap_groups` に基づく追加の行を持つため、その空行分を含む実行時間をベンチマークできます。値が大きいほど scratch の確保量も増えます。

`docs/DETAILS.md` および `docs/` の調査では、この変数の追加説明や性能測定値は確認できませんでした。ソースコメントは「engine が渡す `n_tokens * K` 個の候補グループに対して、実データ `G` 個を置いたときの empty block rows のコストを測る」と説明していますが、ここでは実装から確認できる容量・launch の変更だけを記載しています。

## 根拠

- `src/kernels/native_expert_bench.cpp:31-47` — ベンチマークの引数、`G`/`T` の取得と最低値検査。
- `src/kernels/native_expert_bench.cpp:86-101,123-127` — `BENCH_CAP` の読み取り、`CAP`/`CAPE`、scratch 確保、kernel 呼び出し。
- `src/kernels/cuda/iq_kernels.cu:4355-4358,5071-5083,5140-5144,5254-5258` — scratch サイズ式、capacity 引数の使用、group grid の容量依存。
- `CMakeLists.txt:2151-2158` — CUDA または HIP ビルド時に限った `native_expert_bench` ターゲット。
- `sycl/src/kernels/native_expert_bench.cpp` — 同名 SYCL ベンチマーク実装に `BENCH_CAP` 読み取りがないこと。
