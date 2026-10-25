# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops result` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`strata ops result` の使い方と、このサブコマンドが受け付ける引数・オプションを表示して終了します。ヘルプを表示するだけなら、必須の操作 ID と `--profile` を付ける必要はありません。

## 使い方

```sh
strata ops result --help
```

短縮形も使えます。

```sh
strata ops result -h
```

## 値と既定値

`--help` / `-h` は値を取りません。明示的な既定値や追加の値 validation はありません。`argparse.ArgumentParser` の標準 help action によって各 parser に自動で登録されます（`strata_cli/cli.py:40-45,255-267`）。

表示される `result` の引数には位置引数 `operation_id`、必須の `--profile`、`--output {human,json}`（既定値 `human`）があります。また、one-shot parser 共通の `--json` と `--quiet` も登録されています（`strata_cli/cli.py:262-267,508-515`）。

## 実行時の動作

parser は `ops` の下に `result` を登録し、`ops` と `result` のサブコマンド階層を必須にしています。`result` を選ぶと `operation_id` を要求し、`--profile` を必須にします（`strata_cli/cli.py:255-267`）。

help action が実行されると usage と引数一覧を標準出力に表示し、終了コード `0` で parser を終了します。そのため通常の `_run()` / `_ops()` へ進まず、操作記録の読み込みは行いません。通常実行時の `_ops()` は `journal.load(profile, operation_id)` の返却値を出力しますが、これは help 表示の経路では呼ばれません（`strata_cli/cli.py:1391-1411,2217-2237`）。

## 適用条件と副作用

`strata ops result` までコマンド階層を指定してから使います。help 自体は操作記録を読まず、変更・削除しません。

CLI の `main()` は引数 parser を作る前に `private_files.adopt_user_defaults()` を呼びます。これは Windows で、昇格実行中にこのプロセスが今後作成するファイルの所有者・既定 ACL をユーザー向けに設定する処理です。非 Windows では何もしません。help 表示ではこの後続ファイル作成処理はありません（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-390`）。

## 出力とエラー

成功時は標準出力に help を出し、parser は終了コード `0` を指定します。CLI entry point は `main()` の戻り値を `SystemExit` に渡します（`strata_cli/cli.py:40-45`; `strata.py:39-43`）。help 以外の構文エラーは `argparse` の parser error 経路で usage とエラーを出し、終了します。通常処理で操作記録が見つからない場合などのエラーは `journal.load()` 側の処理ですが、help 表示ではその処理に入りません（`strata_cli/cli.py:2223-2231,1391-1411`; `strata_control/journal.py:185-198,247-251`）。

## 根拠

- parser / サブコマンドと引数定義: `strata_cli/cli.py:40-45,255-267`
- one-shot 共通 `--json` / `--quiet`: `strata_cli/cli.py:508-515`
- help が parse 時に終了し、通常 dispatch に至らない位置: `strata_cli/cli.py:2217-2237`
- 通常時の `ops result` 読み込み: `strata_cli/cli.py:1391-1411`; journal の読込・記録検証: `strata_control/journal.py:185-251`
- CLI entry point: `strata.py:39-43`
- 起動時の user defaults 処理: `strata_cli/cli.py:2217-2224`; 実装: `strata_control/private_files.py:349-390`
