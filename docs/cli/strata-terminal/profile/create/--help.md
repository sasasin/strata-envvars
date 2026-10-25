# `strata profile create --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile create` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`strata profile create` の usage と、そのサブコマンドで使える引数・オプションを表示します。`--help` は `create` parser のスコープであり、`strata --help` や `strata profile --help` とは表示対象が異なります。

## 使い方

```sh
strata profile create --help
strata profile create -h
```

## 値と既定値

値を取りません。`strata_cli.cli.parser()` は標準の `argparse.ArgumentParser` を使い、`profile` の下に `create` parser を作っています。サブパーサーに `add_help=False` は指定されていないため、`-h` / `--help` は argparse 標準の help action です。

help の表示対象には位置引数 `name`、必須の `--from-config CONFIG.json`、`--output`（`human` または `json`、既定値 `human`）、one-shot 共通の `--json` と `--quiet` が含まれます。これらは `create` の構文に属する項目で、`--help` 自体の値や既定値ではありません。

## 実行時の動作

help action が parser の引数解析中に usage と説明を表示して終了します。そのため、必須の `name` や `--from-config` を省略しても help を表示でき、通常実行時の `_run()` / `_profile_command()` にある `profiles.create()` は呼ばれません。プロファイルの検証・保存、設定ファイルの読込は help によって行われません。

`strata.py` から起動するときは、parser より前に handover 判定、preflight、`main()` 内の user-defaults 処理があります。handover は source checkout では通常行われず、preflight は `serve` / `bench` 以外では依存パッケージ検査を行いません。`adopt_user_defaults()` は Windows 以外では何もせず、Windows でも失敗時に例外を送出しません。これらは `--help` 固有の動作ではなく CLI 共通の起動前処理です。

## 適用条件と副作用

help 表示自体は profile データや run config を作成・変更せず、ネットワーク接続や profile 作成処理にも進みません。標準出力への usage 表示が行われます。CLI の起動前処理は上記のとおり別途実行されます。

## 出力とエラー

argparse の標準 help action は usage と `create` parser の説明を標準出力に表示し、終了コード 0 で終了します。help action が先に parser を終了させるため、通常実行で必須の `name` / `--from-config` は help 表示の条件ではありません。`--help` を付けず必須引数が不足した場合は argparse の usage/error 経路（終了コード 2）になります。

## 調査範囲

指定 commit の parser、dispatch、profile 作成処理、および CLI 起動前処理をソースで確認しました。同 revision の CLI help は実行しておらず、表示項目は parser 定義から確認しています。Windows の token owner / default DACL 設定の実際の成否、およびインストール済み bundle や Release artifact の挙動は実機確認していません。

## 根拠

- `strata_cli/cli.py:40-45` — `argparse.ArgumentParser` による root parser と標準 help を有効にした command parser の構築。
- `strata_cli/cli.py:69-75` — `profile create` parser、`name`、必須 `--from-config`、`--output` の定義。
- `strata_cli/cli.py:508-515` — `profile_create` を含む one-shot parser 群に `--json` と `--quiet` を追加する処理。
- `strata_cli/cli.py:2217-2237` — `main()` の user-defaults 処理、`parse_known_args()`、parse 後の通常 dispatch。
- `strata_cli/cli.py:2119-2128` — parse 成功後に通常処理を `_run()` から `_profile_command()` へ渡す経路。
- `strata_cli/cli.py:958-963` — 通常の `profile create` 実行で `profiles.create()` を呼び、成功結果を出力する箇所。
- `strata_control/profiles.py:25-55,135-147,236-249` — 通常の作成時に適用される profile 名、run config の検査、既存 profile の拒否、保存処理。help action では到達しない。
- `strata.py:14-27,30-43` — entrypoint の handover / preflight と、`serve` / `bench` 以外では preflight が依存検査をしない条件。
- `strata_cli/handover.py:27-29,126-144` — checkout 判定と handover 条件。
- `strata_control/private_files.py:349-389` — Windows 限定の `adopt_user_defaults()` と失敗時に例外を送出しない処理。
- `docs/cli/README.md:57-65` — 索引における `strata profile create` の階層と `--help`（`-h`）のリンク。
