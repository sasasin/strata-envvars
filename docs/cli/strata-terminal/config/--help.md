# `strata config --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata config` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`config` コマンドの使い方と、その下にある `show` サブコマンドを表示します。接続設定の実値を表示する操作ではありません。値を調べるには `strata config show` を使います。

## 使い方

```sh
strata config --help
```

短縮形も同じ parser のヘルプを表示します。

```sh
strata config -h
```

## 値と既定値

値は不要です。`argparse.ArgumentParser` の既定のヘルプ action によって `-h` と `--help` が提供されるため、Strata 独自の既定値・型変換・値の validation はありません。明示値や複数回指定による設定変更もありません。

## 実行時の動作

Terminal CLI の parser は `strata` をプログラム名として作成され、monitor 系の parser 登録関数がトップレベルに `config` を追加します。`config` の下には `show` サブコマンドが必須として登録されています。`config --help` はそのサブコマンド一覧を含む `config` 用 usage/help を出力して終了します。

調査対象 revision の checkout で `python strata.py config --help` を実行した結果は次のとおりでした。これはソース checkout の補助確認であり、Release バイナリの出力を示すものではありません。

```text
usage: strata config [-h] {show} ...

positional arguments:
  {show}
    show      show connection and credential origins

options:
  -h, --help  show this help message and exit
```

help action は parser の引数解析中に実行されるため、通常の `config show` 分岐には進みません。したがって、接続先や credential の解決、ネットワーク要求、接続情報の出力は行いません。`show` は `config` に対する別の必須サブコマンドです。

## 適用条件と副作用

Terminal CLI が受け付ける `strata config` のスコープで使用します。表示と正常終了以外の Strata 側の副作用は確認されません。ヘルプ action は標準出力に usage と説明を出し、終了コード `0` で終了します。

## 出力とエラー

- 有効な `strata config --help` / `strata config -h`: usage と `show` の説明を標準出力に表示して終了コード `0`。
- `strata config` のように help もサブコマンドも指定しない場合: 必須の `show` がないため parser が usage/error を標準エラーに出し、終了コード `2` で終了します。

## 根拠

- `strata_cli/cli.py:40-41` — `argparse.ArgumentParser` を既定設定で作成。`add_help=False` の指定がなく、標準の `-h` / `--help` action が有効です。
- `strata_cli/cli.py:488-493` — Terminal CLI parser に monitor 系 parser 群を追加し、`add_connections` を通じて `config` をトップレベルに登録します。
- `strata_cli/cli.py:2217-2231` — CLI の parser 構築と引数解析。通常の未知引数は parser error 経路に送られます。
- `strata_cli/monitor_commands.py:96-103` — `config` と必須 `show` サブコマンド、および `show` の引数定義。
- `strata_cli/monitor_commands.py:132-139,167-175` — 通常の `config show` が接続設定を解決して出力する経路。help はこの実行分岐とは別です。
- 同一 revision の checkout で `python strata.py config --help` を実行し、実際の usage と `-h, --help` 表示を照合。
