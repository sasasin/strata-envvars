# `strata update --model-config`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--model-config` |
| 別名 | なし |
| 値 | run config JSON ファイルのパス（`RUN_CONFIG.json`）。parser は文字列として受け取る |

## 役割

エンジン更新時、新しいエンジンを実際に起動して確認する試験に使うモデルの run config を指定します。省略時はインストール済みモデルから対象エンジン用の config が選ばれます。この指定は更新後エンジンの試験起動に使われ、`--check` の確認処理には使われません。

## 使い方

```sh
# 指定した run config のモデルで、新しいエンジンを試験してから更新する
strata update --model-config ./configs/test-run.json

# 更新候補だけを確認する。この場合、run config による試験起動は行わない
strata update --check --model-config ./configs/test-run.json
```

## 値と既定値

- parser は `--model-config` に `RUN_CONFIG.json` という metavar を付け、文字列を受け取ります。既定値は `None` で、必須指定ではありません（`terminal/strata_cli/update_cmd.py:47-56,59-62`）。
- Strata 側にパスの存在確認や JSON の事前検証をする parser 処理はありません。相対パスは `Path` として読み込まれるため、実行時の作業ディレクトリを基準に解決されます（`terminal/strata_control/updater.py:1360-1376`）。
- 空文字列は実行時の選択式で未指定と同様に扱われ、インストール済みモデルからの自動選択に進みます（`terminal/strata_control/updater.py:1364-1365`）。
- `strata components update` にも同じ `_common` parser が登録され、同じ `run_config` 経路を通ります。索引上のこの文書の scope は `strata update` です（`terminal/strata_cli/update_cmd.py:47-56,59-79,324`; `terminal/strata_cli/cli.py:2210-2212`）。

## 実行時の動作

1. `strata update` は引数を `updater.Context.run_config` に渡します（`terminal/strata_cli/update_cmd.py:318-325`）。
2. エンジン更新の試験起動では、指定値があればそのパスを使い、なければインストール済みモデルから対象 engine component に合う run config を探します（`terminal/strata_control/updater.py:1360-1365,917-938`）。対象 component と異なる config と判定された場合は、対象に合う config を再検索します（`terminal/strata_control/updater.py:1364-1369`）。
3. 選ばれた JSON を読み込み、試験用 sandbox 内のコピーを作ります。config の engine 参照・backend・host・port・log を試験用に置き換え、引数を短時間の試験向けに軽量化し、試験環境変数を加えて一時 profile から起動します。新エンジンが ready になっても generation が未確認なら 1 token の応答を検証し、最後に停止します。指定元の config ファイル自体を書き換える処理ではありません（`terminal/strata_control/updater.py:1373-1395,1414-1456`）。
4. 更新候補確認の `--check` は `updater.check` の結果を出して終了し、試験起動へ進みません。また、エンジン更新を無効にした実行ではこの値を使うエンジン試験は行われません（`terminal/strata_cli/update_cmd.py:361-372`）。

## 適用条件と副作用

- 効果があるのは更新処理がエンジンを試験する場合です。対象モデルが見つからず `run_config` も指定されていない場合、既定で `allow_no_model_smoke=True` のため、モデルをロードせずバイナリの smoke check にフォールバックします（`terminal/strata_control/updater.py:423-427,1364-1372`）。
- 指定 config が別 component 用と判定された場合は、その指定を使わず対象 component 用 config の自動検索に切り替わります。config component の判定には `exe`、`arch`、engine 固有引数が使われます（`terminal/strata_control/updater.py:865-908,1364-1369`）。
- 試験用の一時 directory、profile、runtime、engine log を作り、試験では loopback host と空き port を使用します。通常は完了後に sandbox を削除します。試験起動に失敗した場合は診断用ログ・記録を更新領域に残してから sandbox を削除します（`terminal/strata_control/updater.py:1374-1375,1414-1425,1435-1456,1123-1149`）。
- 試験時は config 内の `env` を引き継ぎますが、試験専用環境変数で上書きします。API key は子プロセス環境から除かれます（`terminal/strata_control/updater.py:1394-1398,1419-1425`）。

## 出力とエラー

- 指定 config を読み込めない、JSON として読めない、または試験起動に使えない場合、試験起動の失敗として扱われます。試験失敗は exit code 6 となり、新エンジンは切り替えられず現在のエンジンが維持されます。テキスト出力は stderr に `strata: ...` を出し、`--output json` / `jsonl` では機械可読形式の失敗を出します（`terminal/strata_control/updater.py:86-100,132,1442-1449,1567-1588`; `terminal/strata_cli/update_cmd.py:311-316,378-386`）。
- JSON 読み込みの前段で component 判定に失敗した場合、その判定関数は一般 engine として扱います。対象が別 component なら自動検索に切り替わるため、指定 path の問題が直ちに報告されるとは限りません（`terminal/strata_control/updater.py:871-877,1364-1369`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56,59-79` — parser 定義、既定値、値の表示名、および `components update` との共通登録。
- `terminal/strata_cli/update_cmd.py:318-325,361-382` — 値の Context への転送、`--check` 分岐、出力と例外処理。
- `terminal/strata_control/updater.py:865-938,1360-1399` — config の component 判定・自動選択・読込・試験用変換。
- `terminal/strata_control/updater.py:1414-1456,1560-1588` — sandbox 内の試験起動、停止、失敗時記録と更新中止。
- `docs/cli/README.md:257-268` — `strata update` 階層と作成対象リンクの確認。索引は変更していません。
