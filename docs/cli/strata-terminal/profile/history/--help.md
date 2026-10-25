# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile history` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`strata profile history` の使い方と、このサブコマンドで受け付ける引数・オプションを表示します。履歴データの読み出しは行いません。

## 使い方

```sh
python strata.py profile history --help
```

インストール済み CLI では同じ位置で `strata profile history --help` を実行します。`-h` も同じ表示を行います。

## 値と既定値

値は不要です。Python `argparse` の標準ヘルプアクションとして各 parser に `-h` と `--help` が作られます。履歴 parser 自体ではこの動作を上書きしていません。

同じ parser に必須位置引数 `name` と `--output {human,json}`（既定値 `human`）が定義されています。また共通の one-shot オプションとして `--json` と `--quiet` も追加されます。help 表示時はこれらも一覧に載りますが、ヘルプアクションが parser を終了させるため、その値による履歴出力には進みません。

## 実行時の動作

この option は `history` サブコマンド parser のヘルプを標準出力に表示し、終了コード 0 で終了します。調査時の同一 revision での表示は次のとおりでした。

```text
usage: strata profile history [-h] [--output {human,json}] [--json] [--quiet]
                              name

positional arguments:
  name

options:
  -h, --help            show this help message and exit
  --output {human,json}
  --json                alias for --output json
  --quiet               suppress human informational output
```

ヘルプアクションは引数解析中に終了するため、通常の dispatch と `profiles.history(name)` は呼び出されません。したがって profile の履歴ファイルを読みません。なお CLI の `main` は parser 構築・引数解析より先に `private_files.adopt_user_defaults()` を呼びます。この処理は Windows でプロセスの既定 owner/DACL を設定し、他 OS では何もしない実装です。

## 適用条件と副作用

`--help` は `strata profile history` に対するものです。`strata profile --help` は親 `profile` parser のヘルプを表示します。履歴の表示形式を切り替える `--output` などとは異なり、ヘルプ表示の後に履歴処理は続きません。

履歴データの読み出しや書き込み、ネットワーク・子プロセス起動は、この help 経路では確認されません。前述のとおり Windows では parser に入る前にプロセスの既定 owner/DACL 設定が試みられますが、ユーザーデータの変更とは別の処理です。

## 出力とエラー

ヘルプ本文は標準出力へ出力されます。`--help` を指定した実行は成功終了します。ソースの parser は `name` を必須としているため、`--help` を付けず `history` を実行して `name` を省略すると argparse の引数エラーになります（通常の parser エラー終了）。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル `ArgumentParser` とサブコマンド parser の構成。
- `strata_cli/cli.py:69-70,99-101` — `profile history` parser、`name`、`--output` の定義。`add_help=False` や独自 help action の指定はありません。
- `strata_cli/cli.py:508-515` — one-shot parser 群への `--json` と `--quiet` の追加。`profile_history` が対象に含まれます。
- `strata_cli/cli.py:1006-1010` — 通常実行時に限り `profiles.history(a.name)` を呼び、履歴を整形する handler。
- `strata_cli/cli.py:2217-2237` — `main` の事前処理、`parse_known_args`、解析後の dispatch。
- `strata_control/private_files.py:349-385` — `adopt_user_defaults()` の説明と Windows token owner/DACL 設定。
- `strata.py:30-43` — CLI 起動時の handover/preflight と `main` 呼び出し。checkout では自身のソースを実行する handover 規則は `strata_cli/handover.py:126-134`。
- 補助確認: 同一 checkout の `python strata.py profile history --help` の実行結果。parser 定義と表示項目が一致することを確認しました。
