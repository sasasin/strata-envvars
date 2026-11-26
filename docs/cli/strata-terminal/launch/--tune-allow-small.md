# `--tune-allow-small`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--tune-allow-small` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると有効、既定は無効。 |

## 役割

launch 時の自動チューニングで、回答がわずかに変わる可能性のある設定候補も試行対象にします。通常は、回答の配置に依存する候補（expert cache の再配分や speculative window など）は候補から除外されます。このフラグはその候補を許可するもので、回答の変化を避ける設定ではありません。

## 使い方

```sh
# モデル選択後に quick tuning を行い、回答がわずかに変わり得る候補も試す
strata launch --tune quick --tune-allow-small
```

チューニングを実行するには `--tune quick` または `--tune thorough` が必要です。`--tune` の既定値は `skip` なので、`--tune-allow-small` だけを指定しても候補の試行は行われません。

## 値と既定値

引数 parser は `action="store_true"` で登録されているため、値は不要で、指定時に真になります。値の範囲や個別 validation はありません。launch の設定値は既定で `False` です。プリセットから設定を読み込んだ後、このフラグが指定されると設定を `True` にします。CLI には明示的に `False` に戻す対になるフラグはありません（`terminal/strata_cli/launch/cmd.py:122,215-220,274-277`、`terminal/strata_cli/launch/settings.py:141-142`）。

## 実行時の動作

launch は tuning モードが `skip` ならチューニングを呼ばず、このフラグも使いません。`quick` / `thorough` であっても、同じ設定のチューニング済みプリセットまたは保存済み結果があり、`--retune` がなければ測定を再利用して終了します。実際にチューニングへ進む場合、launch は内部の `strata tune auto` 呼び出しにこの設定を `--allow-small-differences` として付加します（`terminal/strata_cli/launch/runner.py:2373-2405`）。

内部チューナーはこの値を `allow_placement` に設定します。候補の回答分類が `placement` の場合に限り、許可設定が真なら候補を残します。候補表の例は expert cache の再配分頻度・減衰 (`--adapt-every` / `--adapt-swaps` / `--adapt-decay`)、`--spec 3`、PCIe share、特定の Qwen3.6 hybrid 向け設定です。実際に試すかどうかは family、backend、マシン分類、必要条件、engine が受け付けるフラグ、候補の検査にも依存します。品質設定は常に自動選択せず、回答が再現不能になる候補には別の許可フラグが必要です（`terminal/strata_cli/tune_commands.py:37-39,342-344`、`terminal/strata_control/tune_knobs.py:58-77,93-114,375-379,434-473`）。

プリセットにチューニング結果が保存された場合、その結果は以後の起動時にも利用されます。測定時には launch 自身が起動した同一プロファイルのサーバーをチューニング用に停止し、完了後の通常フローでサーバーを起動します。他のエンジンはこの停止処理の対象ではありません（`terminal/strata_cli/tune_commands.py:383-425`、`terminal/strata_cli/launch/runner.py:2405-2407,2441-2448,3333-3338`）。

## 適用条件と副作用

- Hy4-Flash と Inkling-2-Mini のネイティブ Strata family は launch の tuning 処理自体をスキップするため、このフラグの効果はありません（`terminal/strata_cli/launch/runner.py:1214-1216,2373-2376`）。
- チューニング候補を増やすため、測定時間や試行数が増えることがあります。候補が実行可能かは上記の適用条件によります。
- チューナーは成功時に結果をプリセットとして保存し、試行履歴や tuning report を記録します。launch は進捗 JSON を `launch_dir()` 配下の `<名前>.tune.json` に置き、既存ファイルの削除を試みてから測定を始めます（`terminal/strata_cli/tune_commands.py:371-374,395-420`、`terminal/strata_cli/launch/runner.py:2395-2407`）。

## 出力とエラー

このフラグ固有の警告やエラー経路はありません。launch は測定中の進捗を表示し、結果が得られない場合は「チューナーが完了せず、標準設定で実行し、設定は変更されなかった」と報告します。チューナー側は JSON 出力時に結果を stdout に出し、失敗理由に応じて終了コードを返します。launch は終了後の JSON 結果を読み取り、測定失敗でも通常設定で起動を続ける経路を持ちます（`terminal/strata_cli/launch/runner.py:229-232,2406-2439`、`terminal/strata_cli/tune_commands.py:421-425`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:121-123` — launch parser の登録。`store_true` と help 文言。
- `terminal/strata_cli/launch/cmd.py:215-220,274-277` — launch 設定の生成、プリセット読込後のフラグ反映。
- `terminal/strata_cli/launch/settings.py:141-142,448-450` — 既定値と、設定表示用の引数列への反映。
- `terminal/strata_cli/launch/runner.py:2373-2405` — skip/native family/既存 tuning 結果の分岐と、内部チューナーへの転送。
- `terminal/strata_cli/tune_commands.py:37-39,342-344` — 内部 `--allow-small-differences` parser と `allow_placement` への設定。
- `terminal/strata_control/tune_knobs.py:83-114,375-379,434-473` — placement 候補の定義、許可判定、環境・engine 条件による候補除外。
- `terminal/strata_cli/launch/runner.py:2406-2439,2441-2448,3333-3338` — 測定進捗・結果処理、同一 profile のサーバー停止、launch の後続起動。
- `terminal/strata_cli/tune_commands.py:371-374,395-425` — tuner scratch directory、結果・report 保存、終了コード。
