# `DS_VOCAB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

同梱ツール `tools/dsv41/serve_prompts.py` が、生成された token ID を表示用テキストに戻すときに使う語彙 JSON ファイルのパスです。DeepSeek V4.1 の prompt 比較・計測用スクリプトの補助表示に限られ、engine の起動引数、プロンプト、生成処理には使われません。ソース全体の完全一致検索で見つかった参照はこのスクリプトの1か所だけです。

## 値と判定

| 環境変数の状態 | 読み込むパス・結果 |
|---|---|
| 未設定 | `/data/dsv41-port/pack/tokenizer/vocab.json` を開く |
| 空文字 | `open("")` を試みる。失敗は捕捉され、空の語彙表になる |
| その他の設定値 | 文字列をそのままファイルパスとして `open()` に渡す。数値変換、空白除去、範囲検査、CLI 引数との優先順位はない |

JSON は `token文字列: token ID` の object を想定し、辞書を反転して `token ID: token文字列` の `_VOC` を作ります。ファイルを開けない、JSON が不正、または `.items()` 等の処理で例外が起きる場合は、例外の種類を問わず捕捉して `_VOC = {}` とします。警告やエラーの出力、終了はこの失敗処理からは発生しません。

## 有効になる条件

この変数を読むのは Python ツールだけです。OS、GPU backend、build macro、server mode、モデル状態による分岐はありません。語彙表はスクリプトの読み込み時に作られます。生成後に環境変数を変更しても再読込されません。

語彙表の読み込み自体は、テキスト表示の有無にかかわらずスクリプト実行時に試みられます。実際に `detok()` の結果を `TEXT` 行として出すのは、対象 prompt に `pic` があるか、別環境変数 `SHOW_TEXT` が空でない値で設定されている場合です。`DS_VOCAB` が未設定または空の場合の既定パス選択と、`SHOW_TEXT` の判定は独立しています。

## 実行時の詳細

モジュール先頭で `os.environ.get("DS_VOCAB", 既定パス)` を評価し、そのパスを `open()` して `json.load()` します。読み込みに失敗して `_VOC` が空でも処理を続けます。`detok()` は各 ID を `_VOC` から引き、見つからない ID には `?` を使います。したがって語彙表が空の場合、表示対象の全 ID は `?` として出力されます。結果の UTF-8 decode は `errors="replace"` で行います。

## 根拠

- `tools/dsv41/serve_prompts.py:7-19` — `DS_VOCAB` の直接読み取り、既定パス、JSON の反転、例外時の空辞書への fallback。
- `tools/dsv41/serve_prompts.py:20-25` — token ID の detokenize、未知 ID の `?`、UTF-8 decode。
- `tools/dsv41/serve_prompts.py:63-65` — 画像 prompt または `SHOW_TEXT` が truthy の場合だけ `TEXT` 行を表示。
- `tools/dsv41/serve_prompts.py:27-33` — 語彙表読み込み後のスクリプト処理と engine subprocess の起動。`DS_VOCAB` は engine コマンドへ引数として追加されない。
