# `strata drafting plan --help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata drafting plan` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ。既定値はありません。 |

## 役割

`strata drafting plan` の使用法と、その parser が受け付けるオプション一覧を表示して終了します。plan の計画結果を表示する処理や drafter の取得処理には進みません。

## 使い方

```console
strata drafting plan --help
strata drafting plan -h
```

いずれも同じ `drafting plan` parser のヘルプを表示します。調査対象 revision の `python strata.py drafting plan --help` でも、`-h, --help` と `--data-dir`、`--config`、`--family`、`--mode`、`--output` が表示されることを確認しました。

## 値と既定値

- `--help` と `-h` は値を受け取りません。独自の型変換、選択肢、値検証はありません。
- `drafting plan` は `argparse` の `add_parser()` で作成され、`add_help=False` を指定していません。トップレベルも `argparse.ArgumentParser` で構築されるため、argparse が通常追加する `-h` / `--help` が有効です。
- このオプション自体に設定値や既定値はありません。

## 実行時の動作

ヘルプは parser が `drafting plan` 用に組み立てた使用法とオプション一覧を stdout に表示して終了します。値をファイル・設定・環境変数に反映したり、plan やダウンロード結果を生成したりしません。`drafting_cmd.run()` が呼ばれる前に argparse の help action が終了するため、`_inputs()`、`drafting.needs_pack()`、`drafting_fetch.plan()` を実行しません。

コマンド parser には `--data-dir DIR`、`--config FILE`、`--family NAME`、`--mode {auto,mtp,dflash2,off}`、`--output {human,json,jsonl}` が定義されています。これらは同じ `drafting plan` スコープのヘルプに列挙されます。

## 適用条件と副作用

ヘルプ表示後は終了コード `0` で終わります。通常の plan 実行やネットワーク取得は行われません。ただし `strata_cli.cli.main()` は parser を作る前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows では現在のプロセス token の既定 owner / DACL を設定しようとし、Windows 以外では何もしません。したがって、ヘルプ action による後続コマンド処理はありませんが、プロセス初期化処理は parser より先に通ります。

未知の引数は `parse_known_args()` 後に検出され、`drafting` は launch/connect の特別扱いに該当しないため `ap.error()` へ進みます。これは通常 stderr に usage とエラーを表示して終了コード `2` となる経路です。

## 出力とエラー

- ヘルプ本文は標準出力に表示され、argparse の help action が parser を終了します（終了コード `0`）。
- 不正なオプションなどの parser エラーは `main()` の `ap.error()` 経由で処理されます。ヘルプ表示とは異なり、stderr にエラーを出して終了コード `2` となります。

## 根拠

- `strata_cli/cli.py:40-45` — CLI root parser の `argparse.ArgumentParser` と必須 subparser 群。
- `strata_cli/cli.py:172-173` — `drafting_cmd.add_parser(sp)` を呼び、Terminal CLI に drafting parser を登録。
- `strata_cli/drafting_cmd.py:17-29` — `drafting` と `plan` の parser 作成、および `plan` に属するオプション。`add_help=False` の指定はありません。
- `strata_cli/cli.py:2217-2231` — parser 作成・`parse_known_args()` の順序、未知引数のエラー処理。
- `strata_cli/cli.py:2144-2146` — 通常処理では `drafting_cmd.run(a)` に委譲。
- `strata_cli/drafting_cmd.py:57-73` — plan 実行時にのみ入力解決・必要性判定・plan 結果出力を行う処理。
- `strata_control/private_files.py:349-385` — `adopt_user_defaults()` の Windows token 設定と非 Windows での no-op。
- 補助確認: 同一 checkout で `python strata.py drafting plan --help` を実行し、表示された alias・使用法・option 一覧を parser 定義と照合。
