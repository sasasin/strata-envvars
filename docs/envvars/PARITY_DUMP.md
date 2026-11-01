# `PARITY_DUMP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の作業ツリーは `main...origin/main` で、変更表示はありません。外部ライブラリ・driver の環境変数は対象外です。

## 役割

`PARITY_DUMP` は SYCL 版 `qsa_prompt_attn_parity` の診断出力を追加します。この実行ファイルは GPU の prompt-attention kernel、従来の FP32 kernel、FP64 host reference の結果を合成データで比較するものです。環境変数は比較や計算の選択を変えず、最初の query の一部の出力値を標準出力へ表示するだけです（`sycl/src/kernels/qsa_prompt_attn_parity.cpp:1-11,326-327`）。

この名前を値として読む箇所は同 SYCL ソースの1箇所です。通常の Strata engine の設定として読む箇所は確認できません。CUDA 用の同名 parity 実行ファイルは別の `src/kernels/qsa_prompt_attn_parity.cpp` を使い、この名前を読みません（`CMakeLists.txt:522-528`）。

## 値と判定

値の内容は parse せず、`std::getenv("PARITY_DUMP")` が null かどうかだけを判定します（`sycl/src/kernels/qsa_prompt_attn_parity.cpp:326`）。

| 値 | 判定 | 結果 |
|---|---|---|
| 未設定 | null | 追加の `dump ...` 行を出さない |
| 空文字 | null ではない | 条件を満たす値を追加出力する |
| その他の設定値 | null ではない | 値の文字列に関係なく追加出力する |

`1`、`0`、`false` などの特別扱い、数値変換、範囲判定、無効値 fallback はありません。CLI 引数による上書きもありません。

## 有効になる条件

- `sycl/src/kernels/qsa_prompt_attn_parity.cpp` でビルドされた parity 実行ファイルを使う必要があります。SYCL の CMake では `STRATA_SYCL_PARITY` が有効な場合にこの実行ファイルを作成します。同オプションの既定値は `ON` で、CMake コメントはこの parity 実行ファイルを build するが ctest には登録しないとしています（`sycl/CMakeLists.txt:279-281,404-408`）。
- 実行中に reference 計算のループが `i == 0` に達し、次元 `d` が `3` または `70` のときだけ表示します。通常の正の query 数では各 head についてこの2次元の値を表示します（`sycl/src/kernels/qsa_prompt_attn_parity.cpp:286-291,326-327`）。
- 同じ parity ソースを使う CUDA / HIP 側では `PARITY_DUMP` を読んでいません。トップレベル CMake の CUDA target と HIP target は `src/kernels/qsa_prompt_attn_parity.cpp` を指定しています（`CMakeLists.txt:522-528,1104-1110`）。
- この条件はモデル状態やサーバーモードに依存しません。ソースコメントと実行例は synthetic data でモデル不要の parity 実行として説明しています（`sycl/src/kernels/qsa_prompt_attn_parity.cpp:2-11`、`docs/NVIDIA_V100.md:71-79`）。

## 実行時の詳細

環境変数は比較ループの各要素で `getenv` され、static 変数などへの cache はありません。ループ中の `i == 0` で `d == 3` または `d == 70` なら、head 番号、次元番号、FP64 reference、旧 kernel、現行 kernel の値を `dump h... d... ref ... old ... new ...` 形式で `printf` し、標準出力へ出します（`sycl/src/kernels/qsa_prompt_attn_parity.cpp:263-277,326-327`）。

この出力は parity 判定に使われません。PASS/FAIL は reference との差と旧・新 kernel 間の差から決まり、全 run の失敗数がプロセスの終了値になります。したがって `PARITY_DUMP` を設定しても成功・失敗条件や終了値は変わりません（`sycl/src/kernels/qsa_prompt_attn_parity.cpp:361-366,382,405-418`）。未設定時も各 run の要約と最終 `FAILURES: ...` は表示されます。

## 根拠

- 候補名は環境変数候補一覧にあります（`docs/envvars/000_envvers.md:476`）。実際の読み取りは SYCL parity ソースの `std::getenv` 1箇所に限られます（`sycl/src/kernels/qsa_prompt_attn_parity.cpp:326`）。
- SYCL parity target の作成条件と ctest 未登録の注記: `sycl/CMakeLists.txt:279-281,404-408`。
- CUDA parity target の条件と別ソースの指定: `CMakeLists.txt:522-528`。HIP target も同じ CUDA/SYCL 共通側の `src/kernels/qsa_prompt_attn_parity.cpp` を指定します（`CMakeLists.txt:1104-1110`）。
- parity の用途と synthetic data の説明: `sycl/src/kernels/qsa_prompt_attn_parity.cpp:1-11`。CUDA の実行例とモデル不要の説明: `docs/NVIDIA_V100.md:71-79`。
