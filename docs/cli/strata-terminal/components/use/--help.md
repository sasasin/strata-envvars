# `strata components use --help`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。`use` の説明と引数・オプションの usage を表示する。 |

## 役割

`strata components use` の利用方法を表示して終了します。トップレベル parser が標準の `argparse.ArgumentParser` で作られ、`use` も `components` の subparser として標準設定で登録されます。`add_help=False` は指定されていないため、Python `argparse` の標準 help action（`-h` / `--help`）が有効です（`strata_cli/cli.py:40-45,114-116`、`strata_cli/update_cmd.py:84-87`）。

## 使い方

```sh
strata components use --help
```

`strata components --help` とは別の parser scope です。このコマンドの説明に加え、位置引数 `engine` と `--family`、共通オプションを表示します。索引では `components/use` に配置されています（[CLI 索引](../../../README.md)）。

## 値と既定値

値は不要です。`--help` と `-h` は同じ標準 action の別名です。表示対象の parser には、位置引数 `engine`（必須）、`--family`（選択肢 `qwen` / `deepseek`、既定値なし）、共通オプション `--feed`、`--components-dir`、`--backend`、`--wait`、`--force`、`--model-config`、`--output`、および one-shot 用の `--json` と `--quiet` が登録されています（`strata_cli/update_cmd.py:47-56,84-87`、`strata_cli/cli.py:508-515`）。

`--help` 自体に値・既定値・複数回指定時の独自処理はありません。標準 help action が parser の説明と登録済み引数の表示を行います。

## 実行時の動作

`strata.py` から呼ばれる `main()` は parser を構築し、`parse_known_args()` で引数を解析します。help action が処理されると `argparse` が表示後に終了するため、その後の余分な引数処理、出力形式の調整、`_run()` への dispatch は実行されません（`strata_cli/cli.py:2233-2254`）。従って `strata components use` の通常処理、engine 一覧の読取り・選択、engine の切替、server 待機、engine package の検証は help 表示からは呼び出されません（通常処理への dispatch は `strata_cli/cli.py:2136-2138`、engine 選択と切替は `strata_cli/update_cmd.py:358-394`）。

CLI entry point は parser 構築より前に `private_files.adopt_user_defaults()` を呼びます。これは Windows ではプロセストークンの既定 owner と DACL の設定を試み、成功可否を返し、`OSError` では `False` を返します。Windows 以外では何もしません。この初期化は help の副作用とは別に、引数解析前に起きます（`strata_cli/cli.py:2233-2239`、`strata_control/private_files.py:349-392`）。

ソース checkout から `strata.py` を起動する場合、通常は新しい Control への handover を行いません。handover 実装が checkout を検出して戻る条件を持ち、`strata.py` はそれを `main()` より前に呼びます（`strata.py:30-43`、`strata_cli/handover.py:27-29,126-134`）。インストール済み Terminal での handover は、より新しい Control が導入されている場合など条件により実行され得ます（`strata_cli/handover.py:1-10,137-160`）。したがって、別 Control に handover した環境で表示される help 内容は、その実行先 revision の parser に依存します。

## 出力とエラー

標準 `argparse` の help action は usage と parser の説明を標準出力へ表示し、終了コード `0` で終了します。Strata 独自の `--help` 出力処理やエラー変換はありません（parser の生成と引数解析: `strata_cli/cli.py:40-45,2239-2248`、`use` parser の説明・登録: `strata_cli/update_cmd.py:84-87`）。

この調査では同一 revision の CLI を実行していません。表示文の実出力と配布バイナリは照合していません。上記の出力先と終了動作は標準 `argparse` action に基づきます。

## 根拠

- `strata_cli/cli.py:40-45,114-116` — 標準 `ArgumentParser` と `components` subparser の生成。
- `strata_cli/update_cmd.py:84-87` — `use` parser、説明、必須位置引数、`--family`、共通 option 登録。
- `strata_cli/update_cmd.py:47-56` — `use` に共通登録される option。
- `strata_cli/cli.py:508-515` — one-shot parser への `--json` / `--quiet` 追加。
- `strata_cli/cli.py:2136-2138,2233-2254` — 通常の `use` dispatch と、dispatch 前に help が終了する引数解析経路。
- `strata_control/private_files.py:349-392` — help 解析前に呼ばれる Windows 向け owner/DACL 初期化。
- `strata.py:30-43`、`strata_cli/handover.py:27-29,126-160` — entry point と Control handover 条件。
