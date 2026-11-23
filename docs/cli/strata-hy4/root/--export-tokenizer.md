# `strata-hy4 --export-tokenizer`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP root） |
| オプション | `--export-tokenizer` |
| 別名 | なし |
| 値 | `.strata` ファイルのパスと、既存の出力ディレクトリのパスを順に取る |

## 役割

`.strata` ファイルの Section 0 manifest に含まれる `tokenizer_json` と `chat_template` を、後続の Python tokenizer 変換処理で使える2ファイルとして取り出します。serve 用 tokenizer を作る際、Python 側に zstd モジュールがなくても engine 経由で manifest を扱える経路として利用されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:25-26`、`terminal/tools/hy4_tokenizer.py:9-12`）。

## 使い方

出力先には既存ファイルを置かず、事前に作成した空のディレクトリを指定します。

```sh
export_dir=$(mktemp -d)
strata-hy4 --export-tokenizer /path/to/Model.strata "$export_dir"
```

成功時は出力した tokenizer JSON と chat template のバイト数を標準出力に表示します（`engine/src/hy4flash/run/hy4_main.hip.cpp:47-49`）。

## 値と既定値

- 値は必須で、順に入力ファイル、出力ディレクトリです。parser は `--export-tokenizer` の直後の値を入力ファイルとして読み、その次の値を出力先として渡します（`engine/src/hy4flash/run/hy4_main.hip.cpp:393-396`）。
- 値の型・拡張子・ディレクトリの存在を parser 段階では検証しません。入力は `StrataFileReader::open` に渡され、出力先は `DIR/tokenizer.hf.json` と `DIR/chat_template.jinja` のパスに連結されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:27-38`）。
- 省略時の既定値はありません。どちらかの値が欠けると `ERR --export-tokenizer needs a value` を標準出力に出して終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383`）。
- 追加の引数や後続オプションは処理されません。この option の分岐は exporter の戻り値を返して終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:393-396`）。

## 実行時の動作

1. `StrataFileReader::open` で入力を開き、header と Section 0 manifest を読み込みます。ファイルを開けない、header が短い・magic が不正、section 数や alignment が不正、manifest の ZSTD 展開に失敗するなど、reader が報告する失敗では exporter が `open: <理由>` を標準エラーに出して終了コード 1 を返します（`engine/src/hy4flash/run/hy4_main.hip.cpp:27-33`、`engine/src/artifact/strata_reader.cpp:33-90`）。
2. manifest を解析し、`keep_tokenizer=true` によって `chat_template` と `tokenizer_json` を読み込みます（`engine/src/hy4flash/run/hy4_main.hip.cpp:34-35`、`engine/src/hy4flash/run/hy4_manifest.h:78-80,136-139`）。
3. `DIR/tokenizer.hf.json`、続いて `DIR/chat_template.jinja` を binary write mode (`wb`) で開いて内容を書きます。`wb` のため、同名ファイルがあれば切り詰めて上書きします。出力ディレクトリは作成しません（`engine/src/hy4flash/run/hy4_main.hip.cpp:36-47`）。
4. 両方の書き込み後、バイト数を標準出力に表示して終了コード 0 を返します（`engine/src/hy4flash/run/hy4_main.hip.cpp:47-49`）。

## 適用条件と副作用

- 対象は CUDA/HIP `strata-hy4` の root parser です。Metal と SYCL にも同名 option がありますが、索引上も別 scope であり、この文書の対象外です（`docs/cli/README.md:1279-1283,1358-1363,1452-1457`）。
- exporter 分岐は引数走査中に直接呼ばれて戻るため、後続の通常実行経路にある GPU 選択・モデル実行へ進みません（`engine/src/hy4flash/run/hy4_main.hip.cpp:393-396,514-544`）。exporter 本体にも GPU 操作はありません。
- 指定ディレクトリはあらかじめ存在する必要があります。書き込み先を開けない、または書き込みバイト数が要求量に満たない場合は `cannot write <path>` を標準エラーに出し、終了コード 1 です（`engine/src/hy4flash/run/hy4_main.hip.cpp:36-47`）。2つ目のファイルで失敗すると、1つ目のファイルはすでに書き込み済みの可能性があります。
- `parse_manifest` の JSON 欠損・形式不正時に CLI がどの例外処理や終了表示を行うかは、この exporter/parser の範囲から確認できません。ここではその失敗時の出力・終了コードを断定しません（呼び出し箇所: `engine/src/hy4flash/run/hy4_main.hip.cpp:34-35`、manifest field access: `engine/src/hy4flash/run/hy4_manifest.h:78-80,136-139`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:25-49` — exporter の目的、reader 呼び出し、出力ファイル名・書き込み方式、成功・失敗時の表示と戻り値。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-396` — 値の取得、値不足時の処理、オプションの即時実行。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:514-544` — exporter 分岐後に続く GPU 選択・serve 分岐。
- `engine/src/artifact/strata_reader.cpp:33-90` — `.strata` reader が入力と Section 0 manifest を読む際のエラー条件。
- `engine/src/hy4flash/run/hy4_manifest.h:78-80,136-139` — manifest の解析と tokenizer 関連フィールドの取り出し。
- `terminal/tools/hy4_tokenizer.py:9-12` — Python 側で exporter を使う背景（補助資料）。
