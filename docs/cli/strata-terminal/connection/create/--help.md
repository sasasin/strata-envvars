# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection create` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。`argparse` の標準ヘルプ action。 |

## 役割

`strata connection create` の構文と、その parser に登録された引数・オプションを表示する。`create` は名前付きの monitor 接続先を保存するコマンドで、ヘルプでは位置引数 `name`、必須の `--url`、`--prefix`、`--credential-env`、出力関連オプションを確認できる。

## 使い方

```sh
strata connection create --help
strata connection create -h
```

ヘルプは `create` parser の引数定義から生成される。`--url` の値や `name` を指定する必要はない。これらは通常の create 実行時には必要だが、help action が parser を終了させるためである。

## 値と既定値

値は不要。`-h` は `--help` の短縮別名である。`create` parser には独自の help action の定義がなく、サブパーサー作成時に有効な `argparse` の標準 help が使われる。

## 実行時の動作

このオプションを付けると、`create` parser の usage と定義済み項目を標準出力に表示し、成功 status で終了する。parser の解析段階で終了するため、`monitor_commands.run()` や接続作成処理には進まず、接続情報の読込・保存も行わない。`--url` や `name` の通常実行向け必須条件も、ヘルプ表示を妨げない。

通常の `strata` エントリポイントは parser 構築・引数解析の前に handover 判定、preflight、Windows 向け既定 owner/DACL 処理を通る。preflight は `serve` / `bench` 以外では追加依存を検査せず続行し、checkout からの起動では handover も標準で無効になる。これらは `--help` 専用の処理ではなく、起動前処理である。テスト用 `STRATA_HANDOVER_IN_CHECKOUT` などで checkout handover が有効な場合は、handover 先が先にコマンドを処理し、現在のプロセスでは help を表示せずに終了することがある。

## 適用条件と副作用

`--help` 自体は接続先への通信や接続レコードの作成・変更を行わない。通常の CLI 起動前処理は別途実行される。`strata.py` では更新済み Control への handover 判定が parser より先にあるが、source checkout は標準では handover 対象外である。`strata_cli.cli.main()` では `adopt_user_defaults()` を parser より前に呼ぶ。後者は Windows 向けの処理で、`strata_control` がない薄型 bundle では import error を無視して続行する。

## 出力とエラー

標準 `argparse` の help action によりヘルプを標準出力へ出し、status 0 で終了する。通常の構文エラーは `argparse` の usage/error 経路（status 2）だが、`--help` の表示経路ではない。checkout handover が明示的に有効化された場合など、CLI 起動前の処理が引き継ぎ・終了する場合は、その処理側の結果が優先される。

## 調査範囲

この文書は指定 commit の parser・起動経路を調べた結果であり、同 revision の `--help` 実行出力は採取していない。表示項目と既定値は parser 定義から確認した。OS 別の Windows owner/DACL 処理の成否や、checkout handover を明示有効化した場合の引き継ぎ先実装は、このオプション固有の動作としては評価していない。

## 根拠

- `strata_cli/monitor_commands.py:75-94` — `connection create` parser の登録、`name` と必須 `--url`、`--prefix` / `--credential-env` の既定値、および共通 `--output` / `--json` / `--quiet`。
- `strata_cli/cli.py:40-45` — `argparse.ArgumentParser` による `strata` root parser と必須 command subparser の構築。
- `strata_cli/cli.py:488-493` — `add_connections()` を root parser に登録。
- `strata_cli/cli.py:2217-2224` — `main()` の起動前処理、parser 構築と `parse_known_args()`。
- `strata_cli/cli.py:2119-2165` — parse 後に通常処理を dispatch し、残りの monitor 系コマンドを `monitor_commands.run()` に渡す経路。
- `strata_cli/monitor_commands.py:140-164` — 通常の `create` action が呼び出す接続作成と成功出力。help action ではこの処理に到達しない。
- `strata.py:30-43` — CLI entrypoint の handover 判定と preflight が `strata_cli.cli.main()` より前に実行されること。
- `strata_cli/handover.py:27-29,132-133` — checkout 判定と、source checkout では通常 handover しない条件。
- `strata.py:14-27` — preflight は `serve` / `bench` に限って依存を検査すること。
- `strata_control/private_files.py:349-385` — Windows 向け既定 owner/DACL 設定の条件と処理。
- `docs/cli/README.md:1039-1049` — 索引における `strata connection create` のコマンド階層と `--help` リンク。
