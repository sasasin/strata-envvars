# `STRATA_DIT_TRACE_DIR`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

これは Strata の通常の実行ファイルやサーバーが読む設定ではなく、Strata が生成する stable-diffusion.cpp の Qwen-Image-2.1 ネイティブ DiT runner に入る、テストビルド専用の診断フックである。指定ディレクトリへ DiT 計算途中のテンソルをバイナリで保存し、各ブロックの入力値の最大絶対値を `trace.txt` に追記する。追加コードは同期してテンソルを読み出して保存するもので、計算値自体は変更しない（`tools/image/sdcpp_dit/apply.py:152-185,193-237,240-266`）。

このフックは `tools/image/sdcpp_dit/apply.py` が外部の stable-diffusion.cpp checkout の `qwen_image_2_1_native.hpp` に埋め込むコードであり、Strata の通常ビルドや `setup` が有効化するものではない（`tools/image/sdcpp_dit/apply.py:1-15,331-349`）。

## 値と判定

埋め込まれた C++ は `getenv("STRATA_DIT_TRACE_DIR")` の null 判定だけを使い、値を文字列として出力パスの先頭に連結する。値の内容を parse、trim、正規化、検証する処理はない。相対/絶対パス、空白、大文字小文字、数値形式の違いによる有効性の差はない（`tools/image/sdcpp_dit/apply.py:156-165`）。

| ビルド・値 | 判定 |
|---|---|
| 未設定 | `getenv` が null。`trace_dir` が偽となり、trace の保存・統計処理を行わない。 |
| 空文字 | 設定ありとして有効。値は空のまま使われ、生成パスは `/ファイル名` となる。 |
| 任意の非空文字列（例 `trace`、`/tmp/trace`、`0`、`true`、空白を含む値） | 設定ありとして有効。文字列をディレクトリ部分として連結する。 |
| パスが書き込み不能、存在しない等 | 有効/無効の事前判定はない。`fopen` が失敗しても Strata のログやエラーにはせず、保存に失敗する。 |

空文字の場合も `trace_dir` は null ではないため trace 分岐に入る。連結式が `"/" + name` の形になる（`tools/image/sdcpp_dit/apply.py:158,160-165,182-184`）。ディレクトリの作成処理はこのコードにはない。

## 有効になる条件

- `tools/image/sdcpp_dit/apply.py` の変更を適用した Qwen-Image-2.1 ネイティブ runner が必要。適用前提として native runner が既に適用済みであることを検査する（`tools/image/sdcpp_dit/apply.py:331-349`）。
- 埋め込みコードは `SD_STRATA_DIT` の下に置かれ、同スクリプトが `SD_CUDA` または `SD_HIPBLAS` のときに同 macro を定義する。したがってこのパッチ経由では CUDA/HIPBLAS のテストビルドが対象（`tools/image/sdcpp_dit/apply.py:269-307`）。
- gate の `build_variant.py` では `--dit REPO` を指定したときにこのパッチを適用する。ファイル自身は「TEST BUILDS ONLY」とし、setup は適用しないと明記している（`tools/image/gate/build_variant.py:1-9,35-38`; `tools/image/sdcpp_dit/apply.py:1-4`）。
- `--model-args strata_dit_gemm=1` は Strata 独自 GEMM の使用条件であり、trace フックの条件ではない。trace 分岐は `trace_dir` の設定有無で判定される（`tools/image/sdcpp_dit/apply.py:12-15,39-46,193-207`）。
- `STRATA_DIT_TRACE_BLOCK` は別変数で、未設定時 `-1`、設定時 `atoi` で整数化され、指定ブロックの内部テンソル出力に使われる。`STRATA_DIT_TRACE_DIR` が設定されていても、この別変数が通常の非負ブロック番号に一致しない場合、ブロック内部の `blk_*.bin` は出力されない。一方、通常のストリーム・統計ファイルは出力対象のまま（`tools/image/sdcpp_dit/apply.py:158-159,193-207,213-237`）。

## 実行時の詳細

この値は挿入された runner クラス内の `trace_dir` メンバー初期化式で一度読み取られる。プロセス実行中に環境を変更しても、その runner インスタンスには反映されない（`tools/image/sdcpp_dit/apply.py:156-159,342`）。

`trace_dir` が設定されていると、prelude の `mod.bin` / `scale.bin`、テキスト入力後の `txtin.bin`、画像入力後の `imgin.bin`、最終出力 `out.bin` を保存する。各ブロック後にはテキスト側 `txt_NN.bin` と画像側 `img_NN.bin` の residual stream を出力し、各ブロックの GEMM/attention 入力最大絶対値を `trace.txt` に記録する（`tools/image/sdcpp_dit/apply.py:193-237,240-266`）。選択された画像ブロックでは `STRATA_DIT_TRACE_BLOCK` に従って `blk_qkv.bin`、`blk_q16.bin`、`blk_k16.bin`、`blk_v16.bin`、`blk_att.bin`、`blk_x_mid.bin`、`blk_ln2.bin`、`blk_act.bin` も書く（`tools/image/sdcpp_dit/apply.py:193-200,213-224,230-237`）。

ファイル出力前に backend を同期し、テンソルを host buffer に読み出す。ファイルは `wb`（`trace.txt` は `a`）で開き、書き込み結果は検査しない。`fopen` 失敗時はそのファイルを黙って飛ばす。ディレクトリ作成、fallback 先、再試行、診断ログはこの trace コードにない（`tools/image/sdcpp_dit/apply.py:160-185`）。

## ログと測定値

環境変数設定を示す stdout/stderr ログ、保存失敗時の warning/error、終了コード変更は trace コードにない。観測結果は指定パスに作られるファイル群である（`tools/image/sdcpp_dit/apply.py:160-185,193-237,240-266`）。

## 根拠

- `tools/image/sdcpp_dit/apply.py:1-15` — テスト専用適用ツールであること、通常 setup では適用しないこと。
- `tools/image/sdcpp_dit/apply.py:152-185` — 変数読み取り、別変数のブロック判定、同期・読み出し・ファイル出力。
- `tools/image/sdcpp_dit/apply.py:193-266` — trace を呼ぶ処理箇所と生成ファイル。
- `tools/image/sdcpp_dit/apply.py:269-307,331-349` — CUDA/HIPBLAS と macro の条件、native runner へのパッチ適用。
- `tools/image/gate/build_variant.py:1-9,35-38` — gate variant が `--dit` でパッチを適用する経路。
