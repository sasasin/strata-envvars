# `strata code --help` (`-h`)

- 対象: Strata Terminal CLI の `code` コマンド parser
- 調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`
- 調査日: 2026-10-25

## 役割

`strata code` が受け付ける共通オプションとサブコマンドを表示する。トップレベルの `strata --help` や、`strata code run --help`、`strata code sessions --help` とは別の parser スコープである。索引でも `strata-terminal/code` のオプションとして登録されている。

## 使い方

```sh
strata code --help
strata code -h
```

## 値と既定値

値は取らない。`strata_cli/cli.py` は `argparse.ArgumentParser` を通常の `add_help=True` で作成し、そのサブパーサーとして `code` を追加している。`argparse` の標準動作により `--help` と `-h` が自動登録され、ヘルプを表示して終了する。独自の既定値・validation は定義されていない (`strata_cli/cli.py:40-45, 494-499`)。

## 実行時の動作

ヘルプには `code` の共通オプション (`--workspace`、`--resume`、`--quiet`) と `run` / `sessions` サブコマンドが含まれる。`run` と `sessions` 自身のオプションは、それぞれの help parser に属するため、この文書の対象外 (`strata_cli/cli.py:494-507`)。

`main()` は parser の解析後に `_run()` へ進むが、標準 help action は解析中に表示して終了する。そのためこの指定では `code` のコマンド処理や共有 Desktop harness の可用性確認には進まない (`strata_cli/cli.py:2217-2237`)。

## 適用条件と副作用

ヘルプ内容は実行時に parser 定義から生成され、固定の文面ではない。幅などに応じた表示整形は `argparse` に委ねられている。コード上、`main()` は引数解析の前に `private_files.adopt_user_defaults()` を呼ぶ。この関数は Windows 以外では何もせず、Windows では以降にプロセスが作成するファイルの owner/default access を現在のユーザー向けにする処理を試みる。help action がこの呼び出しを飛ばす構造ではない (`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-360`)。

この help 呼び出し自体はモデル、GPU、サーバー、ネットワークを起動する処理を呼ばない。なお `strata code` を help なしで実行すると、共有 Desktop harness が未インストールとして終了コード5を返す実装である。従って parser がコマンドとそのオプションを掲載することは、機能が利用可能であることを意味しない (`strata_cli/cli.py:2162-2164`; `docs/TERMINAL.md:275-277`)。

## 出力とエラー

標準出力に `code` parser の usage、説明、オプション、サブコマンドを表示して終了コード0となるのが `argparse` の標準 help action の挙動である。`strata_cli/cli.py` にこの help 用の独自出力処理や、help 表示専用のエラー経路はない。実際の端末出力は実行していないため、具体的な整形結果は記録しない。

## 根拠

- `strata_cli/cli.py:40-45` — ルート parser とサブコマンドの構築。
- `strata_cli/cli.py:494-507` — `code` parser、共通オプション、子 parser。
- `strata_cli/cli.py:2217-2237` — 実行時の事前処理と引数解析。help action 後に通常 dispatch へ進む構造ではない。
- `strata_cli/cli.py:2162-2164` — `code` の実処理が harness 不在として終了コード5を返す。
- `strata_control/private_files.py:349-360` — 引数解析前に呼ばれる owner/access 設定処理の条件。
- `docs/TERMINAL.md:275-277` — Terminal 文書に記載された harness 機能の制約。
- 索引: [`docs/cli/README.md`](../../README.md) の `strata code` 節で `--help`（alias `-h`）を確認。

調査は上記 revision のソース読み取りに基づく。CLI の実行、build、テスト、GPU 実行は行っていない。
