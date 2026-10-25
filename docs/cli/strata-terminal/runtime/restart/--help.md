# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime restart` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`runtime restart` の使い方と、そのサブコマンドで受け付けるオプションを表示して終了します。これは `runtime` 全体やトップレベルのヘルプではなく、`restart` parser のヘルプです。

## 使い方

```sh
strata runtime restart --help
```

短縮形も使えます。

```sh
strata runtime restart -h
```

## 値と既定値

値を取りません。`argparse.ArgumentParser` の標準ヘルプ action により `--help` と `-h` が登録されます。適切な位置引数・オプション値の後に値を付ける形式ではありません。

## 実行時の動作

ヘルプは `runtime restart` parser の引数一覧を標準出力へ表示し、引数解析を終了します。そのため `--profile` が必須であってもヘルプ表示には不要で、`_run()` の `runtime` 分岐や `_runtime()`、`management.runtime_action()` には到達しません。再起動・停止・待機・plan の実行、JSON 出力への切替は行われません。

表示対象には restart 固有の `--profile`、`--plan`、ソース変更許可、待機時間、実行前提条件、`--output` が含まれます。また one-shot parser 共通処理で追加される `--json` と `--quiet` もこの parser のヘルプ対象です。

## 適用条件と副作用

`main()` は引数解析より前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows では現在のプロセスの既定 owner と DACL を設定しようとしますが、失敗しても例外を送出せず、戻り値は CLI で使われません。POSIX では何もしません。ヘルプ自体は実行時管理処理に進まないため、Strata runtime の再起動に伴うプロセスやサーバーの変更はありません。

## 出力とエラー

標準 argparse のヘルプ action が usage と説明・オプション一覧を標準出力へ出し、終了コード `0` で終了します。値を要する他のオプションの不正値検証や runtime の失敗経路は実行されません。`--help` 自体には値検証・副作用はありません。

## 根拠

- `strata_cli/cli.py:40-46` — トップレベル parser は `argparse.ArgumentParser` を使用し、標準の help action を無効化していません。
- `strata_cli/cli.py:197-202` — `runtime` parser と `runtime` サブコマンド群を定義。
- `strata_cli/cli.py:238-254` — `restart` parser の説明と固有オプションを定義。
- `strata_cli/cli.py:508-515` — `runtime_restart` を one-shot parser 群に含め、`--json` と `--quiet` を追加。
- `strata_cli/cli.py:2217-2237` — ユーザー引数を parse する前の初期化と解析後の dispatch。標準 help action は解析を終了するため後続処理に進まない。
- `strata_cli/cli.py:2119-2160` — 通常実行時の `_run()` における `runtime` dispatch。
- `strata_control/private_files.py:349-389` — Windows の既定 owner/DACL 初期化の条件と、失敗時に例外を送出しない処理。
- `docs/cli/README.md:451-468` — `strata runtime restart` の索引上の階層、`--help` と alias `-h`。
