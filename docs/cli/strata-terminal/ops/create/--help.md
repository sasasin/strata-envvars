# `strata ops create --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops create` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`strata ops create` の構文と、このサブコマンドで使える引数・オプションの説明を表示します。`--help` は `create` の parser に対するヘルプであり、`strata --help` や `strata ops --help` とは表示対象が異なります。

## 使い方

```sh
strata ops create --help
strata ops create -h
```

## 値と既定値

値を取りません。`strata_cli.cli` は `argparse.ArgumentParser` を使い、`ops` と `create` の parser を `add_parser()` で生成しています。`add_help=False` は指定されていないため、Python `argparse` の標準ヘルプ引数 `-h` / `--help` が有効です。

表示される `create` の引数には、位置引数 `name`、必須の `--profile`、必須の `--kind`（`runtime.restart`、`engine.calibrate.measure`、`components.verify` のいずれか）、`--output`（`human` または `json`、既定値 `human`）が含まれます。また one-shot コマンド共通の `--json` と `--quiet` も追加されます。これらはヘルプ表示の対象となる構文であり、`--help` 自体の値ではありません。

## 実行時の動作

通常の `strata ops create` は `NAME`、`--profile`、`--kind` を受け取り、レシピ作成処理へ進みます。`--help` が指定されると parser がヘルプを表示して終了するため、通常の引数検証や `_run()` / `_ops()` のレシピ作成分岐には進みません。したがって、このフラグによってレシピや履歴が作成・更新されることはありません。

CLI の `main()` は parser を処理する前に `private_files.adopt_user_defaults()` を呼びます。この処理は Windows ではプロセスの既定 owner と既定 DACL の設定を試み、失敗しても例外を送出しません。POSIX では何もしません。これはヘルプ固有の処理ではなく、CLI 起動時に共通する前処理です。

## 適用条件と副作用

この `--help` は `strata ops create` の parser スコープです。ヘルプ表示自体はレシピ、プロファイル、サーバーを変更せず、ネットワーク接続や子プロセス起動にも進みません。前述の Windows のプロセストークン既定値設定だけは parser より前に試行されます。

## 出力とエラー

標準出力に usage と `create` parser の説明を表示して正常終了（終了コード 0）します。ヘルプ action は必須の `name`、`--profile`、`--kind` を満たしていなくても表示できるため、これらを指定しない `strata ops create --help` は引数不足エラーになりません。`--help` を付けない場合に必須引数が欠けていれば、argparse の parser エラーになります。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser と `argparse` サブコマンド parser の設定。
- `strata_cli/cli.py:255-272` — `ops create` の登録、`name`、必須の `--profile` / `--kind`、`--output` の定義。
- `strata_cli/cli.py:508-515` — one-shot parser 群に `--json` と `--quiet` を追加する処理（`ops_items` に `create` を含む）。
- `strata_cli/cli.py:2217-2237` — parser 前の Windows user-defaults 処理、`parse_known_args()` と通常実行への分岐。
- `strata_control/private_files.py:349-389` — `adopt_user_defaults()` の Windows 限定処理と失敗時の戻り方。
- `strata_cli/cli.py:1391-1415` — `ops create` の通常実行時に `recipes.create()` を呼び、成功結果を表示する経路。
