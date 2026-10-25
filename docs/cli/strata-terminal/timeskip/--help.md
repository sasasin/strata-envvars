# `strata timeskip --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

`timeskip` のサブコマンド一覧と説明を表示して終了します。ヘルプは `argparse.ArgumentParser` が標準で追加するもので、`timeskip` 用の独自 `--help` action はありません。`timeskip` parser はトップレベル parser の `add_subparsers` で登録され、その下に `run`、`status`、`list`、`apply` が登録されています（`strata_cli/cli.py:40-45,348-393`）。

## 使い方

```sh
strata timeskip --help
```

ソース checkout から起動する場合は `python strata.py timeskip --help` でも同じ CLI grammar を通ります（`strata.py:1-4,30-43`）。

## 値と既定値

値は不要です。`-h` は `--help` の短縮別名です。`timeskip` parser は `add_parser("timeskip", ...)` で作られ、通常の `argparse` parser と同じく標準ヘルプを有効にしています（`strata_cli/cli.py:40-45,348-350`）。help action は解析を終了させるため、`timeskip` サブコマンドの必須指定があっても `--help` だけで表示できます。

## 実行時の動作

標準ヘルプには `run`（チェックポイント作成・改訂・検査・判定）、`status`（run の状態と証拠の表示）、`list`（記録済み run の一覧）、`apply`（保持した結果の適用）の各サブコマンドが掲載されます（`strata_cli/cli.py:352,371,376,380-381`）。各サブコマンド固有の引数はそれぞれの parser に属し、この `timeskip` 階層のヘルプオプションとは別スコープです（`strata_cli/cli.py:350-393`）。

解析で help action が終了するため、`main` の後段にある `timeskip` 分岐から `_timeskip` の run/status/list/apply 処理へは進みません（`strata_cli/cli.py:2223-2231,2147-2150`）。CLI entry point は parse 前に handover 判定を行いますが、checkout からの実行では installed Control への handover を行わず、`timeskip` は entry point の依存パッケージ preflight の対象外です（`strata_cli/handover.py:27-29,126-145`; `strata.py:14-27,30-43`）。

## 適用条件と副作用

ヘルプ表示はサブコマンドの処理や run データの読み書きを行いません。ただし `main` は parser 作成前に `private_files.adopt_user_defaults()` を呼びます。この関数は Windows ではプロセスの既定 owner/DACL を設定し、Windows 以外では何もせず `False` を返します（`strata_cli/cli.py:2217-2224`; `strata_control/private_files.py:349-389`）。

インストール済み entry point では `strata.py` が handover/refusal 判定を先に実行するため、更新状態などに応じて別 Control が同じ引数を処理する場合があります。source checkout では `running_from_checkout()` により handover を抑止します（`strata.py:30-38`; `strata_cli/handover.py:27-29,126-145,174-185`）。

## 出力とエラー

有効な呼び出しでは `argparse` の usage、説明、サブコマンド一覧を標準出力に表示し、終了コード `0` で parser を終了します。`--help` に値を付けた場合や未知の引数を渡した場合は通常の引数エラーとなり、usage とエラーを標準エラーへ出して終了コード `2` になります。Strata 側は `parse_known_args` 後に未認識引数を `ap.error(...)` へ渡します（`strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル `ArgumentParser` とサブコマンド parser の生成。
- `strata_cli/cli.py:348-393` — `timeskip` parser、必須サブコマンド群、および各サブコマンドの parser 定義。
- `strata_cli/cli.py:2147-2150,2217-2231` — 通常のコマンド dispatch と parse 前後の処理。
- `strata.py:14-43`、`strata_cli/handover.py:27-29,126-145,174-185` — entry point の preflight と handover 条件。
- `strata_control/private_files.py:349-389` — parse 前に呼ばれる既定 owner/DACL 設定の条件と効果。
- 作成先リポジトリの索引 `strata-envvars/docs/cli/README.md:674-686` — `timeskip` とその `run`、`status`、`list`、`apply` 各階層の option scope。索引では本書の配置が予定リンクとして示されています。
