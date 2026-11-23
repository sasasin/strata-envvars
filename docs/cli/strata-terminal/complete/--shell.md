# `strata complete --shell`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata complete` |
| オプション | `--shell` |
| 別名 | なし |
| 値 | `bash`、`zsh`、`fish` のいずれか |

## 役割

出力する `strata` コマンド用のタブ補完スクリプトの対象シェルを選びます。`strata complete` が現在の CLI parser からコマンド階層・オプション・固定選択肢を含むスクリプトを組み立てて標準出力へ出力します。シェルの設定ファイルへの追記や補完の有効化はこのオプションの処理では行いません。

## 使い方

```sh
strata complete                         # bash 用スクリプトを標準出力へ出す
strata complete --shell zsh             # zsh 用スクリプトを標準出力へ出す
strata complete --shell fish            # fish 用スクリプトを標準出力へ出す
```

## 値と既定値

- `bash`、`zsh`、`fish` のいずれかを指定します。parser の `choices` による制約で、それ以外の値は受理されません。
- 省略時は `bash` です。
- 別名はありません。`--shell` は `complete` サブコマンドに登録されています。

## 実行時の動作

`main` は `complete` の場合に `completion.script(parser(), a.shell)` を呼び、その戻り値を `sys.stdout.write` で出力して終了コード `0` を返します。生成処理は parser を `walk` してコマンド・サブコマンドとオプションを収集し、選択肢のあるオプションについてはその候補値も含めます。

- `bash` は Bash completion 関数と `complete -F` 登録行を生成します。
- `zsh` は Bash completion 層を初期化する行を付け、Bash 用関数を利用するスクリプトを生成します。
- `fish` は `complete` コマンドの登録行を生成します。

## 適用条件と副作用

`--shell` は `strata complete` の実行時だけ参照されます。出力先は標準出力であり、ソース上この処理によるファイル書き込み、シェル起動、設定ファイル変更はありません。利用者が出力をリダイレクトした場合のファイル操作は、そのシェルのリダイレクトによるもので、この処理自体の副作用ではありません。

## 出力とエラー

成功時は選択したシェル用スクリプトを標準出力へ書き、`0` を返します。選択肢外の値を渡すと `argparse` の parser validation で拒否されます（CLI の通常の parser error として stderr に usage/error を出して終了コード `2`）。

## 根拠

- `terminal/strata_cli/cli.py:62-66` — ルート parser と必須のサブコマンド登録。
- `terminal/strata_cli/cli.py:536-538` — `complete` サブコマンド、および `--shell` の候補値・既定値。
- `terminal/strata_cli/cli.py:2231-2234` — 選択値で生成関数を呼び、標準出力へ書いて `0` を返す実行経路。
- `terminal/strata_cli/cli.py:2325-2334` — parser が引数を解析し、未認識引数をエラーにする経路。無効な `choices` 値も `argparse` の解析時に拒否される。
- `terminal/strata_cli/completion.py:11-12` — 対応シェル一覧。
- `terminal/strata_cli/completion.py:23-38` — parser からサブコマンド、オプション、固定選択肢を収集する処理。
- `terminal/strata_cli/completion.py:52-85` — Bash 用スクリプトの生成。
- `terminal/strata_cli/completion.py:88-95` — zsh 用スクリプトの生成方法。
- `terminal/strata_cli/completion.py:98-118` — fish 用スクリプトの生成。
- `terminal/strata_cli/completion.py:121-122` — シェル名から生成関数を選ぶ処理。
- `docs/cli/README.md:1020-1023` — `strata complete` と `--shell` の索引登録および文書パス。
