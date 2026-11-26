# `--dsv41-package`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat`（`terminal/setup.py` に委譲） |
| オプション | `--dsv41-package` |
| 別名 | なし |
| 値 | `FILE`。必須の文字列引数。パスとしての検証はない |

## 役割

DeepSeek-V4.1 用エンジン package を指定していた旧オプションです。現行 Strata は DeepSeek を提供しないため、互換性のため引数として受理した後、値が空でなければ「DeepSeek は提供されない」というメッセージを出して終了します。package の読み込み・検証・インストールには進みません（`terminal/setup.py:11518`, `terminal/setup.py:11616-11618`; 廃止メッセージは `terminal/strata_control/retired.py:42-43`）。

## 使い方

```sh
# 旧スクリプトとの互換確認用。FILE が空でなければ廃止メッセージを出して終了する
python terminal/setup.py --dsv41-package /path/to/old-package.tar.gz
```

`setup.sh` や `START-HERE.bat` は引数を `setup.py` に渡します（`setup.sh:7-17`, `START-HERE.bat:53-64`）。この指定で現行環境に DeepSeek package を導入することはできません。

## 値と既定値

`argparse` に `metavar="FILE"` で登録されており、`type`、`choices`、`default`、独自 validator は指定されていません（`terminal/setup.py:11518`）。値は文字列としてそのまま受理され、ファイルの存在・形式・署名・ハッシュの確認には使われません。値を省略すると通常の `argparse` により引数不足として拒否されます。明示した値が空文字列の場合は後段の真偽値判定に通らず、このオプションによる拒否は起きません（`terminal/setup.py:11616`）。

## 実行時の動作

引数解析後、`a.dsv41_package` が真なら `retired.NOT_OFFERED` を表示して `main()` は `2` を返します。したがって通常の非空 `FILE` では、モデル選択や package の処理には進みません（`terminal/setup.py:11606-11608`, `terminal/setup.py:11616-11618`; メッセージ定義 `terminal/strata_control/retired.py:42-43`）。

この判定より前に、`--output jsonl` の出力切替、旧レイアウト移行処理、指定があれば `--update` の処理が実行されます。`--update` が先に終了コードを返した場合は、package オプションの拒否判定まで到達しません。また `--gguf-dir` が同時指定されていると、その既存ファイルの前処理も拒否判定より先に呼ばれます（`terminal/setup.py:11607-11618`）。

## 適用条件と副作用

このオプション自体は、空でない値を渡した場合に廃止メッセージを出して処理を止めるだけです。ファイルを開いたり、ネットワークアクセスや package のインストールをしたりする処理は確認できません。`--output jsonl` 併用時は標準出力を JSONL 用に確保し、人向け出力を標準エラーへ送る仕組みが先に有効になります（`terminal/setup.py:961-974`, `terminal/setup.py:997-999`, `terminal/setup.py:11607-11608`）。

## 出力とエラー

通常出力では標準出力に `Strata no longer offers DeepSeek models. Run \`strata launch\` to choose one of the Qwen models.` を表示し、終了コード `2` を返します（`terminal/setup.py:11616-11618`, `terminal/strata_control/retired.py:42-43`）。`--output jsonl` では人向けメッセージが標準エラーに出て、スクリプト末尾で `error` と `done` の JSONL イベントが標準出力へ出ます（`terminal/setup.py:967-974`, `terminal/setup.py:11616-11618`, `terminal/setup.py:12565-12571`）。

値を付け忘れた場合のエラー文・出力先の細部は、Python `argparse` の標準処理に委ねられており、このソース内で個別に定義されていません。

## 根拠

- `terminal/setup.py:11518` — `FILE` 値を取る parser 定義。help は `argparse.SUPPRESS` で非表示。
- `terminal/setup.py:11606-11618` — 引数解析後の順序と、非空値に対する終了コード `2`。
- `terminal/setup.py:961-999`, `terminal/setup.py:12565-12571` — JSONL 時の標準出力切替、人向けメッセージと終了イベント。
- `terminal/strata_control/retired.py:42-43` — 廃止オプションに使うメッセージ。
- `setup.sh:7-17`, `START-HERE.bat:53-64` — wrapper から `setup.py` への引数転送。
