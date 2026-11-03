# `strata components use --family`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--family` |
| 別名 | なし |
| 値 | `qwen` または `deepseek`。値は必須 |

## 役割

導入済み engine のうち、どの engine 系統から対象を選ぶか指定します。同じ版番号が複数系統に存在する場合の候補絞り込みに使います。モデルの family を選ぶオプションではありません。コマンドは engine を切り替え、ダウンロードはしません（`strata_cli/update_cmd.py:84-87`）。

## 使い方

```sh
strata components use 0.1.54 --family deepseek
```

版番号の代わりに、インストール済み engine の folder 名、または `newest` を指定できます（`strata_cli/update_cmd.py:84-87`）。

## 値と既定値

- `argparse` の `choices` は `qwen` と `deepseek`、既定値は `None` です。オプション省略時は両系統を候補に含めます（`strata_cli/update_cmd.py:84-87`、`strata_control/engine_library.py:198-205`）。
- 値は必須です。未指定、または `qwen` / `deepseek` 以外の値は parser が拒否し、usage とエラーを表示して終了コード 2 になります。繰り返し指定時は `argparse` の通常の単一値引数として最後の値が残ります（宣言: `strata_cli/update_cmd.py:86`）。
- `newest` に加え `latest` も内部で同じ意味として扱われますが、parser の help は `newest` のみを位置引数の例として示します（`strata_control/engine_library.py:198-205`）。

## 実行時の動作

`strata components use` の parser は `_common()` ではなくこの `--family` を直接登録します。コマンド処理では `list_engines()` が作る候補一覧に `a.family` を渡し、その値に一致する family の候補だけから指定された版番号・folder 名・`newest` を検索します（`strata_cli/update_cmd.py:84-87,358-363,378-379`、`strata_control/engine_library.py:180-195,198-205`）。family を省略して複数候補が一致すれば曖昧エラーとなり、folder 名を使うよう案内されます（`strata_control/engine_library.py:209-210`）。

候補一覧は engine を読み取り、Qwen 系では OS、backend、runtime、GPU architecture、driver、署名・ファイル整合性などからこの PC で実行可能かを判定します。DeepSeek 系では OS と指定 backend を使って適合性を判定します（`strata_control/engine_library.py:59-81,91-123,136-162`）。`--family` 自体はこの適合性判定を変更せず、候補を絞ります。選択された候補が実行不可なら切替前に終了コード 5 のエラーとなります（`strata_cli/update_cmd.py:378-383`）。

切替時には共有 engine 更新 lock を取り、実行中モデルがあれば停止を待つか、待ち時間を超えて Busy エラーになります（`strata_control/engine_library.py:225-239`）。Qwen engine は署名と全ファイルを再検証してから pin / active 状態などを更新します。最新 engine を選んだ場合は pin を外して更新追従に戻し、それ以外は pin します（`strata_control/engine_library.py:246-262`、`strata_control/updater.py:1303-1352`）。DeepSeek engine は test start の可否を確認し、最新でない場合は pin を設定し、関連する保存済み設定を選択先へ向け直し、履歴を保存します。最新を選んだ場合は pin を解除します（`strata_control/engine_library.py:265-289`）。

## 適用条件と副作用

このオプションは `strata components use` の候補検索にのみ作用します。同じ `--family` 内でも同一版番号に複数の folder が一致すれば、引き続き曖昧となり folder 名を指定する必要があります（`strata_control/engine_library.py:204-210`）。

切替は将来起動する engine に適用され、すでに動作中のモデルを差し替えません。Qwen 系では共有更新 state の pin / active / previous / skipped / 履歴が更新され、engine が変わったときは保存 tuning preset が短い再確認対象としてマークされる場合があります。DeepSeek 系では family 側の pin、設定参照先、履歴が更新されます。engine のダウンロードや削除は行いません（`strata_control/engine_library.py:225-239,246-289`、`strata_control/updater.py:1303-1352`）。

## 出力とエラー

- 成功時は人間向け出力で「既に使用中」または切替先・preset の扱い・更新追従状態を表示します。`--output json` / `jsonl` では機械向け JSON を出力します（`strata_cli/update_cmd.py:358-394`）。
- 指定 family に該当する engine がない場合や、指定が曖昧な場合はエラーになります。人間向けでは `strata: ...` を stderr に出し、エラーコードを終了コードとして返します。該当 engine がない・曖昧はコード 2、実行不能または検証失敗はコード 5、稼働中モデルにより切替できない場合はコード 7 です（`strata_control/engine_library.py:198-210,216-239,248-260,265-279`、`strata_cli/update_cmd.py:237-242,378-383`）。
- 同一 revision の CLI help も確認し、parser 定義と `qwen` / `deepseek` の選択肢が一致することを照合しました。help は `latest` alias の説明を含みません。実行したのは help 表示のみで、engine 切替は行っていません。

## 根拠

- parser と位置引数: `strata_cli/update_cmd.py:82-95`
- コマンド処理、候補選択、適合性エラー: `strata_cli/update_cmd.py:358-400`
- 候補の family 絞り込み、`newest` / `latest`、未一致・曖昧時: `strata_control/engine_library.py:180-210`
- 切替 lock と Qwen / DeepSeek の分岐、検証: `strata_control/engine_library.py:216-289`
- 適合性判定と一覧生成: `strata_control/engine_library.py:59-81,91-123,136-162`
- Qwen engine の pin、state、preset mark 更新: `strata_control/updater.py:1303-1352`
- 共通 option 登録と `--json` / `--quiet`: `strata_cli/cli.py:508-515`
