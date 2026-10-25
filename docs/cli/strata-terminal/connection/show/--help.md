# `strata connection show --help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection show` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプ action を実行する |

## 役割

`strata connection show` の使い方を表示する。`argparse` の `ArgumentParser` とサブコマンド parser は既定でヘルプを有効にしており、この parser で `--help` と `-h` が使える。索引上、このヘルプは `strata connection show` のスコープに属する（トップレベルや `strata connection` のヘルプとは別）。

## 使い方

```sh
strata connection show --help
strata connection show -h
```

ヘルプ表示には接続名を付けなくてよい。通常の `show` 実行では `name` 位置引数が必要だが、ヘルプ action が引数解析中に終了するため、接続の読み込みには進まない。

## 値と既定値

値を取りません。parser に明示的な `--help` 定義や既定値の上書きはなく、`argparse` 標準のヘルプ action が適用される。`show` parser の通常引数は `name` で、共通の出力 option は `--output {human,json}`（既定値 `human`）、`--json`、`--quiet` だが、ヘルプ表示時にはこれらの実行時処理は行われない。

## 実行時の動作

ヘルプにはコマンドの usage、説明（保存済み接続を credential なしで表示するコマンドであること）、`name` 引数、利用可能な option が表示される。表示後は成功終了し、保存済み接続を検索・表示する通常処理へ進まない。通常処理での接続読み込みは `monitor_commands._local_command` の `show` 分岐にあり、`connections.load(a.name)` を呼ぶ。

## 適用条件と副作用

この option 自体は接続ファイルの読み書き、ネットワーク接続、接続先への認証を行わない。通常の `strata.py` 起動では、parser 構築前に更新済み Control への hand-over 判定が行われる。ソース checkout からの起動では hand-over を行わない。さらに `main` は引数解析前に `adopt_user_defaults()` を呼ぶが、この処理は Windows 以外では何もせず、Windows ではプロセスの既定 owner/DACL を設定しようとし、失敗しても CLI を止めない。この前処理は `--help` action 自体の効果ではない。

## 出力とエラー

`argparse` が標準出力へヘルプを表示し、終了コード `0` で終了する。ヘルプ表示のために必須の `name` 引数は検証されない。未知 option などで通常の引数解析に失敗した場合は `ap.error(...)` 経路で usage とエラーが標準エラーへ出て、終了コード `2` となる。

## 根拠

- `strata_cli/monitor_commands.py:75-94` — `connection show` parser と `name`、共通出力 option の登録。明示的な `add_help=False` はなく、`actions.add_parser("show", ...)` で標準 parser を作成する。
- `strata_cli/monitor_commands.py:140-146` — 通常実行時の `show` 分岐と `connections.load` 呼び出し。
- `strata_cli/monitor_commands.py:247-248` — parser の引数解析後に処理を実行する構造。
- `strata_cli/cli.py:490-493` — 同じ connection parser を Terminal CLI のトップレベルへ登録。
- `strata_cli/cli.py:2217-2231` — `main` の起動前処理、`parse_known_args`、未知引数エラー処理。
- `strata.py:30-43` — ソース checkout の CLI entry point、hand-over 判定とトップレベル `main` 呼び出し。
- `strata_cli/handover.py:126-134` — checkout からの実行では hand-over を省く条件。
- `strata_control/private_files.py:349-389` — Windows 限定の既定 owner/DACL 設定と失敗時の扱い。
