# `strata bench compare --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench compare` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプを表示して終了する |

## 役割

`compare` サブコマンドの利用法と、その parser が受け付ける位置引数・オプションを表示する。`strata bench` や `strata bench run` の help とは別スコープである。`bench compare` は保存済みの baseline と candidate のベンチマーク結果を比較するコマンドだが、`--help` の指定では比較を実行しない。

## 使い方

```sh
strata bench compare --help
```

短縮別名も使用できる。

```sh
strata bench compare -h
```

## 値と既定値

値は不要。`-h` と `--help` は `argparse` の標準 help action として自動追加される。help action が実行されると usage と説明を標準出力へ表示し、終了コード 0 で parser を終了する。内容は `compare` parser の定義（必須位置引数 `baseline`、`candidate`、`--output`、`--out`）から生成される。help 自体に設定可能な既定値はない。

## 実行時の動作

トップレベル parser は `argparse.ArgumentParser(prog="strata", ...)` で作られ、`bench` とその必須サブコマンド群の中に `compare` parser が登録される。`compare` parser には `baseline` と `candidate` の位置引数、`--output`（`human` / `json` / `markdown`、既定値 `human`）、`--out` が定義されている。標準 help action はこれらの定義を表示し、`parse_known_args` の後にあるコマンド実行分岐へ進む前に終了する。そのため `--help` だけを指定した場合、入力 report の読み込み、比較、Markdown 出力ファイルの作成は行われない。

`--help` を付けず実行した場合は `baseline` と `candidate` を `bench.load` で読み込み、`bench.compare` が比較する。両 report が成功済みで run ID が異なること、suite/model ID・phase 数・request workload が一致することなどが必要で、環境情報の不一致などは比較失敗、情報不足は warning となる。これは help の効果ではなく、コマンド本体の動作である。

## 適用条件と副作用

`strata bench compare` の parser でのみ有効。`strata bench --help` など親 parser の help は別の parser scope である。help の表示はローカルの report を読み込まず、ネットワーク接続、ベンチマーク実行、設定変更、ファイル作成を伴わない。

## 出力とエラー

標準出力に `compare` の usage、位置引数、オプションの説明を表示して終了コード 0 となる。help action が実行される前に parser が構文不正と判断した場合は argparse の usage/error を表示し、終了コード 2 となる。通常実行で発生する report の読み込み・比較エラーは `ValueError` 等として CLI のエラー処理へ送られ、human mode では `strata: ...` を標準エラーへ出力する。help 表示ではこの report 処理経路に入りません。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル `argparse` parser とサブコマンド parser の生成。
- `strata_cli/cli.py:291-293` — `bench` と必須サブコマンドの登録。
- `strata_cli/cli.py:343-347` — `compare` parser、位置引数、`--output` と `--out` の定義。`add_help=False` の指定がなく標準 help action が有効。
- `strata_cli/cli.py:2217-2231` — `parse_known_args` を実行し、未知引数は parser error とする処理。help action はこの parse の中で表示・終了する。
- `strata_cli/cli.py:1129-1134,1163-1174` — compare 通常実行での `--out` 条件、report 読み込み、比較結果の表示・Markdown 出力。
- `strata_cli/cli.py:2119-2173` — コマンド dispatch と `ValueError` のエラー処理。
- `strata_cli/bench.py:891-900` — 保存済み report のファイル選択と読み込み失敗処理。
- `strata_cli/bench.py:1006-1048` — 比較対象の成功状態、run/suite/model/workload/environment の確認と warning。
