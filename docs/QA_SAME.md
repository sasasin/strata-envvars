# `QA_SAME`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`QA_SAME` は prompt attention の parity/benchmark 実行ファイルが作る合成 query selection (`ids`) の重なり方を切り替えます。Strata の通常の `strata` エンジンが読む設定ではありません。`qsa_prompt_attn_parity` と、そのソースを共有する HIP テスト `hip_prompt_attn_wmma` に限る診断用フックです。CUDA 実行ファイルは `STRATA_BUILD_TESTS` または `STRATA_PARITY_PROMPT_ATTN` を有効にしたビルドで作られ、HIP 側はテスト構成で作られます。SYCL にも target はありますが、CMake 上は「built, not registered」であり、対応する tensor-core kernel が未移植であるため使用可能な parity 経路とは確認できません。

## 値と判定

各 `run()` 呼び出しで `std::getenv("QA_SAME")` を調べ、設定されている場合に `std::atoi()` で整数化します。文字列全体の検証はありません。したがって空文字や数値で始まらない文字列は 0、数値の後ろに文字がある場合は先頭の数値部分として扱われます。負値も受け付けますが、1、3、4 以外は同じ隣接窓モードになります。

| 値（`atoi` の結果） | 各 query の selection |
|---|---|
| unset | 先に生成した合成 selection を維持する。古いセルの集合を query ごとに少しずつ変え、直近 512 セルを含める。 |
| `1` | 先頭 `w` セル（`0..w-1`）を全 query で共有する。 |
| `3` | query ごとに seed を変えて、`w-512` 個の古いセルをランダム選択し、直近 512 セルを加える。 |
| `4` | 4 query ごとに同じ seed (`i/4`) を使って古いセルを選び、直近 512 セルを加える。 |
| その他（`0`, `2`, 無効文字列など） | `i / 4 * 64` を開始位置とする幅 `w` の連続窓を使う。窓が範囲外にならないよう `nkv-w` で上限を取る。 |

いずれの設定値でも、その query の幅 `w` が全セル数 `nkv` と等しい場合は上書きされません。mode 4 は4 query ごとに同じ seed を使いますが、query ごとに `nkv` から古いセル候補を作り直すため、コード上で同一セル集合になる保証まではありません。`QA_DUMP` が設定され、有効な記録を読み込む場合は、この処理の後に dump の selection が `ids` を上書きします。

## 有効になる条件

- `qsa_prompt_attn_parity` は CUDA が有効で、`STRATA_BUILD_TESTS` または `STRATA_PARITY_PROMPT_ATTN` が有効な場合にビルドされます。CMake の説明上、モデルを使わない合成 GPU parity/性能比較用です。
- HIP ビルドの `hip_prompt_attn_wmma` も同じソースを使います。CMake では HIP テストとして登録されています。実行時は gfx11/gfx12 以外の GPU を skip (終了コード 77) します。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp` にも同じ `getenv` と selection 処理があります。`sycl/CMakeLists.txt` は `qsa_prompt_attn_parity` target を作りますが、コメントでは未登録で、必要な tensor-core prompt kernel が未移植のため実行は未対応とされています。
- この変数による通常エンジンの attention selection、モデル出力、生成処理への変更は、対象ソース内にありません。

## 実行時の詳細

`run()` 内で合成 selection を作った後、各 query の幅が全セル数と異なる場合だけ `QA_SAME` を評価してセル ID を書き換えます。CUDA の `main()` は int8、FP16、Q4_0 の形式ごとに `run()` を呼ぶため、環境変数は各形式の実行時に読み直されます。コード内で値をキャッシュしたり、環境変数を書き換えたりする処理はありません。

出力の PASS/FAIL と時間・checksum は、書き換え後の selection を入力にした parity 検証と性能測定の結果です。`QA_SAME` 自体の値や選択モードを示すログ出力は見当たりません。CUDA parity 実行例と合成・モデル非依存の説明は `docs/NVIDIA_V100.md` にあります。

## 根拠

- `src/kernels/qsa_prompt_attn_parity.cpp:1-11` — 実行ファイルの目的、合成入力、引数。
- `src/kernels/qsa_prompt_attn_parity.cpp:100-149` — 既定 selection、値の取得・変換、モードごとの ID 生成。
- `src/kernels/qsa_prompt_attn_parity.cpp:151-167` — `QA_DUMP` による後続の ID 上書き。
- `src/kernels/qsa_prompt_attn_parity.cpp:346-370` — `main()` と形式ごとの `run()` 呼び出し。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:125-175` — SYCL ソースの同等処理。
- `CMakeLists.txt:420-426, 808-813` — CUDA parity executable と HIP テスト target のビルド条件。
- `sycl/CMakeLists.txt:351-355` — SYCL target はビルドするがテスト登録しない旨と kernel 未移植の説明。
- `docs/NVIDIA_V100.md:65-73` — parity 実行例、合成入力、モデルを使わない検査の説明。
