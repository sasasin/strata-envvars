# `strata components rollback --backend`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components rollback` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | エンジンの backend 名。parser では文字列をそのまま受け取り、選択肢を限定しません。 |

## 役割

PC の GPU backend 自動検出を上書きし、その backend を対象に「直近の切替または更新で保持された前の engine」へ戻せるか確認します。rollback 対象の engine は保存状態の `previous` から決まり、`--backend` で任意の engine package を指定するわけではありません。

## 使い方

```sh
strata components rollback --backend hip
```

指定を省略する場合:

```sh
strata components rollback
```

## 値と既定値

- 値は必須の文字列です。`argparse` の `type`、`choices`、独自の CLI validation は設定されていません。既定値は `None` です（`strata_cli/update_cmd.py:47-56,80-82`）。
- 実行時には前後の空白を除き小文字化します。`hip-<variant>` 形式は `hip` backend と variant に分解されます。それ以外は backend 名としてそのまま渡されます（`strata_control/engine_component.py:465-471`）。
- 空白だけの値は parser では受理されますが、分解後の backend は空文字列になります。rollback resolver では `None` の場合だけ自動検出へ進むため、この値は自動検出に戻らず engine 選択に失敗します（`strata_cli/update_cmd.py:247-252`、`strata_control/engine_component.py:1012-1027,1043-1045`）。
- `nvidia` / `amd` / `intel` などの別名変換はこの経路では行われません。`clean_backend_name()` は launch 用の別処理であり、rollback の `run()` からは呼ばれません（`strata_control/engine_component.py:474-482`、`strata_cli/update_cmd.py:244-252`）。
- 未指定なら `updater.detect_hardware()` が検出した値を使います。同関数は `STRATA_ENGINE_BACKEND` も検出入力として扱います（`strata_control/updater.py:261-281`）。

## 実行時の動作

`run()` はまず自動検出した hardware 情報を作り、`--backend` が空文字列でなければその値で `hardware["backend"]` を上書きします。`hip-<variant>` の場合は分解結果を `variant_wanted` にも記録します（`strata_cli/update_cmd.py:233-255`）。

rollback は `updater.rollback_engine()` に進み、状態ファイルの `engine.previous` が指す folder の manifest と署名・全ファイルを検証します。続いて、現在選択される engine と rollback 先を切り替える際に `hardware["backend"]` を `engine_component.resolve()` に渡して、指定 backend で使用可能かを確認します（`strata_control/updater.py:1355-1377,1303-1329`、`strata_control/engine_component.py:1012-1045,1064-1097`）。したがって指定 backend に対応する保持済み engine がない場合や、platform・runtime・GPU architecture・driver 条件を満たさない場合は切替できません。実機の platform や GPU architecture 情報は backend 上書きだけでは置き換わりません（`strata_control/updater.py:261-281`）。

この rollback 経路では分解した `variant_wanted` は参照されず、resolver に渡るのは backend family です。したがって `--backend hip-rdna2` は `hip` family として適合性を確認し、`rdna2` variant の package を明示選択する指定にはなりません（`strata_cli/update_cmd.py:247-260`、`strata_control/updater.py:1355-1377`）。

## 適用条件と副作用

- rollback は feed からのダウンロードを行いません。成功すると engine の `pinned`、`previous`、`active` 等の状態を更新し、成功履歴を保存します。engine package 自体を削除しません（`strata_control/updater.py:1303-1352,1355-1377`）。
- backend 指定文字列自体を設定ファイルに保存する処理はありません。ただし成功した切替では対象 package の pin が状態に保存されます。backend 指定が検証にだけ使われる一時値でも、結果としての engine pin は後続の起動に影響します（`strata_control/updater.py:1313-1328,1345-1350`）。
- 切替前に稼働中 engine があれば、`--wait` が指定されている場合は停止まで待機し、指定がなく対話端末なら待機確認を行います。非対話または machine output の場合は確認せず、稼働状態なら Busy として拒否されます（`strata_cli/update_cmd.py:403-418,257-260`、`strata_control/updater.py:311-322,1364-1365`）。
- engine の変更に伴い、必要な場合は保存済み tuning preset を短い再確認対象としてマークします（`strata_control/updater.py:1345-1352`、`strata_cli/update_cmd.py:264-270`）。

## 出力とエラー

- 成功時は標準出力に切替元・切替先を表示し、preset の状態と次の操作を案内します。比較上 rollback 先が新しい版なら「rolled-forward」として表示されます。`--output json` / `--json` では JSON 結果を出力します（`strata_cli/update_cmd.py:257-270`、`strata_cli/cli.py:508-515,2249-2254`）。
- `previous` がない、または既にその engine を使っている場合は終了コード 2。対象 package が壊れている・署名検証に失敗する場合、指定 backend で使用できない場合は終了コード 5 です（`strata_control/updater.py:1361-1376,1327-1336`）。
- 稼働中 engine の終了待ちが必要なのに待機できない場合は Busy による終了コード 7 です。失敗は human 出力では標準エラーに `strata:` 付きで出力し、JSON 系出力ではエラー JSON になります（`strata_control/updater.py:72-83`、`strata_cli/update_cmd.py:237-242,307-311`）。

## 根拠

- `strata_cli/update_cmd.py:47-56,80-82` — 共通 parser の `--backend` 宣言と rollback parser への登録。
- `strata_cli/update_cmd.py:233-271` — hardware backend の上書き、rollback の呼び出し、結果出力。
- `strata_control/engine_component.py:465-482,1012-1045,1064-1097` — backend/variant 分解、resolver の適合性判定と engine 選択。
- `strata_control/updater.py:261-281,1303-1352,1355-1377` — 検出値、pin/履歴更新、rollback 対象の検証と切替。
- `strata_cli/update_cmd.py:403-418`、`strata_control/updater.py:311-322` — 稼働中 engine の待機・拒否。
