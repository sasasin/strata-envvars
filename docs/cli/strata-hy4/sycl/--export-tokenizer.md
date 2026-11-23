# `--export-tokenizer`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| オプション | `--export-tokenizer` |
| 別名 | なし |
| 値 | `.strata` ファイルのパスと出力ディレクトリの 2 値 |

## 役割

Hy4-Flash の `.strata` ファイルに含まれる tokenizer JSON と chat template を取り出し、Hugging Face 形式のファイル名で指定ディレクトリに書き出す。通常の SYCL 推論処理へ入る前に処理を終えるため、SYCL デバイス選択・GPU 初期化やモデル推論はこの経路では行わない。

## 使い方

```sh
strata-hy4-sycl --export-tokenizer model.strata ./tokenizer-export
```

出力先ディレクトリは事前に存在している必要がある。コマンドはその中に `tokenizer.hf.json` と `chat_template.jinja` を作成する。

## 値と既定値

オプションの直後から順に入力 `.strata` ファイル、出力ディレクトリを 1 つずつ読み取る。省略可能な値や既定値はない。引数文字列の形式・拡張子・ディレクトリの存在を parser 側で事前検証する処理はない。必要な値が足りない場合は `ERR --export-tokenizer needs a value` を標準出力に出し、終了コード 2 で終了する。

## 実行時の動作

`StrataFileReader::open` で入力ファイルを開いてコンテナを読み、`hy4::parse_manifest(..., true)` で manifest を解析する。`true` により manifest の `chat_template` と `tokenizer_json` が読み込まれる。その後、両値をそれぞれ `DIR/tokenizer.hf.json`、`DIR/chat_template.jinja` に書き込み、成功時には各データのバイト数を標準出力へ表示する。

この処理は `--export-tokenizer` を解析した時点で `main` から戻る。従って同時にモデル指定や `--serve` などを渡しても、それらの後続処理は実行されない。後続の引数はこの分岐では検査されない。

## 適用条件と副作用

入力は Hy4 manifest を含む `.strata` ファイルである必要がある。`parse_manifest` は tokenizer 項目だけでなく `config.text_config`、`engram_meta`、`trunk_tensors` なども解析し、最後に `chat_template` と `tokenizer_json` を参照するため、それらの構造・キーが欠けた場合の挙動はこのオプション固有の検証エラーとして定義されていない。

出力ディレクトリは作成されない。ファイルは `fopen(..., "wb")` で開かれるため、同名ファイルがあれば切り詰めて上書きする。最初のファイルを書いた後に2つ目の書き込みが失敗すると、最初の出力は残る。`fclose` の戻り値は確認されていない。

## 出力とエラー

- 入力のオープンまたはコンテナ読み込みに失敗すると、`open: <理由>` を標準エラーに出し、終了コード 1。
- 出力ファイルの open または `fwrite` に失敗すると、`cannot write <パス>` を標準エラーに出し、終了コード 1。
- 2ファイルの書き込み成功後、`tokenizer: <バイト数> bytes, chat template: <バイト数> bytes` を標準出力に出し、終了コード 0。
- parser が受け取るべき値がない場合は標準出力に不足メッセージを出し、終了コード 2。

manifest の JSON/schema 不正時に `json_parse` / `parse_manifest` がどのようなプロセス終了・診断を行うかは、当該呼び出し元で捕捉・変換されていないため、この調査では特定できない。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:105-128` — 引数値の取得、不足値処理、オプション分岐、処理後の即時 return。
- `engine/src/hy4flash/sycl/sy_main.cpp:18-41` — 出力名、入力を開いて manifest を解析する処理、ファイル作成・書き込み、成功時の表示と失敗経路。
- `engine/src/hy4flash/run/hy4_manifest.h:78-80, 114-138` — manifest 全体の解析と、`keep_tokenizer` が真の場合に読む tokenizer/chat template キー。
- `engine/src/artifact/strata_reader.cpp:33-47, 71-90, 113-146` — Strata ファイルのオープン、Section 0 の解凍・manifest 読み込み、および Section 3 の読み込み失敗経路。
- `docs/cli/README.md:1452-1468` — `strata-hy4-sycl` のコマンド scope と対象リンク。
