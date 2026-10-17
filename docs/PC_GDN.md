# `PC_GDN`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

Metal の `prompt_chain` 診断プログラムで、GDN 層を処理するカーネル経路を選びます。Strata の通常実行ファイルや Metal engine はこの名前を読まず、`metal/tests/prompt_chain.cpp` だけで参照します。このプログラムは GGUF の重みを使い、指定した token 数 `T` の prompt chunk に対するカーネル処理時間を測るものです。したがって、`PC_GDN` は一般の Strata 実行設定ではなく、この診断プログラム用です。

## 値と判定

値は文字列全体で比較されます。数値への一般的な parse や trim、小文字化はありません。

| 環境変数の状態 | 選択される経路 |
|---|---|
| 未設定 | `scanr_4`（既定） |
| `step` と完全一致 | 各 GDN 層の `gdn_step` decode kernel を `T` token 分 dispatch |
| それ以外の設定値 | prompt 用 `gdn_pre` → `gdn_<値>` → `gdn_post` の経路 |

prompt 経路では、値が `scan_v` と完全一致すると `ib=8` を使い、その他は `std::atoi(値 + 6)` で `ib` を得ます。`atoi` は数値部分の後ろを無視し、先頭に数値がなければ `0` を返します。値の長さや形式の検証、`ib` の clamp はありません。6文字より短い値（`step` と `scan_v` を除く）は `値 + 6` が文字列の範囲を越えるため、定義された入力として扱えません。さらに、値そのものから `gdn_<値>` という pipeline 名を組み立てるため、未対応名では pipeline 作成が失敗し得ます。

## 有効になる条件

- `metal/tests/prompt_chain.cpp` から作られる `prompt_chain` 診断実行ファイルを実行するときだけ評価されます。`metal/CMakeLists.txt` は `metal/tests/*.cpp` を実行ファイルとして登録し、`prompt_chain` もその対象です。
- macOS の Metal 用 CMake プロジェクト内のテスト・計測ツールです。CUDA/HIP/SYCL の実行経路や `strata` engine の prompt 処理には適用されません。
- prompt 経路で実在するカーネル名として、Metal ソースは `gdn_scanr_2`、`gdn_scanr_4`、`gdn_scanr_8`、`gdn_scanr_4_8`、`gdn_scan_v` などを定義しています。`PC_GDN=step` はこれらと別に `gdn_step` を選びます。

## 実行時の詳細

`main()` のバッファ準備時に一度 `std::getenv("PC_GDN")` を呼び、値を `gdn_mode` にコピーします。実行中にプロセス環境を書き換えても選択は変わりません。GDN block（ループ上 `l % 4 != 3`）ごとに、共通の四つの投影 GEMM の後で分岐します。

- `gdn_mode != "step"` では `gdn_pre` で prompt chunk の中間状態を準備し、指定名の scan kernel を dispatch し、`gdn_post` と出力 GEMM を行います。
- `gdn_mode == "step"` では `gdn_step` を `T` 用の定数とともに dispatch し、activation の fp16 化と出力 GEMM を続けます。

この設定自体に専用ログや fallback はありません。診断プログラムは選択した経路の実行時間を測りますが、この変数の値による速度差や数値同一性を保証する測定結果は、調査対象 HEAD の資料から確認できませんでした。

## 根拠

- `metal/tests/prompt_chain.cpp:1-19,57-60`: プログラムの用途と prompt chunk の説明。
- `metal/tests/prompt_chain.cpp:150-151`: `getenv`、未設定時の `scanr_4`。
- `metal/tests/prompt_chain.cpp:298-331`: 共通投影後の step/prompt 分岐、scan kernel 名、`atoi`、dispatch。
- `metal/kernels/gdn_prompt.metal:317-323`: prompt scan kernel の公開名。
- `metal/kernels/gdn.metal:36-38,169-170`: `gdn_step` / `gdn_step8` kernel 定義。
- `metal/CMakeLists.txt:32-43`: Metal tests の各 `.cpp` を個別実行ファイルとして登録。
- 同一名の全参照確認: ソース全体では上記テストコードの読み取り1箇所のみ。`metal/src/engine` と通常の `strata` 実行経路には読み取りがありません。
