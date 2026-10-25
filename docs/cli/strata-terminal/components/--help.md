# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし。ヘルプ表示用のフラグ |

## 役割

`strata components` parser の使い方と登録済みサブコマンドを表示します。Strata の処理本体を実行せず、CLI の利用方法を確認するためのものです。

## 使い方

```sh
strata components --help
```

`python strata.py components --help` はソース checkout から起動する場合の形です。サブコマンドのヘルプは別スコープで、たとえば `strata components verify --help` は [`verify` の `--help`](verify/--help.md) を参照してください。

## 値と既定値

値を取りません。短縮形 `-h` は同じヘルプ表示を行います。CLI は `argparse.ArgumentParser` を使い、`components` とその子 parser のいずれも `add_help=False` を指定せずに作られているため、Python `argparse` の標準ヘルプ action が各 parser に自動追加されます。`components` 自体の明示的なヘルプ action、型変換、独自の値検証や既定値設定はありません（根拠: `strata_cli/cli.py:40-45`, `strata_cli/cli.py:114-140`）。

## 実行時の動作

ルート parser は `prog="strata"` で構成され、`components` parser の説明は「read-only installed component inventory」です。`strata components --help` はその説明、使用形式、登録された子コマンドと各説明を表示します。ソース上で `components` に登録されるのは `verify`、`plan`、`backends`、`engine` と、`update_cmd.add_parsers` が追加する `update` / `rollback` です（根拠: `strata_cli/cli.py:40-45`, `strata_cli/cli.py:114-140`, `strata_cli/update_cmd.py:42-59`）。

`argparse` の help action はヘルプを標準出力へ書き、parser を終了するため、サブコマンドの実行処理には進みません。通常の dispatch は引数解析後に `_run` で行われ、`components` の各処理はそこで初めて選択されます（根拠: `strata_cli/cli.py:2119-2140`, `strata_cli/cli.py:2217-2237`）。

## 適用条件と副作用

この help は `components` parser のスコープです。サブコマンドより前に指定します。`strata components verify --help` などサブコマンド名の後に指定した場合は、その子 parser のヘルプになります。`components` ではサブコマンドが必須として宣言されていますが、`--help` は parser 終了 action なので、サブコマンドがないことのエラーには進みません（根拠: `strata_cli/cli.py:114-115`）。

ヘルプ処理自体は component の読み取り、ネットワーク取得、ファイル変更を行いません。ただし `main()` は引数解析より前に `private_files.adopt_user_defaults()` を呼びます。これは Windows ではプロセス token の既定 owner / DACL を調整し、他 OS では何もしません。したがって、ヘルプ action に到達するまでのプロセス初期化を含めて副作用が皆無とはいえません（根拠: `strata_cli/cli.py:2217-2224`, `strata_control/private_files.py:349-389`）。

## 出力とエラー

有効な `strata components --help` はヘルプを stdout に出して終了コード `0` で終了します（`argparse` の標準 help action）。一方、`strata components` のように help も子コマンドも指定しない呼び出しは、`components` の required subparsers により usage とエラーを stderr に出して終了コード `2` になります。引数解析の後に余分な未認識引数が残る場合も `ap.error(...)` でエラーになります（根拠: `strata_cli/cli.py:114-115`, `strata_cli/cli.py:2223-2231`）。

この調査では CLI を実行して出力文面を採取していません。ソース checkout の入口 `strata.py` は `main()` より先に updater の handover 判定と preflight を行います。これらの起動経路を含む実行時の挙動は実行して確認していません。上記の終了・出力動作は `argparse` 標準 action と、Strata 側の parser / 呼出し経路に基づく説明です（`strata.py:30-42`）。

## 根拠

- `strata_cli/cli.py:40-45` — `argparse.ArgumentParser` による root parser と `strata` の program 名。
- `strata_cli/cli.py:114-140` — `components` parser、必須サブコマンド parser、子 parser の登録。
- `strata_cli/update_cmd.py:30-58` — `components` に追加される update / rollback parser。
- `strata_cli/cli.py:2119-2140` — 引数解析後に行う `components` の dispatch。
- `strata_cli/cli.py:2217-2231` — 初期化、`parse_known_args`、未認識引数のエラー処理。
- `strata_control/private_files.py:349-389` — `adopt_user_defaults()` の OS 条件と Windows token 設定。
