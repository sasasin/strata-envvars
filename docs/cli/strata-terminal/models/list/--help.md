# `strata models list --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models list` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`strata models list` の usage と、その parser に属するオプションの説明を標準出力に表示して終了します。`strata models --help` は親 `models` parser のヘルプであり、この文書の対象とは別です。

## 使い方

```sh
strata models list --help
strata models list -h
```

## 値と既定値

値は不要です。`models list` は `argparse.ArgumentParser` の既定設定（`add_help=True`）で作られ、明示的な help action の上書きもありません。そのため `-h` と `--help` が自動で同じ help action に登録されます。既定 help action は引数値を受け取りません。

表示される `models list` 固有の引数には、`--installed` / `--served`、`--install-dir`、`--url`、`--connection`、`--credential-env`、`--timeout`、`--output` のほか、後から共通 one-shot 引数として加わる `--json` と `--quiet` があります。`--installed` と `--served` は相互排他的です。help の出力内容は Python `argparse` が parser 定義から生成します。

## 実行時の動作

Python CLI の標準 parser help action がヘルプを印字し、parser を終了させるため、通常の `_run()` / `_models()` によるモデル一覧取得処理には進みません。ヘルプを表示して終了すること自体は `models.list_installed()` やサーバーへの snapshot 要求を行いません。

ただし、CLI の `main()` は parser の構築・引数解析より先に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows でプロセスの既定 owner と default DACL の設定を試み、失敗しても例外を送出しません。非 Windows では何もしません。したがって `--help` の処理経路にもこの起動時処理は含まれます。

## 適用条件と副作用

`-h` と `--help` は同一の `models list` parser で機能します。標準 `argparse` の help action は help を標準出力へ出し、終了 status 0 で parser を終了します。オプション名だけを示すため、`--help` と他の `models list` オプションを同時に指定しても、それらの実行時効果は起きません。

通常の引数構文エラーは `argparse` が usage とエラーを標準エラーへ出して status 2 で終了します。これは help action 自体の失敗経路ではありません。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser の生成とサブコマンド登録。
- `strata_cli/cli.py:141-152` — `models list` parser、相互排他グループ、個別オプションの宣言。`add_parser()` に `add_help=False` 等の指定はなく、標準 help action が使われます。
- `strata_cli/cli.py:508-515` — `models_list` を含む one-shot parser 群への `--json` と `--quiet` の追加。
- `strata_cli/cli.py:550-596` — list の実行経路。help action で終了しなかった場合に限り、ローカル一覧または `--served` の snapshot 取得へ進みます。
- `strata_cli/cli.py:2217-2231` — `main()` の起動時処理、parser 構築、引数解析、構文エラー処理。
- `strata_control/private_files.py:349-385` — `adopt_user_defaults()` の Windows 条件、既定 owner/DACL 設定と戻り値。

この文書では既存 CLI の help を実行しておらず、配布済み Release の CLI も照合していません。記述は上記 commit のソースと `argparse` の標準動作に基づきます。
