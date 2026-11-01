# `--help`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `metal/setup_mac.py`（`setup.py` から Apple Silicon の macOS で委譲） |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし |

## 役割

Apple Silicon 用ソースセットアップ CLI の使用方法と、その parser が公開する引数一覧を表示して終了します。この parser は `metal/setup_mac.py` 独自のもので、共通の `setup.py` parser とは別 scope です。macOS で `STRATA_CONTROL_INSTALL=1` が設定されていない `setup.py` は、引数をこのスクリプトへ渡します（`setup.py:82, 7703-7707, 9068-9069`）。

## 使い方

Strata checkout のルートから、Python 3.10 以降で直接実行する例です。

```sh
python3 metal/setup_mac.py --help
```

macOS の `./setup.sh --help` も `setup.py` を経て同じ parser に届きます。ただし wrapper は Python 実行環境を確認・用意してから `setup.py` を呼ぶため、初回は help 表示より前に Python のダウンロード等が行われる場合があります（`setup.sh:7-13, 39-50`）。

## 値と既定値

値を取りません。`argparse.ArgumentParser` は既定で help action を作り、短縮形 `-h` と長形式 `--help` を登録します。`metal/setup_mac.py` は `add_help=False` を指定しておらず、formatter も独自指定していません（`metal/setup_mac.py:327-328`）。help action に値を付ける形式はありません。

## 実行時の動作

help action は引数解析中にヘルプを出力して終了するため、通常の setup 処理には進みません。parser の宣言と解析は `metal/setup_mac.py:327-356`、setup の表示・データディレクトリ解決・Mac 検査は解析後の `metal/setup_mac.py:364-380` から始まります。したがって、このオプション自体はモデル選択、ダウンロード、engine build、server 起動を要求しません。

`setup.py` 経由では Darwin 判定後に `metal/setup_mac.py` を子プロセスとして呼び、その終了コードを返します（`setup.py:9068-9069, 7703-7707`）。`STRATA_CONTROL_INSTALL=1` の場合はこの委譲条件を満たさず、通常の `setup.py` 側へ進むため、この mac scope の help ではありません（`setup.py:82, 9068-9069`）。

## 適用条件と副作用

この help は `metal/setup_mac.py` の parser で有効です。parser が `parse_known_args` を使用するため、未知の引数は通常なら警告して続行します（`metal/setup_mac.py:356-358`）。ただし help action は解析をそこで終了させるので、help 指定時には後続の setup 本体や未知引数の警告処理へ進みません。

ソース上、help action が行うのはヘルプ表示と終了です。直接スクリプトを実行した場合に parser より前に実行されるのは Python module の import です。`setup.py` / `setup.sh` 経由では上記の委譲処理と wrapper の Python 環境準備も通ります。

## 出力とエラー

Python 標準 `argparse` の既定 help action は usage と説明・オプション一覧を標準出力へ表示し、終了コード `0` で終了します。ここで確認できる一覧は、同 parser に宣言された `--family`、`--model`、`--context`、`--port`、`--host`、`--api-key`、`--draft-vocab`、`--no-browser`、`--data-dir`、`--move-data`、`--set-default-data-dir`、`--models-dir`、`--gguf-dir`、`--yes`、`--source`、`--setup`、`--no-start`、`--check`、`--update`、`--build`、`--vision` および help alias です（`metal/setup_mac.py:328-355`）。表示文言・整形は Python の `argparse` が生成します。

この action 固有のエラー経路はありません。ここでの終了コードは `argparse` の既定動作です。親の `setup.py` 経由では子プロセスのコードが呼び出し側へ返されます（`setup.py:7703-7707, 9068-9069`）。

## 根拠

- parser 定義、help action を含む引数解析: `metal/setup_mac.py:327-358`。
- 解析後に始まる通常処理: `metal/setup_mac.py:364-380`。
- `setup.py` の Darwin 委譲条件と wrapper 関数: `setup.py:82, 7703-7707, 9062-9069`。
- shell wrapper の `setup.py` 起動と Python bootstrap: `setup.sh:7-13, 39-50`。
- scope・予定リンクと索引記載: `docs/cli/README.md:1594-1609`。
