# `strata code sessions --help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata code sessions` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。`argparse` が `sessions` parser に標準追加するヘルプ action。 |

## 役割

`strata code sessions` の usage と、このサブコマンド parser が受け付ける引数・オプションを表示して終了します。通常の `sessions` 実行で必須となる位置引数 `action` を省略していても、`--help` で parser の案内を確認できます。

## 使い方

```sh
strata code sessions --help
strata code sessions -h
```

ソース checkout から確認する場合の入口は `python strata.py code sessions --help` です。

## 値と既定値

値は不要です。`--help` と `-h` は同じ標準 help action です。トップレベル parser は通常の `argparse.ArgumentParser` で作られ、`sessions` も `add_parser()` で作られており、`add_help=False` の指定はありません。そのため `sessions` parser に標準の `-h` / `--help` が追加されます（`strata_cli/cli.py:40-45,505-507`）。

## 実行時の動作

help action は `sessions` parser のヘルプを表示して終了するため、`_run()` の `code` 分岐には進みません。表示対象は `sessions` parser 自身の位置引数 `action`（選択肢 `list`）、`--output`、および共通 one-shot オプションの `--json`、`--quiet` とヘルプ action です。`--output` の選択肢は `human` / `json`、既定値は `human` です（`strata_cli/cli.py:505-515`）。

親の `strata code` parser にある `--workspace`、`--resume`、`--quiet` は別スコープです。`strata code sessions --help` は `sessions` parser のヘルプを表示するため、親 parser のオプションはこのヘルプ一覧には含まれません（`strata_cli/cli.py:494-507`）。

## 適用条件と副作用

help 表示自体は通常のコーディングセッション処理を行いません。この revision の `_run()` は `command == "code"` を受けると共有 Desktop harness component が未導入として終了コード `5` を返しますが、`--help` は parser 内で終了するため、この実行時エラー経路には到達しません（`strata_cli/cli.py:2162-2164`）。

ただし `strata.py` の checkout entry point は `main()` を呼ぶ前に Control handover の確認を行います。また `main()` は引数解析前に `private_files.adopt_user_defaults()` を呼びます。この初期化は POSIX では何も変更せず、Windows では可能な場合にプロセス token の既定 owner と DACL を設定します（`strata.py:30-43`、`strata_cli/cli.py:2217-2224`、`strata_control/private_files.py:349-389`）。配布済み CLI の handover 先やその環境固有の挙動は、この parser 調査では確認していません。

## 出力とエラー

標準 `argparse` の help action は usage と `sessions` parser の説明・引数一覧を標準出力へ表示して終了します。`--help` を付けない通常の呼び出しでは `action` が必須で、受理される値は `list` です（`strata_cli/cli.py:505-507`）。未知の引数は `parse_known_args()` 後に `ap.error()` へ進み、usage とエラーを標準エラーに出して終了します（`strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベルの標準 `argparse` parser とサブコマンド登録。
- `strata_cli/cli.py:494-507` — `code` / `sessions` parser、親 parser の引数、`action` と `--output`。
- `strata_cli/cli.py:508-515` — one-shot parser への `--json` / `--quiet` 追加。
- `strata_cli/cli.py:2162-2164` — 通常実行時の共有 Desktop harness 未導入エラー。
- `strata_cli/cli.py:2217-2231` — `main()` の共通初期化、parser 作成、引数解析と未知引数の処理。
- `strata_control/private_files.py:349-389` — Windows の token 既定 owner / DACL 初期化と POSIX での無効化。
- `strata.py:30-43` — checkout entry point の handover 確認と CLI 起動。

索引には `strata-terminal` の `code/sessions` スコープの `--help`（alias: `-h`）として掲載されています（`docs/cli/README.md:1119-1126`）。この文書は指定 revision の parser と関連処理を根拠に記述しました。同 revision の実行バイナリによる help 表示、Release 配布物、配布環境での handover 挙動は確認していません。
