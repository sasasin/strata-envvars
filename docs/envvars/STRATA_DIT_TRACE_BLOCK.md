# `STRATA_DIT_TRACE_BLOCK`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

テスト専用の DiT trace で、画像側の指定 transformer block 内部の中間値を `.bin` ファイルへ書き出す block 番号を選ぶ。Strata 本体の通常ビルドが直接読む設定ではない。Strata の `tools/image/sdcpp_dit/apply.py` が、テスト用 stable-diffusion.cpp native runner に挿入する C++ コードとして読み取り処理を定義しており、`tools/image/gate/build_variant.py --dit REPO` 経由でこのパッチを適用したビルドで使われる（`tools/image/sdcpp_dit/apply.py:1-15, 152-160, 331-349`; `tools/image/gate/build_variant.py:1-9, 31-38`）。

対象 block では QKV 出力、Q/K/V、attention 出力、残差 stream、LN2 出力、活性値を `blk_*.bin` に書き出す。ブロック番号は画像側ループの `i` と比較されるため 0 始まり。全 block 後の residual stream や `trace.txt` の各段階最大値は `STRATA_DIT_TRACE_DIR` だけで有効になり、この変数では選別されない（`tools/image/sdcpp_dit/apply.py:193-205, 213-235, 239-246`; `tools/image/gate/dit_replay.py:1-4, 67-70`）。

## 値と判定

runner に挿入されるメンバー初期化子は `getenv("STRATA_DIT_TRACE_BLOCK")` が null なら `-1`、設定されていれば `std::atoi` の結果を保存する。文字列全体の検証はせず、`atoi` が変換できる先頭の整数部分を使う。したがって空文字や数字で始まらない値は `0`、`" 2tail"` は `2`、`"-1"` は `-1` となる。空白・符号は `atoi` の変換規則に従い、大文字小文字の区別はない（文字列比較をしない）。`0` は block 0 を選び、負数や存在する block 範囲外の整数は一致する `i` がないため block 内部ダンプを選ばない。値の clamp や無効値警告はない。変換可能な範囲を超える数値の結果はこのコードで定義していない（`tools/image/sdcpp_dit/apply.py:156-160, 193-199, 213-217, 230-235`）。

| 条件 | 未設定 | block 内部ダンプを選ぶ値 | 選ばない値 |
|---|---:|---|---|
| `SD_STRATA_DIT` を付けて生成した native runner | `-1` | `atoi` の結果が実在する画像 block の 0 始まり番号と一致する値（例: `0`, `1`, `"1tail"`） | 負数や範囲外番号など（空文字や `"true"` のような非数値文字列は `0` へ変換されるので block 0 があれば選ぶ） |

## 有効になる条件

- Strata 同梱の `tools/image/sdcpp_dit/apply.py` で、先に native runner が適用された stable-diffusion.cpp checkout にパッチを挿入する必要がある。通常セットアップは適用せず、同スクリプトは test builds only と記している（`tools/image/sdcpp_dit/apply.py:1-15, 331-349`）。
- ビルド時に `SD_CUDA` または `SD_HIPBLAS` が成立して `SD_STRATA_DIT` が定義される必要がある。挿入される trace 部分も `#ifdef SD_STRATA_DIT` 内にある（`tools/image/sdcpp_dit/apply.py:152-160, 268-307`）。
- native Qwen-Image-2.1 runner が該当する画像 block を実行し、`STRATA_DIT_TRACE_DIR` が null でないことも必要である。空文字も null ではないため条件を通り、空の directory 文字列に `/ファイル名` を連結したパスで open を試みる。block 内部の書き出し条件は `trace_dir && !prefix && i == trace_block` なので、未設定の trace directory ではこの値が一致してもファイルを書かない（`tools/image/sdcpp_dit/apply.py:193-199, 213-217, 230-235`）。
- `--model-args strata_dit_gemm=1` は Strata GEMM を使う条件として説明されるが、trace の block 選択条件には含まれない。trace のコードは `trace_dir`、画像側かどうか、block 番号で分岐する（`tools/image/sdcpp_dit/apply.py:12-15, 39-46, 193-199`）。

## 実行時の詳細

環境変数の値は、パッチで runner クラスに追加される `trace_block` メンバーの初期化時に読み取られ、その runner インスタンス内に保持される。各 block では保存済み番号と `i` を比較し、合致した画像 block の内部 tensor を `trace_file` で同期・取得して trace directory に書き出す。関数呼び出しごと／block ごとに環境を読み直す処理はなく、稼働中に環境を変更しても既存 runner の値には反映されない（`tools/image/sdcpp_dit/apply.py:156-165, 193-199, 213-217, 230-235`）。

この変数が選ぶ内部 dump は `blk_qkv.bin`, `blk_q16.bin`, `blk_k16.bin`, `blk_v16.bin`, `blk_att.bin`, `blk_x_mid.bin`, `blk_ln2.bin`, `blk_act.bin`。各書き出し箇所の条件は `trace_dir && !prefix && i == trace_block`（`blk_act.bin` も同等）である。dump のための同期と tensor 読み出しは行われるが、Strata のパッチコメントは値を変更しない trace と説明している（`tools/image/sdcpp_dit/apply.py:152-165, 193-199, 213-217, 230-235`）。

## ログと測定値

`STRATA_DIT_TRACE_BLOCK` の不一致や変換失敗について、Strata 側の警告・終了処理はない。block 内部 dump は `trace_file` が trace directory 内のファイルを開けた場合だけ書き込まれ、open 失敗時のログはない（`tools/image/sdcpp_dit/apply.py:160-165, 193-199, 213-217, 230-235`）。この変数に関する測定値は該当資料にない。

## 根拠

- `tools/image/sdcpp_dit/apply.py:1-15` — test-only patch と native runner/GEMM の適用条件。
- `tools/image/sdcpp_dit/apply.py:152-165` — trace メンバー、環境変数の読み取り、ファイル書き出し。
- `tools/image/sdcpp_dit/apply.py:193-205, 213-235` — block 番号による内部 dump と、別の trace 記録。
- `tools/image/sdcpp_dit/apply.py:268-307, 331-349` — backend/build macro とパッチ適用処理。
- `tools/image/gate/build_variant.py:1-9, 31-38` — `--dit` による test variant への適用。
- `tools/image/gate/dit_replay.py:1-4, 67-70` — block 番号と dump の使い方。
