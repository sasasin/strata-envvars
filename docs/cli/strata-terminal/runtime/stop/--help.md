# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime stop` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`strata runtime stop` の構文と、このサブコマンドで受け付けるオプションを表示して終了します。Strata の runtime を停止する処理には進みません。

## 使い方

```sh
strata runtime stop --help
strata runtime stop -h
```

## 値と既定値

値は不要です。`-h` は `--help` の短縮別名です。Strata は `runtime` のサブコマンドとして `stop` parser を作成し、その parser に `--profile`、`--plan`、`--wait`、`--if-owner-id`、`--if-instance-id`、`--output` を登録します。さらに one-shot parser 群への共通登録で `--json` と `--quiet` も追加されます。実行時の同一 revision の help 出力には、これらがすべて表示されます。

## 実行時の動作

help は `runtime stop` の parser が持つ構文説明とオプション一覧を標準出力に表示して終了します。通常の runtime 処理は parser の後で `_run` から呼ばれますが、help 表示で引数解析が終了するため、`management.runtime_action()` や stop 要求は実行されません。ファイル、プロセス、ネットワークへの副作用はありません。

この help の利用可能範囲は `strata runtime stop` です。トップレベルの `strata --help` や他の `runtime` サブコマンドの help とは別 parser の出力です。

```text
usage: strata runtime stop [-h] --profile PROFILE [--plan] [--wait WAIT]
                           [--if-owner-id IF_OWNER_ID]
                           [--if-instance-id IF_INSTANCE_ID]
                           [--output {human,json}] [--json] [--quiet]
```

`--profile` は必須です。`--wait` の parser 既定値は 330 秒、`--output` の既定値は `human` です。`--plan` は停止せず owner と instance の確認用プランを返します。`--if-owner-id` / `--if-instance-id` は停止実行時に plan で確認した識別子を条件として渡すためのオプションです。これらの sibling option の詳しい挙動は索引の各文書を参照してください。

## 適用条件と副作用

コマンド固有 parser の help なので、`runtime stop` を選択した後に適用されます。help 自身は runtime 状態の確認や変更を行いません。表示される `--json` と `--quiet` は `runtime stop` を含む one-shot parser 群に追加される CLI 共通オプションです。

## 出力とエラー

`strata runtime stop --help` の補助確認では、usage と `-h, --help show this help message and exit` を含むオプション一覧が表示されました。help 出力は標準出力です。通常の引数解析では未知の引数が `ap.error(...)` に送られる経路がありますが、`--help` は help 表示後に解析を終了するため、そのエラー経路には進みません。

## 根拠

- `strata_cli/cli.py:40-46` — トップレベル `argparse.ArgumentParser` とサブコマンド parser 群の生成。
- `strata_cli/cli.py:226-232` — `runtime stop` parser と固有オプションの登録。
- `strata_cli/cli.py:508-515` — one-shot parser 群（`runtime_stop` を含む）への `--json` / `--quiet` 登録。
- `strata_cli/cli.py:1345-1358` — 通常実行時の `management.runtime_action()` 呼び出しと、成功した `--plan` の出力経路。
- `strata_cli/cli.py:2223-2235` — 引数解析と未知引数のエラー処理。
- `strata_control/management.py:271-291` — `stop` の wait 検証、plan 分岐、ID 条件確認後の停止処理への委譲。
- 同一 commit の補助確認: `python strata.py runtime stop --help`。出力された usage は上記 parser と一致しました。
