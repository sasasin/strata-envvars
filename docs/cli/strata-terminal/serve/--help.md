# `--help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。`argparse` が parser ごとに自動登録する help action。 |

## 役割

`strata serve` の usage と、このコマンドで受け付けるオプションを表示する。トップレベルの `strata --help` とは対象 parser が異なり、`serve` の後に指定する。

## 使い方

```sh
python strata.py serve --help
# または
python strata.py serve -h
```

`--profile` / `--config` は通常の `serve` 実行では必須だが、help action が引数解析を終了するためヘルプ表示の呼び出しでは指定しなくてよい。

## 値と既定値

値は不要で、値の変換・範囲 validation はない。`strata_cli.cli.parser()` は `argparse.ArgumentParser` を既定設定で生成し、そのサブ parser として `serve` を追加している。`add_help=False` や独自 help action の指定はなく、Python `argparse` の既定により `-h` と `--help` が登録される（`strata_cli/cli.py:40-47`）。

## 実行時の動作

引数解析時に `serve` parser の説明と usage を標準出力へ表示し、status 0 で終了する。help action は解析を終了させるため、`main()` の後続 dispatch から `_serve()` へ進まず、profile の読み込み、launch plan 作成、server 起動は行わない（parser 作成: `strata_cli/cli.py:40-47`; dispatch: `strata_cli/cli.py:2119-2123`, `strata_cli/cli.py:2223-2231`）。出力形式は `serve` の `--output` や `--quiet` による実行時出力ではなく、`argparse` の help 出力である。

実際の entry point `strata.py` では CLI parser より先に `_preflight()` が実行される。引数中の最初の非オプション語が `serve` のとき、必要な server package を検査し、欠落があれば不足名を標準エラーへ表示して status 5 で終了する。この場合は `--help` を指定していても help は表示されない（`strata.py:14-27`, `strata.py:39-43`）。依存パッケージがそろえば CLI の引数解析に進む。

## 適用条件と副作用

`strata serve` の parser にだけ適用される。トップレベルや他のサブコマンドでの `--help` は、それぞれ別 parser のヘルプを表示する。オプション自体は profile や server を変更・起動しない。

ただし `strata.py` 経由では、Windows 上で parser 構築前に `private_files.adopt_user_defaults()` が呼ばれる。この関数は Windows のプロセストークンの既定 owner / DACL を調整し、他の OS では何もしない。したがって「help action が serve を起動しない」ことと、この entry point の前処理が一切ないことは別である（`strata_cli/cli.py:2217-2224`, `strata_control/private_files.py:349-358`, `strata_control/private_files.py:372-385`）。

ソース checkout では `strata.py` が checkout 内の CLI を使う。handover 実装は checkout 起動時に installed Control への引き渡しを行わない（`strata_cli/handover.py:27-29`, `strata_cli/handover.py:126-134`）。installed CLI の配布形態や Windows / POSIX の実機表示はこの調査では実行確認していない。

## 出力とエラー

- 通常の parser help は標準出力に usage / option list を表示して status 0 で終了する（Python `argparse` の既定 help action。Strata 側の help 固有出力処理はない）。
- entry point の依存 package preflight が失敗すると、不足 package と案内を標準エラーに出し status 5 で終了する（`strata.py:17-27`）。
- parser まで到達した通常の `strata serve` 解析で未知の引数があり、help action が先に終了していない場合は `argparse` の error 表示となる。Strata は `parse_known_args()` の余剰引数をここで `ap.error()` に渡す（`strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/cli.py:40-47` — 既定設定の top-level parser と `serve` subparser の生成。`serve` に `--profile` / `--config` が必須として宣言される。
- `strata_cli/cli.py:2119-2123`, `strata_cli/cli.py:2223-2231` — parser の引数解析とコマンド dispatch。
- `strata.py:14-27`, `strata.py:30-43` — handover 後、CLI parser より前に行う server package preflight とその status 5 経路。
- `strata_cli/cli.py:2217-2224`, `strata_control/private_files.py:349-358`, `strata_control/private_files.py:372-385` — CLI 初期化時の Windows user defaults 処理。
- `strata_cli/handover.py:27-29`, `strata_cli/handover.py:126-134` — source checkout 起動時の handover 条件。

本調査では既存 CLI の help 出力を実行せず、同一 revision の parser 定義と entry point を根拠にした。Python `argparse` による表示内容・標準出力・成功終了は Strata 独自処理ではなく、既定 action の仕様に基づく。
