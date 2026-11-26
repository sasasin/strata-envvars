# `STRATA_MMVQ_WIDE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL backend の Strata 独自 native MMVQ で、Q6_K 行列に 16-byte load の wide kernel を選択するかを制御する。既定は有効。無効にすると wide kernel の分岐を飛ばし、後続の rowwarp 条件または通常の Q6_K MMVQ 経路へ進む。Q4_K など他の形式の wide kernel を制御する変数ではない。読み取りと選択は `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp` の `g_q6k_wide` と `native_q6_k_mmvq` にある（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2185,3935-3978`）。

## 値と判定

ファイルスコープの `g_q6k_wide` 初期化時に `std::getenv` を使い、未設定なら `true`、設定済みなら `std::atoi(...) != 0` とする。明示的な空文字は `atoi("") == 0` となり無効。文字列全体の厳密な数値検証はなく、`atoi` が先頭から変換できた整数で判定する。先頭空白と符号は `atoi` の規則で扱われ、後続文字は無視される。大文字小文字の比較はない。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL `strata_kernels` にこの実装を含むビルド | 有効 | `1`, `-1`, `2`, `1junk`（`atoi` の結果が非ゼロ） | `0`, `0junk`, `true`, `false`, 空文字、整数に変換できない文字列（結果がゼロ） |

値は boolean 化するだけで、範囲 clamp や無効文字列の警告はない。`atoi` の整数範囲を超える入力は C の変換規則上安全な値として扱えないため、利用可能な値として保証されない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2185`）。

## 有効になる条件

- 対象は SYCL backend の Strata native MMVQ 経路。`engine/sycl/CMakeLists.txt` は `src/kernels/cuda/native_mmvq.dp.cpp` を SYCL kernel source として `strata_kernels` に含める（`engine/sycl/CMakeLists.txt:273-280`）。
- 行列形式が Q6_K であること。汎用 `native_mmvq` は GGML type `14` を `native_q6_k_mmvq` に振り分ける（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4204-4217`）。
- Q6_K の packed / planar 登録済み行列は wide 判定より先にそれぞれの kernel で処理されるため、この変数はその呼び出しでは効かない（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3935-3938`）。
- wide 分岐には `1 <= ncols <= wide_maxc`, `n_in % 256 == 0`, `n_out >= wide_min` も必要。`wide_maxc` と `wide_min` は `STRATA_MMVQ_WIDE_MAXC` / `STRATA_MMVQ_WIDE_MIN` で指定でき、未設定時は `STRATA_MMVQ_A2` の状態に応じてそれぞれ 8/0（A2 有効）または 4/4096（A2 無効）になる。これらの読み取り値は各関数内 `static` に保存される（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1545-1548,3943-3955`）。
- 上の wide 条件を満たさない場合でも、`ncols` が 1〜4、`n_in` が 256 の倍数で、`STRATA_MMVQ_RPW` の値が正なら rowwarp 経路が後続で選ばれうる。そうでなければ通常の Q6_K 経路へ進む（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3958-3978`）。
- CLI 引数による優先上書きはこの読み取り経路にない。ベンチマーク実行ファイルは比較測定中に setter で一時的に off/on し、比較後に環境変数を読み直して値を復元する（`engine/sycl/src/kernels/mmvq_bench.cpp:29-38`）。

## 実行時の詳細

通常の SYCL engine では、翻訳単位のファイルスコープ変数として初期化され、プロセス開始後に環境を変更してもこの値は再読込されない。`native_q6_k_mmvq` はまず packed / planar 行列を判定し、そのどちらでもなければ `g_q6k_wide` と形状条件を調べる。条件を満たすと `ncols` ごとの `launch_q6k_wide` を起動して戻る。wide 分岐に入らなければ rowwarp を試し、続いて通常 kernel に進む。`ncols > 1` の通常経路は multi kernel、1 列は通常の Q6_K kernel を使う（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3935-4005`）。

ベンチマークの `mmvq_bench` では、環境値の初期化後に correctness 比較のため wide を一度無効化・有効化し、その後 `STRATA_MMVQ_WIDE` を再度読み取って測定用の選択値に戻す。このためこのベンチマーク内に限り、比較用 setter の変更後に環境を再参照する箇所がある（`engine/sycl/src/kernels/mmvq_bench.cpp:29-50`）。

## ログと測定値

この変数の値や wide kernel 選択を直接知らせるログ、警告、終了経路は見つからない。測定値は記載しない。

## 根拠

- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2185` — 環境値の初期化。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2876-2898,3007-3028,3935-3978` — packed / planar の先行処理、Q6_K wide の形状ゲートと kernel 選択、fallback。
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4204-4217` — Q6_K 形式から対象関数への dispatch。
- `engine/sycl/src/kernels/mmvq_bench.cpp:29-50` — ベンチマーク内の一時切替と環境値の復元。
- `engine/sycl/CMakeLists.txt:141-149,273-286` — `.cu` 名の SYCL source 解決と `strata_kernels` への登録。

`terminal/data/settings-register.json:25400-25429` にも名前と読み取り座標が載るが、これは設定レジストリのメタデータであり、追加の実行時読み取り箇所ではない。
