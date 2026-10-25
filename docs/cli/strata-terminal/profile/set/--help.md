# `strata profile set --help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile set` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし |

## 役割

`strata profile set` の使い方と、このサブコマンドで受け付ける引数・オプションを表示します。`profile set` の parser は `argparse` の `add_parser` で作られ、`add_help` を無効にしていないため、標準の `-h`／`--help` が利用できます。

## 使い方

```sh
strata profile set --help
strata profile set -h
```

## 値と既定値

値を取りません。引数を省略したときの既定値はありません。表示される usage は、位置引数 `name` と1個以上の `assignments`、および `--plan`、`--output {human,json}`、共通オプションの `--json` と `--quiet` を示します。

## 実行時の動作

ヘルプを標準出力に表示して終了コード 0 で終了します。help action が parser の引数解析中に終了するため、profile の読み込み、変更案の作成、保存は実行されません。`--json` や `--quiet` を併記しても help 表示を JSON 化したり抑制したりはしません。

## 適用条件と副作用

Terminal CLI の `profile set` サブコマンドに適用されます。help action 自体は profile を読み書きしません。CLI の `main()` は parser 構築前に `private_files.adopt_user_defaults()` を呼び、Windows では後続のファイル作成に使うプロセス token の owner と default DACL の設定を試みます。これは `--help` 固有の処理ではありません。ソース checkout で parser を直接呼び出して確認した help 表示は、この commit の parser と一致しました。Release 配布物は別途確認していません。

## 出力とエラー

確認したソース checkout では、usage とオプション説明を標準出力に表示し、終了コード 0 で終了しました。`-h` と `--help` は同じ help action です。

## 根拠

- `strata_cli/cli.py:40-45` — `argparse.ArgumentParser` と最上位 parser の構築。
- `strata_cli/cli.py:69-88` — `profile set` parser、位置引数、`--plan`、`--output` の定義。`add_help=False` の指定はなく、標準の `-h`／`--help` が有効。
- `strata_cli/cli.py:508-515` — `profile set` を含む one-shot parser 群へ `--json` と `--quiet` を追加。
- `strata_cli/cli.py:2217-2237` — parser での引数解析後に通常の `_run` へ進む CLI 経路。help action は解析中に終了するため、この経路の dispatch より前に完了する。
- `strata_control/private_files.py:349-389` — CLI 起動時に呼ばれるユーザー既定値の設定。Windows では process token を調整し、他 OS では何もしない。
- `strata.py:30-43` — `strata` スクリプト入口。handover 判定と preflight の後に CLI `main()` を呼び出す。
- `strata_cli/cli.py:986-997` — 通常の `profile set` 実行時は変更案を作り、`--plan` がなければ保存する分岐。help 表示ではこの分岐に到達しない。
- 同一 checkout の parser に `profile set --help` を渡した補助確認 — 表示内容に `-h, --help`、`--plan`、`--output`、`--json`、`--quiet` と位置引数が含まれ、終了コード 0。
