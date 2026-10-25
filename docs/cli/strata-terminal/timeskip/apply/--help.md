# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（`2026-10-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip apply` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`timeskip apply` の使い方と、その parser に登録された位置引数・オプションを標準出力に表示して終了する。トップレベルや別コマンドの `--help` とは対象範囲が異なる。

## 使い方

```sh
python strata.py timeskip apply --help
```

ソース checkout のルートで実行する例。インストール済み CLI では `strata timeskip apply --help` とする。

## 値と既定値

値を取りません。`argparse.ArgumentParser` の既定の help action が `-h` と `--help` を登録するため、`timeskip apply` 専用 parser でも両方を受理する。独自の既定値や値検証はない（`strata_cli/cli.py:40-41,380-393`）。

## 実行時の動作

`timeskip apply` の parser が持つ `run_id`、`--workspace`、`--attempt`、`--dry-run`、`--restore`、`--state-dir`、`--output` を表示する。`run_id` は通常の apply 呼び出しでは必要だが、help action が parser を終了させるため、ヘルプ表示だけなら指定しなくてよい。確認した同一 checkout の出力では、usage は `strata timeskip apply [-h] [--workspace WORKSPACE] [--attempt ATTEMPT] [--dry-run] [--restore] [--state-dir STATE_DIR] [--output {human,json}] run_id` となる。

help action は通常の引数処理を終了する。そのため `_timeskip()` の apply 分岐には進まず、run の読み込み、workspace の照合、結果の適用・復元は行わない（`strata_cli/cli.py:1524-1555,2217-2237`）。

## 適用条件と副作用

`--help` は `timeskip apply` parser に対して有効。値を取らず、他の `apply` オプションとの相互作用によって apply 処理へ進むことはない。

Strata の CLI 入口では parser を作る前に `private_files.adopt_user_defaults()` を呼ぶ。この関数は Windows でプロセスの既定 owner/DACL を調整し、Windows 以外では何もしない。help 自体は run データや workspace を変更しない（`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-389`）。また、インストール環境で更新済み Control がある場合は parser に入る前に引き継ぎが起き得る。ソース checkout からの起動はこの handover 対象外（`strata.py:30-43`、`strata_cli/handover.py:27-29,126-134`）。

## 出力とエラー

ヘルプ本文は標準出力に表示され、正常終了する。確認した checkout での出力は上記の引数一覧と各 help 文で、終了コードは `argparse` の既定 help action が `parser.exit()` するため `0`。`--help` 自体の値エラーはない。CLI の入口処理やインストール済み Control への handover が失敗した場合は help parser に到達しない可能性があるが、その環境別の実行結果は確認していない。

## 根拠

- `strata_cli/cli.py:40-45` — `argparse.ArgumentParser` とトップレベル parser の定義。
- `strata_cli/cli.py:348-393` — `timeskip` / `apply` の階層と `apply` parser の引数。
- `strata_cli/cli.py:1524-1555` — 通常実行時の apply / restore 処理と表示・エラー経路。
- `strata_cli/cli.py:2217-2237` — parser 作成、`parse_known_args()`、通常コマンド処理への分岐。
- `strata_control/private_files.py:349-389` — 起動時の既定 owner/DACL 調整。
- `strata.py:14-43`、`strata_cli/handover.py:27-29,126-134` — preflight と checkout 時の handover 条件。
- 補助確認: 同一 checkout で `PYTHONDONTWRITEBYTECODE=1 python strata.py timeskip apply --help` を実行し、出力形式と掲載オプションを parser 定義と照合した。Release 配布物や Windows 実機での出力は調査していない。
