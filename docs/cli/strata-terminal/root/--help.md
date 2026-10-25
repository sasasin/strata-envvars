# `strata --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata`（トップレベル） |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。トップレベルの使用法、説明、サブコマンド、トップレベル option を表示する。 |
| 既定値 | `--help` を指定しない場合はヘルプを表示しない。 |

## 役割と適用範囲

`strata --help` は Terminal CLI のトップレベル parser のヘルプを表示して終了します。トップレベル parser は `prog="strata"`、説明 `Strata serving and terminal clients` で作られ、`--version` と必須のサブコマンド群を登録します（`strata_cli/cli.py:40-45`）。`argparse.ArgumentParser` に `add_help=False` を指定していないため、標準の `--help` と `-h` が同じ parser action として利用できます。

この文書の scope はトップレベルだけです。たとえば `strata serve --help` や `strata launch --help` はそれぞれサブコマンド parser のヘルプで、別スコープです（`strata_cli/cli.py:45-46,488-490`）。索引も同じ階層で別文書に分けています（[CLI 索引](../../README.md)）。

## 使い方

```sh
strata --help
strata -h
```

値を付けないフラグです。位置引数やサブコマンドがなくても、help action が処理されればサブコマンド必須条件によるエラーにはなりません。表示内容はこの revision で parser に登録されたトップレベル command/option 定義から生成され、サブコマンド固有の全 option 一覧を一括表示するものではありません。

## 実行時の動作と副作用

配布 wrapper の `strata.py` は CLI 本体を読み込む前に updater の handover/refusal 判定を行い、その後 `_preflight()` を実行します。preflight は最初の非 option token が `serve` または `bench` の場合だけ server 依存パッケージを確認し、それ以外は成功扱いで本体へ進みます。通常の `strata --help` / `strata -h` はこの依存チェックの対象外です（`strata.py:30-42,14-18`）。handover 判定が特定の環境状態で何をするかは `--help` 固有の処理ではなく、ここでは配布・インストール状態ごとの差を調査していません。

CLI 本体の `main()` は parser を構築する前に `strata_control.private_files.adopt_user_defaults()` を呼びます。関数は Windows 以外では `False` を返して何もせず、Windows ではプロセスが以後作るファイルの既定 owner と DACL を現在ユーザー向けに設定しようとします。失敗時も例外を外へ出さず `False` を返します。この呼び出しは help 解析より前であり、設定を試みる処理自体は `--help` 表示にも伴います（`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-389`）。

`argparse` の help action がヘルプを出力して解析を終了するため、通常は `parse_known_args()` の後にある未認識引数処理や `_run()` へ進みません（`strata_cli/cli.py:2223-2237`）。従って help action 自体はサーバー起動やコマンド実行を行いません。

## 出力と失敗経路

標準 `argparse` の help action によりヘルプ本文を標準出力へ出し、終了コード `0` で終了します。トップレベル parser に独自 help action は登録されていません（`strata_cli/cli.py:40-45`）。通常のヘルプ解析後の未知引数は `ap.error()` によりエラーになりますが、help action が先に処理される呼び出しではその経路へ到達しません（`strata_cli/cli.py:2223-2231`）。

この挙動は指定 revision のソースから確認しました。CLI の実出力を取得するためのコマンド実行、Release archive/wrapper との照合は行っていません。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser、説明、`--version`、必須サブコマンド parser の定義。標準 help action を無効化していない。
- `strata_cli/cli.py:486-490` — `launch` と他の parser 群をトップレベルへ登録する位置。
- `strata_cli/cli.py:2217-2237` — `main()` の事前処理、引数解析、未知引数分岐、実行分岐。
- `strata_control/private_files.py:349-389` — Windows の既定 owner/DACL 設定と失敗時の戻り値。
- `strata.py:14-27,30-42` — source entry point の依存 preflight と CLI 本体を呼び出す前の handover 判定。
