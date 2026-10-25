# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune rollback` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。Python `argparse` の標準 help action。 |

## 役割

`strata tune rollback` の使い方と、このサブコマンドに属する引数・オプションを表示します。この parser は `argparse.ArgumentParser` の既定の help を有効にしており、rollback 固有の help 処理や独自の出力形式は定義していません。

## 使い方

```sh
strata tune rollback --help
```

短縮形は `strata tune rollback -h` です。help の対象は `rollback` サブコマンドに限られます。親の `strata tune --help` は tune 全体のサブコマンド一覧を表示します。

## 値と既定値

値を取りません。値の validation、既定値、複数回指定時の独自動作はありません。`rollback` parser 自体は必須位置引数 `application_id` と、`--state-dir`（既定値 `None`）、`--output`（`human` / `json`、既定値 `human`）を定義しています。help はこれらを表示するためのもので、通常の rollback 実行に必要な `application_id` を指定する必要はありません。

## 実行時の動作

help は parser が引数を解析する段階で処理され、`_run` の tune rollback 分岐や `tune_apply.rollback` には進みません。従って、rollback の適用記録・保存済み設定の検査、設定ファイルの復元、rollback 記録の更新は help 表示では行われません。通常の rollback は `application_id` を `tune_apply.rollback` に渡し、成功すると保存されていた `before.json` の内容で対象設定を置換して記録を `rolled_back` にします。

エントリポイント `main` は parser を作る前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows でプロセスの token 既定 owner / DACL を設定しようとし、失敗しても例外を送出しない実装です。Windows 以外では何もしません。これは help action 自体による rollback 副作用ではありません。

## 適用条件と副作用

`--help` は `strata tune rollback` の parser で使用します。Python `argparse` 標準の help action により usage と parser の説明を表示して正常終了します。ヘルプ表示時には rollback 記録や設定ファイルに触れません。起動時の Windows token 既定値への best-effort な設定については「実行時の動作」を参照してください。

## 出力とエラー

標準出力に標準 help action による usage とコマンド説明・引数一覧を表示します。help action は終了コード 0 で parser を終了し、以後のコマンド dispatch を行いません。Strata 側にこの option 専用のエラー文や終了コードの上書きはありません。

参考として、通常の rollback では適用記録がない、既に rollback 済み、保存された変更前設定や対象設定がない、適用後に対象設定が変更された場合に `ApplyError` となります。CLI は人間向けでは `strata: ...` を stderr に出し、`--output json` ではエラー JSON を stdout に出します。help はこの rollback エラー経路を通りません。

## 根拠

- `strata_cli/cli.py:40-45` — `argparse.ArgumentParser` を生成し、トップレベル subparser を定義。
- `strata_cli/cli.py:395-397` — `tune` と必須の tune subcommand parser。
- `strata_cli/cli.py:472-475` — rollback parser と `application_id`、`--state-dir`、`--output` の定義。`ArgumentParser` は既定で `--help` / `-h` を追加。
- `strata_cli/cli.py:2217-2237` — parser 前の初期化、引数解析、dispatch への進み方。
- `strata_control/private_files.py:349-389` — Windows token 既定値設定の条件と best-effort 動作。
- `strata_cli/cli.py:1712-1713`, `1953-1963` — 通常 rollback の CLI dispatch、エラー処理、人間向け・JSON 出力。
- `strata_control/tune_apply.py:373-400` — rollback の記録・ファイル検査、変更後 hash の照合、復元と rollback 記録更新。
- `docs/cli/README.md:780-786` — 索引上の `strata tune rollback` の command path と `--help` alias・option scope。

同一 revision の CLI help 出力は実行していません。help の挙動は parser の `argparse.ArgumentParser` 宣言と標準 action に基づいています。配布済みバイナリの help 表示は調査していません。
