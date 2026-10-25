# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models move` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らないフラグ |

## 役割

`strata models move` が受け付ける引数とオプションの使い方を表示します。これは `models move` の parser に対するヘルプで、トップレベルの `strata --help` や `strata models --help` とは対象範囲が異なります。コマンド固有の `--help` は明示的には追加されていませんが、トップレベル parser が通常の `argparse.ArgumentParser` として作られ、`models move` もそのサブ parser として作られるため、標準の `-h` / `--help` が使えます（`strata_cli/cli.py:40-45`, `strata_cli/cli.py:141-143`, `strata_cli/cli.py:162-171`）。

## 使い方

```sh
python strata.py models move --help
```

配布済み Terminal CLI では同じコマンド階層で `strata models move --help` とします。表示例では `NEW_FOLDER` は任意引数であり、`--resume`・`--leave`・`--status` と各オプションが列挙されます。`--json` と `--quiet` も one-shot parser 群へ共通追加されるため、このコマンドのヘルプに表示されます（`strata_cli/cli.py:163-171`, `strata_cli/cli.py:508-515`）。

## 値と既定値

値は不要です。`-h` と `--help` は同じ標準ヘルプ action の別名であり、既定の parser 設定によって提供されます。Strata 独自の値検証や既定値はありません（`strata_cli/cli.py:40-45`, `strata_cli/cli.py:162-171`）。

## 実行時の動作

parser がヘルプを表示して終了するため、引数の `parse_known_args` 後に行われる余分な引数の処理、`--json` の出力モード変換、および `_run()` のコマンド dispatch には進みません（`strata_cli/cli.py:2217-2237`）。したがって、`models move` が行う移動計画・ファイル移動・中断操作も実行されません。通常実行時は `models move` から `_models_move()` に dispatch されます（`strata_cli/cli.py:617-624`, `strata_cli/cli.py:2140-2142`）。

## 適用条件と副作用

`strata models move` の parser に到達してヘルプ action が処理される場合に適用されます。ヘルプ表示そのものはモデルファイルを移動・削除せず、移動状態も変更しません。

ただし `strata.py` の起動経路では、引数解析より先に旧 updater の拒否確認と、必要に応じた新しい Control への handover 判定が実行されます（`strata.py:30-43`）。さらに Control が利用可能な場合、`main()` は parser を作る前に `private_files.adopt_user_defaults()` を呼びます。この関数の説明では Windows でプロセスの既定所有者・アクセス規則を設定し、他 OS では効果がないとされています（`strata_cli/cli.py:2217-2224`, `strata_control/private_files.py:349-354`）。そのため、ヘルプ表示経路の全副作用が常にゼロとは限りません。

## 出力とエラー

調査対象 revision で `python strata.py models move --help` を実行すると、使用法と位置引数・オプションの説明が標準出力に表示されました。ヘルプ表示後は成功終了します（標準 `argparse` の help action）。これはソース parser と同じ checkout の CLI による補助確認です。

通常の parser エラー（未知の引数など）は `argparse` の usage/error 経路になります。`NEW_FOLDER` 自体は parser 上は任意ですが、`--resume`・`--leave`・`--status` のいずれでもなく、移動先もない通常実行は、別途 `strata:` エラーを標準エラーへ出して終了コード 2 を返します（`strata_cli/cli.py:163`, `strata_cli/cli.py:623-625`）。この通常実行の失敗経路は `--help` の表示とは別です。

## 根拠

- `strata_cli/cli.py:40-45`, `strata_cli/cli.py:141-143`, `strata_cli/cli.py:162-171` — 標準 parser と `models move` の位置引数・オプション定義。
- `strata_cli/cli.py:508-515` — `models_move` を含む one-shot parser 群への `--json`・`--quiet` 追加。
- `strata_cli/cli.py:617-660`, `strata_cli/cli.py:2217-2237` — 通常の move 実行経路と parse 後の dispatch 順序。
- `strata.py:30-43`, `strata_cli/cli.py:2217-2224`, `strata_control/private_files.py:349-354` — 起動時 handover 判定および parser より前の Windows 向け設定処理。
- 同一 revision の `python strata.py models move --help` — 表示内容の補助確認。parser 実装の根拠は上記ソース。

調査範囲は指定 checkout の Terminal CLI ソースと、その checkout からの安全な help 表示です。別環境の配布版での表示や handover 先 Control の挙動は確認していません。
