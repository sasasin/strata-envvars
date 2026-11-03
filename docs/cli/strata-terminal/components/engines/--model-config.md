# `--model-config`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engines` |
| オプション | `--model-config RUN_CONFIG.json` |
| 別名 | なし |
| 値 | run config のパスとして説明される文字列。parser では `str` のまま受け取る |

## 役割

`--model-config` は共通 option parser によってこのコマンドでも受理されます。parser の共通 help は「test start に使うモデルの run config」と説明しますが、`strata components engines` は導入済み engine の一覧経路に分岐し、一覧処理はこの値を使いません。そのため、このコマンドでは指定しても一覧内容や処理に影響しません。

## 使い方

```sh
strata components engines --model-config /path/to/run-config.json
```

この例のパスは parser に文字列として渡されます。engine 一覧の取得では開かれません。

## 値と既定値

- 省略時の値は `None` です。指定値は型変換や選択肢制限のない文字列です（`strata_cli/update_cmd.py:47-56`）。
- parser に値の形式やファイル存在を検証する処理はありません。値が空文字列または存在しないパスでも、この一覧経路では run config として読まれません。
- 値を付けずに `--model-config` だけを指定した場合は parser の引数不足になります。

## 実行時の動作

`strata components engines` の parser は `_common()` を呼び出して `--model-config` を登録します（`strata_cli/update_cmd.py:82-83`）。`run()` は全コマンド共通の `updater.Context` を構築するとき `a.model_config` を `ctx.run_config` に渡しますが、`engines` はその直後に `_engines_command()` へ分岐します（`strata_cli/update_cmd.py:254-255,272-273`）。

一覧分岐は `lib.list_engines(ctx)` の結果を表示します（`strata_cli/update_cmd.py:358-377`）。`list_engines()` は導入済み Qwen/DeepSeek engine を調べて一覧を返し、処理の説明も「ファイルを読むだけで、変更・ダウンロードはしない」としています（`strata_control/engine_library.py:180-195`）。その実装と一覧を作る `_qwen_entries()` / `_ds_entries()` は `ctx.run_config` を参照しません（`strata_control/engine_library.py:91-123,128-162`）。したがってこのスコープでは run config の自動選択、JSON 読込、test-start は発生しません。

この option の共通 help が説明する用途は、update/install の test-start 経路にあります。`Context.run_config` は test-start 用と定義され（`strata_control/updater.py:336-355`）、実際に `default_test_start()` が指定値または自動発見した設定を読む処理を持ちます（`strata_control/updater.py:988-1001`）。ただし `components engines` はその install 経路へ進みません。

## 適用条件と副作用

`--model-config` 自体によるファイル読込、書込、ネットワークアクセス、engine の変更はありません。一覧コマンド本来の処理ではローカルの engine package と状態を読み、稼働状況も取得して表示します（`strata_control/engine_library.py:91-111,128-161,180-195`）。

`--output human|json|jsonl` または後付けの `--json` によって表示形式は変わりますが、`--model-config` は一覧の選別条件ではありません（`strata_cli/update_cmd.py:56,235,363-377`、`strata_cli/cli.py:508-515`）。

## 出力とエラー

通常は engine 一覧を標準出力に表示します。機械可読出力では JSON の一覧を標準出力に出し、正常終了は `0` です（`strata_cli/update_cmd.py:363-377`）。`--model-config` のパスに関するエラー経路は一覧分岐にはありません。値不足による parser error は別で、run config の内容不正やファイル不在を理由とする失敗はこのコマンドでは起きません。

## 根拠

- 索引上の command scope と予定リンク: `docs/cli/README.md:274-289`
- 共通 option 宣言、`components engines` への登録: `strata_cli/update_cmd.py:47-56,82-83`
- option 値を Context に渡した後の一覧分岐: `strata_cli/update_cmd.py:233-256,272-273`
- 人向け / JSON 出力: `strata_cli/update_cmd.py:358-377`
- 一覧処理とその read-only 性、run config を使わない engine 列挙: `strata_control/engine_library.py:91-123,128-162,180-195`
- `run_config` の test-start 用途と設定ファイル読込（対照）: `strata_control/updater.py:336-355,988-1001,1147-1158`
