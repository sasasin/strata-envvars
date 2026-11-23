# `--export-tokenizer`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-metal` |
| コマンド | `strata-hy4-metal` |
| オプション | `--export-tokenizer` |
| 別名 | なし |
| 値 | `.strata` ファイルのパスと、出力先ディレクトリのパスを各1つ |

## 役割

`.strata` ファイルを開き、その manifest に格納された tokenizer 定義と chat template を通常のファイルとして書き出します。この分岐は parser から直接エクスポート処理を呼び出して終了するため、モデル推論や Metal GPU の初期化を行いません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1458-1481,1586-1589`）。

## 使い方

既存ファイルとの衝突を避ける例です。`mktemp -d` で新しい出力ディレクトリを作成してから実行します。

```sh
out_dir="$(mktemp -d)"
strata-hy4-metal --export-tokenizer ./model.strata "$out_dir"
```

成功すると出力先に `tokenizer.hf.json` と `chat_template.jinja` が作成されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1468-1481`）。

## 値と既定値

- オプションの後に入力ファイルと出力ディレクトリをこの順で渡します。既定値や短縮別名はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1586-1589`）。
- 入力ファイルは `StrataFileReader::open` で開き、manifest を `parse_manifest(..., true)` に渡します。`true` によって manifest の `chat_template` と `tokenizer_json` を読み取ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1460-1467`; `engine/src/hy4flash/run/hy4_manifest.h:78-80,136-139`）。
- 引数個数や入力形式の追加 validation はこの option 分岐にはありません。値を省略した場合の安全なエラー処理は確認できず、`nxt()` が `argv` の次要素を直接読みます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1586-1589`）。必要な2値を必ず指定してください。

## 実行時の動作

1. 入力 `.strata` を読み取り専用で開き、reader が manifest を用意します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1460-1467`）。
2. manifest の tokenizer JSON と chat template を保持する設定で解析します（`engine/src/hy4flash/run/hy4_manifest.h:78-80,136-139`）。
3. 出力先ディレクトリ内の `tokenizer.hf.json`、続いて `chat_template.jinja` をバイナリ書き込みモードで開き、各内容を書き込みます。既存の同名ファイルは切り詰めて上書きします（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1468-1479`）。
4. 2ファイルの書き込みに成功すれば、各データのバイト数を標準出力へ表示して `0` を返します（同 `:1479-1481`）。

出力先ディレクトリはこの処理では作成しません。1つ目を書いた後に2つ目の書き込みが失敗した場合、1つ目のファイルは残り得ます。処理は左から短絡評価されるため、2つ目の書き込みは1つ目の成功後にのみ試されます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1468-1479`）。

## 適用条件と副作用

- `.strata` を開けない場合は `open: <reader のエラー>` を標準エラーへ出し、終了コード `1` で終了します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1460-1465`）。
- 出力ファイルを開けない、または `fwrite` が要求バイト数を書けない場合は `cannot write <path>` を標準エラーへ出し、終了コード `1` になります。出力先ディレクトリが存在しない場合もファイルを開けず、この経路になります（同 `:1468-1479`）。
- Metal 用 reader のビルド構成によって manifest の取得方法が異なります。通常の reader は Section 0 の zstd manifest を展開します（`engine/src/artifact/strata_reader.cpp:71-110`）。zstd なしの reader は入力ファイル隣接の `<入力パス>.manifest.json` を読みます（`engine/src/hy4flash/metal/strata_reader_nozstd.cpp:1-4,70-78`）。後者を使う構成では、その sidecar がなければ空 manifest のまま reader が成功し得ますが、tokenizer export 用の有効な manifest として解析できることまでは保証されません。
- 入力ファイルのオープンと manifest 解析以外に、推論モデル・GPU を使う処理はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1458-1481,1586-1589`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1586-1589` — parser 分岐。入力 path と出力 dir を順に取得し、export 処理の戻り値で終了する。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1458-1481` — 入力 open、manifest 読み込み、2つの出力ファイル、メッセージと戻り値。
- `engine/src/hy4flash/run/hy4_manifest.h:78-80,136-139` — manifest を解析し、tokenizer JSON と chat template を保持する条件。
- `engine/src/artifact/strata_reader.cpp:71-110` — zstd 対応 reader の Section 0 manifest 展開。
- `engine/src/hy4flash/metal/strata_reader_nozstd.cpp:1-4,70-78` — zstd なし reader の sidecar manifest 読み込み。
- `docs/cli/README.md:1358-1384` — `strata-hy4-metal` のコマンド階層と `--export-tokenizer` 文書リンク。
