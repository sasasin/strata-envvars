# `--help`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし |

## 役割

`strata components remove` の usage と、このサブコマンドで受理される位置引数・オプションを表示して終了します。エンジンの削除処理は実行しません。

## 使い方

```sh
strata components remove --help
```

同じ help は `-h` でも表示できます。

## 値と既定値

値を取りません。`remove` parser は `components_sp.add_parser("remove", ...)` で登録され、独自の help action は定義していません。実行時 help 出力では `-h, --help` として表示されます。

## 実行時の動作

表示内容には `engine` 位置引数（version または folder name）、`--family {qwen,deepseek}`、共通オプション `--feed`、`--components-dir`、`--backend`、`--wait`、`--force`、`--model-config`、`--output {human,json,jsonl}`、および `--json`・`--quiet` が含まれます。共通オプション群は `update_cmd._common()` が追加し、`--json` と `--quiet` は `cli.parser()` が update parser 群へ追加します。

Help を解析すると argparse が usage/options を表示して終了するため、`update_cmd.run()` や `_engines_command()` には進みません。通常の `remove` 実行時は `_engines_command()` が engine library の `delete_engine()` を呼びますが、この help 表示では削除処理は呼び出されません。

## 出力とエラー

同一 checkout で確認した help は usage と引数説明を標準出力に表示し、終了コード 0 で終了しました。help 表示のためのネットワークアクセス、ファイル変更、engine 操作はありません。

## 根拠

- `strata_cli/cli.py:40-45` — root `ArgumentParser` の生成と `strata` CLI の構成。
- `strata_cli/update_cmd.py:88-95` — `remove` parser、位置引数 `engine`、`--family`、共通 parser オプションの登録。
- `strata_cli/update_cmd.py:47-56` — 共通オプションの定義。
- `strata_cli/cli.py:508-515` — update parser 群への `--json` と `--quiet` の追加。
- `strata_cli/cli.py:2233-2248` — parser による argv 解析。help で解析が終了した場合、dispatch へ進まない。
- `strata_cli/cli.py:2136-2138` — 通常実行時に `components remove` を `update_cmd.run()` へ dispatch。
- `strata_cli/update_cmd.py:272-273,358-360,395-400` — 通常の remove 経路と削除処理の呼び出し。
- 補助確認: 同一 revision の `python3 strata.py components remove --help` 実行出力。実行した help は parser の `-h, --help` 表示と上記オプション一覧を確認するために使い、実行時の削除挙動の根拠にはしていません。
