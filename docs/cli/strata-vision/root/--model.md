# `--model`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。調査時の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision` / `strata-vision-hip` / `strata-vision-sycl` |
| オプション | `--model` |
| 別名 | なし |
| 値 | テキストモデルの GGUF ファイルパス。分割モデルでは先頭 shard を指定する |

## 役割

画像エンコーダが使うテキストモデルを指定します。`strata-vision` はモデル重みを推論するのではなく、画像 encoder の初期化に必要な tokenizer と GGUF header を読み込みます。画像 embedding は対応する `--mmproj` の vision encoder が生成します (`tools/vision/strata_vision.cpp:3-8, 208-215`)。

## 使い方

```sh
strata-vision --mmproj /models/vision-mmproj.gguf --model /models/text-model-00001-of-00004.gguf
```

`--model` と `--mmproj` の両方が必要です。位置引数はありません。CPU/GPU variant は同じ引数 parser を使います (`tools/vision/strata_vision.cpp:93-128`; `tools/vision/CMakeLists.txt:96-116`)。

## 値と既定値

- 値は次の argv 要素から文字列として受け取られます。型変換、拡張子検査、パスの存在確認を parser 段階では行いません (`tools/vision/strata_vision.cpp:93-101`)。
- 既定値はありません。`--model` が省略されるか、値が空文字列の場合は `--mmproj` と合わせて必須引数チェックにかかり、usage を stderr に出して終了コード 2 になります (`tools/vision/strata_vision.cpp:125-128`)。
- 値を付けずに `--model` を指定すると `--model needs a value` を stderr に出して終了コード 2 になります (`tools/vision/strata_vision.cpp:95-97`)。
- 同じオプションを複数回指定した場合、parser は値を順次代入するため最後の値が使われます (`tools/vision/strata_vision.cpp:93-101`)。

## 実行時の動作

1. 受け取ったパスを `strata_open_text_model()` に渡します。通常は GGUF の key/value header を tensor なしの一時 GGUF に複写し、`vocab_only` で読み込みます。重み tensor はこの経路で読み込まれません (`tools/vision/strata_vision.cpp:208-212`; `tools/vision/gguf_meta.h:1-10, 135-155`)。
2. 一時ファイルは `TMPDIR`、次に `TEMP`、`TMP`、いずれも未設定なら `/tmp` に、プロセス ID を含む `strata-vision-meta-<pid>.gguf` として作成し、読み込み後に削除します (`tools/vision/gguf_meta.h:139-150`)。
3. 独自 header reader が入力を扱えない場合は一時ファイル経由を断念し、元ファイルを `llama_model_load_from_file(..., vocab_only)` で直接読み込む fallback があります。header reader は GGUF v2/v3 と列挙済みの値型を扱い、未知の型、切れた header、過大な key/array 等は複写失敗の理由になります (`tools/vision/gguf_meta.h:33-47, 64-80, 81-129, 151-155`)。
4. 読み込んだモデルは `mtmd_init_from_file()` に `--mmproj` とともに渡され、画像 tokenizer/encoder context の初期化に使われます (`tools/vision/strata_vision.cpp:211-215, 231-235`)。直接起動時には相対パスを絶対化しません。Strata server 経由では reader 起動引数を組み立てる際、親ディレクトリを含むパスを絶対化します (`serve/server.py:2808-2814`)。

## 適用条件と副作用

- 指定したモデルが開けない場合、`ERR cannot open the text model <path> (<reason>)` を stdout に出し、終了コード 1 で終了します (`tools/vision/strata_vision.cpp:211-212`)。
- モデルを開けても `--mmproj` の読み込みまたは vision 対応確認に失敗すれば、`ERR cannot load the vision encoder <mmproj>` を stdout に出し、終了コード 1 です (`tools/vision/strata_vision.cpp:231-235`)。ソース上にモデルと projector の互換性を個別に照合する validation は確認できません。
- 分割モデルでは先頭 shard の header から tokenizer を得る想定で、header copy 時に `split.no`、`split.count`、`split.tensors.count` を落とします。従ってこのオプションは全 shard を指定するものではありません (`tools/vision/strata_vision.cpp:7, 15`; `tools/vision/gguf_meta.h:8-10, 60-62`)。
- Header copy に成功した場合、一時 GGUF を作成・削除します。書き込み先が作れない場合は copy が失敗し、元ファイルを直接開く fallback に進みます (`tools/vision/gguf_meta.h:64-70, 129-130, 143-155`)。

## 出力とエラー

`--model` のファイルが開けないときの失敗文は stdout、終了コードは 1 です。必須値不足と値の欠落はそれぞれ usage または `needs a value` を stderr に出し、終了コード 2 です (`tools/vision/strata_vision.cpp:95-97, 125-128, 211-212`)。モデル読み込み成功時はファイルロード時間を stderr に記録します (`tools/vision/strata_vision.cpp:237-238`)。

## 根拠

- Parser と必須値チェック: `tools/vision/strata_vision.cpp:88-128`
- モデル読み込み、失敗出力、画像 context への引き渡し: `tools/vision/strata_vision.cpp:208-235`
- Header-only 読み込み、fallback、一時ファイルの生成と削除: `tools/vision/gguf_meta.h:1-10, 60-80, 135-155`
- server 起動時の引数構成: `serve/server.py:2808-2814`
- 実行ファイル target と variant 名: `tools/vision/CMakeLists.txt:96-116`
