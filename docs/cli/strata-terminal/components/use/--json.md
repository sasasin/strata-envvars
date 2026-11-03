# `strata components use --json`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 取らないフラグ。指定すると `--output json` と同じ出力モードになる |

## 役割

エンジン切り替えの結果を機械可読な JSON で出力するための共通 one-shot オプションです。`use` の対象や切り替え方法は変えません。

## 使い方

```sh
strata components use newest --json
```

`engine` 位置引数にはインストール済み engine の版番号、folder 名、または `newest` を指定します。選択方法の詳細は `strata_control/engine_library.py:198-211` にあります。

## 値と既定値

`--json` は値を取りません。既定の出力は `human` です。`strata_cli/cli.py:508-515` が `update_cmd.add_parsers()` から返された `use` parser に `--json` と `--quiet` を追加し、`--json` の指定を `strata_cli/cli.py:2249-2252` で `output="json"` に変換します。

`--output` は `strata_cli/update_cmd.py:47-57,84-87` により `human`（既定）、`json`、`jsonl` のいずれかを取ります。`--output json` は `--json` と同じ機械出力モードです。`--json --output jsonl` は one-shot コマンドでは拒否され、`strata_cli/cli.py:2249-2252` の分岐からエラーになります。`--output jsonl` 単独は受理され機械出力扱いになります。`use` の最終結果は JSON オブジェクトですが、`--wait` で実行中 engine の停止を待つ間は waiting event も JSONL で出力されます（結果: `strata_cli/update_cmd.py:358-400`; 待機 event: `strata_control/updater.py:311-322`）。

## 実行時の動作

`--json` が有効だと、`update_cmd.run()` は `output` が `json` または `jsonl` であることを機械出力モードとして扱います（`strata_cli/update_cmd.py:233-241`）。`strata components use` は `components_command` が `use` のとき `_engines_command()` に振り分けられ、成功時は `schema_version: 1`、`ok: true` と `use_engine()` の結果を含む JSON を標準出力に出します（`strata_cli/update_cmd.py:272-273,358-400`）。すでに選択中の engine なら `status: "already"`、切り替えた場合は `status: "switched"` などの結果を含みます。

このフラグは engine の選択、検証、切り替えそのものを変えません。対象の特定には位置引数と任意の `--family` が使われ、`--backend` と `--components-dir` は共有 Context の検出対象・保存先に影響します（parser: `strata_cli/update_cmd.py:47-58,84-87`; 実行: `strata_cli/update_cmd.py:244-255,378-384`）。切り替え時には、次回起動用の選択状態・履歴などが更新されます。最新の engine を選んだ場合は更新追従の pin を外し、それ以外は pin します。ダウンロードや削除はしません（`strata_control/engine_library.py:225-239,246-262`; `strata_control/updater.py:1303-1352`）。

`--quiet` を併用しても JSON 出力は抑制されません。`cli.main()` は `output` が `json` または `jsonl` の場合、quiet 用の標準出力捕捉を行わず実行します（`strata_cli/cli.py:2253-2265`）。

## 適用条件と副作用

`--json` はこの `use` one-shot parser で有効です。engine が実行中のモデルに使用されている場合、対話確認は行いません。`--wait` が指定されていなければ待機せず、実行中モデルがあるため切り替えなかった旨のエラー（終了コード 7）を返します。`--wait` を指定すると、停止までの待機を試みます（`strata_cli/update_cmd.py:403-418`; `strata_control/engine_library.py:225-239`）。

JSON モードであること以外に `--json` によるファイル・ネットワーク・プロセスへの副作用はありません。副作用は通常の engine 切り替え処理によるもので、選択状態や履歴の保存、engine が変わった場合の保存済み tuning preset の再確認マーク付けなどです（`strata_control/updater.py:1309-1352`）。

## 出力とエラー

通常の成功は標準出力に1行の JSON オブジェクト（`schema_version: 1`, `ok: true`）を出し、終了コード 0 です（`strata_cli/update_cmd.py:383-385`）。engine が未導入・指定が曖昧な場合は終了コード 2、実行中モデルで切り替えを拒否した場合は 7、engine 検証または切り替え適合確認で失敗した場合は 5 です（`strata_control/engine_library.py:198-210,216-221,228-236,246-260`; `strata_control/updater.py:1330-1336`）。`update_cmd.run()` は `UpdateError` を機械モードでは `schema_version`, `ok: false`, `error.code`, `error.message` を持つ JSON として標準出力へ出します（`strata_cli/update_cmd.py:237-242,307-311`）。

`--json --output jsonl` の組み合わせは、one-shot の `--json` と JSONL 出力が競合するため実行前にエラーになります（`strata_cli/cli.py:2249-2252`）。認識されない引数や不足している必須の `engine` は argparse の usage/error 経路となり終了コード 2 です（必須位置引数: `strata_cli/update_cmd.py:84-87`; 未認識引数: `strata_cli/cli.py:2240-2248`）。

## 根拠

- parser と共通 option の追加: `strata_cli/update_cmd.py:47-58,82-87`; `strata_cli/cli.py:139-140,508-515`
- `--json` から出力モードへの変換と JSONL 競合: `strata_cli/cli.py:2240-2253`
- `use` の dispatch、成功・失敗 JSON: `strata_cli/update_cmd.py:233-255,272-273,358-400`
- 対象 engine の選択規則と実行中モデル時の扱い: `strata_control/engine_library.py:198-239`
- Qwen / DeepSeek engine の検証と切り替え処理: `strata_control/engine_library.py:246-289`; `strata_control/updater.py:1303-1352`

この文書では同一 revision の Python ソースを確認しました。CLI の実行、build、GPU 実行、テストは行っていません。
