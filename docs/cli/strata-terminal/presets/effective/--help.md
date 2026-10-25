# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets effective` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`strata presets effective` の使い方と、その parser が受け付ける引数を表示します。`-h` は同じヘルプ表示を起動する短縮名です。トップレベルの `strata --help` や他のサブコマンドのヘルプとは対象 parser が異なります。

## 使い方

```sh
strata presets effective --help
strata presets effective -h
```

## 値と既定値

値を取りません。`strata_cli.tune_commands.add_presets` は `argparse` のサブパーサーに `effective` を登録し、`ArgumentParser` の既定のヘルプ追加を無効化せずに使っています。そのため Python 標準 `argparse` が `--help` と `-h` を用意します。`effective` は位置引数 `target` を必須とし、`--output` は `human`（既定）または `json` ですが、ヘルプ表示時には実行用の target を指定する必要はありません。

## 実行時の動作

トップレベルの `strata` parser の下に `presets`、さらに `effective` の parser が登録されています。`--help` または `-h` が見つかると、`argparse` がこのコマンド階層の usage と引数説明を表示して解析を終了するため、`presets_command` の実処理や設定読み込みには進みません。ヘルプ表示は対象設定の tuning を適用・保存する処理ではありません。

CLI の共通 entry point は parser 解析より先に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows でプロセスが後から作成するファイルの所有者・既定 ACL を現在のユーザー向けに設定しようとし、POSIX では何もしません。関数内で失敗した場合も例外を外へ出しません。したがって Windows では、ヘルプ表示でもこのプロセス設定が先に試行されます。

## 適用条件と副作用

このヘルプは `presets effective` parser に適用されます。表示中は tuning preset の検索や overlay は行われません。Windows での上記 token default の設定試行を除き、ヘルプ経路でファイル、ネットワーク、子プロセスを扱う処理は確認できません。

## 出力とエラー

標準 `argparse` のヘルプ action により、選択した `effective` parser のヘルプが標準出力へ表示され、成功終了します。必須の `target` を省略して `--help` も付けない場合や、認識されない引数を渡した場合は parser のエラー経路となり、usage とエラーを標準エラーへ表示して終了コード 2 になります。共通 entry point は `parse_known_args` 後に残った未知引数について `ap.error(...)` を呼びます。

## 根拠

- `strata_cli/cli.py:40-45` — `strata` の root `ArgumentParser` とサブコマンド parser の登録。
- `strata_cli/cli.py:487-489` — `presets` parser を root に登録。
- `strata_cli/tune_commands.py:49-55` — `presets` とその必須サブコマンド parser、および共通 `--output` の定義。
- `strata_cli/tune_commands.py:78-79` — `effective` parser と必須位置引数 `target` の定義。
- `strata_cli/cli.py:2217-2231` — parser 解析前の `adopt_user_defaults()`、解析、未知引数のエラー処理。
- `strata_control/private_files.py:349-389` — `adopt_user_defaults()` の Windows-only token default 設定と失敗時の戻り値。
- `strata_cli/tune_commands.py:361-378` — 通常実行時の effective overlay と出力。ヘルプ action は解析時に終了するためこの処理へ進まない。
- `docs/cli/README.md:898-903` — `strata presets effective` の索引上の階層と `--help` / `-h` の予定リンク。

調査時の Strata checkout は `main...origin/main` で変更なしでした。CLI の `--help` は実行せず、同一 revision の parser 定義と `argparse` の既定動作を照合しました。Windows 上の実行結果はこの環境では確認していません。
