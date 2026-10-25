# `strata components update`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| 主な実装 | `strata_cli/update_cmd.py`、`strata_control/updater.py` |
| 同等の入口 | `strata update`（共通の更新処理） |

## 役割

署名付き更新 feed を読み、この PC 向けの engine と Strata Control を取得・検証して更新します。engine はテスト起動に成功してから切り替えられ、以前の engine は rollback 用に保持されます。Control は新しいコピーをテストしてから有効版を切り替えます。モデルの起動や server の通常実行とは別の、明示的な取得・更新コマンドです（`strata_cli/update_cmd.py:1-11,43-59`、`strata_control/updater.py:1274-1297`）。

## 代表的な使い方

```sh
# 更新 feed と、この PC に対する更新内容を確認する
strata components update --check

# engine と Control を更新する
strata components update

# engine と Control に加えて、アプリの installer も取得・検証する
strata components update --app
```

`--check` は更新内容を表示する確認モードです。実際の更新を行う場合は、確認後に通常の `strata components update` を実行します。`--app` を付けた場合、Terminal はアプリを自動インストールせず、署名と SHA-256 を確認した installer を components ディレクトリ内に保存します（`strata_cli/update_cmd.py:43-56,203-224`、`strata_control/updater.py:624-640,1226-1257`）。

## 主な動作と副作用

- 既定の feed は環境変数 `STRATA_UPDATE_FEED`、前回記録した feed、プロジェクトの Release feed の順に選ばれます。`--feed` があればそれを使います。feed の署名と更新 sequence を検証し、古い feed の再適用を拒否します（`strata_cli/update_cmd.py:23-25,87-95`、`strata_control/updater.py:355-366`）。
- 更新先は `--components-dir`、または per-user の components ディレクトリです。engine と Control の取得物や状態をそこに保存します（`strata_cli/update_cmd.py:174-184`、`strata_control/engine_component.py:176-177`）。
- engine は対象機種向けの package を取得し、展開後に署名・全ファイル・feed の記載内容・hardware 適合性を確認します。その後 staging 領域でテスト起動し、serving engine がないことを再確認してから切り替えます。旧 engine は1世代を rollback 用に残します（`strata_control/updater.py:656-698,930-1028`）。
- Control は staging 領域で `--version` を実行して応答を確かめてから有効版を切り替えます。更新後の Terminal は次のコマンドから新しい Control に引き継ぎ、アプリは次回起動時に切り替わります（`strata_control/updater.py:1114-1132,1145-1192`）。
- `--check` は feed の取得と照合に加えて、最後の確認結果を components state に保存します。engine、Control、アプリ本体の installer を含め、通常更新はネットワーク取得とディスク書き込みを伴います（`strata_control/updater.py:624-640,1274-1297`）。
- engine の更新中に serving engine が見つかると、既定では engine の置き換え・テストを拒否します。対話端末では待機するか尋ね、`--wait SECONDS` を指定すると停止を待ちます。engine の更新が拒否されても、個別処理のため後続の Control 更新などは続く場合があります（`strata_cli/update_cmd.py:237-252`、`strata_control/updater.py:65-75,302-312,945-978,1274-1297`）。
- `STRATA_NO_ACQUIRE=1` などで取得が禁止されたプロセスからは実行できません。更新各項目は別々に処理されるため、一つが失敗しても先に成功した項目は取り消されません（`strata_cli/update_cmd.py:197-198,225-234`、`strata_control/acquisition.py:12-14,32-43`、`strata_control/updater.py:1274-1297`）。

## 注意点

更新処理は engine・Control・必要に応じてアプリ installer をダウンロードし、ローカルの components 状態を書き換えます。まず `--check` で対象と feed を確認できますが、この確認でも feed の参照と最終確認状態の保存は行われます。engine のテスト起動に使うモデルは、既定では利用可能なインストール済みモデルから選ばれます。必要なら `--model-config RUN_CONFIG.json` で指定できます（`strata_control/updater.py:624-640,701-715`）。

更新結果は既定で人向け表示です。`--output json` または `jsonl` では機械可読形式を選べます。実装上の終了コードは、成功または更新不要が `0`、利用拒否・feed/署名等の拒否が主に `5`、ネットワークやテスト起動などの失敗が `6`、engine serving 中が `7`、中断が `130` です（`strata_cli/update_cmd.py:9-11,62-84,167-172,225-234`、`strata_control/updater.py:65-75,1274-1297`）。

## オプションと関連文書

このコマンドの option scope は `strata components update` です。オプションと個別の値・既定値の説明は[CLI 索引の `strata components update` 節](../../../README.md)を参照してください。`strata update` も同じ parser と実行関数を使います（`strata_cli/update_cmd.py:42-59`、`strata_cli/cli.py:139-140,2135-2137`）。engine のローカル選択確認には [`strata components engine`](../engine/README.md)、以前の engine に戻す操作には [`strata components rollback`](../rollback/README.md) を参照してください。

## 根拠

- Strata `strata_cli/cli.py:139-140,2135-2137` — update parser の登録と dispatch。
- Strata `strata_cli/update_cmd.py:1-11,23-59,87-95,163-234,237-252` — コマンド説明、parser、feed 選択、更新実行、出力・エラー、serving 時の待機。
- Strata `strata_control/updater.py:355-366,624-640,656-698,930-1028,1114-1192,1226-1257,1274-1297` — feed 検証、確認、engine/Control/app の更新、失敗と状態保存。
- Strata `strata_control/acquisition.py:12-14,32-43`、`strata_control/engine_component.py:176-177` — 取得禁止条件と既定 components ディレクトリ。

調査範囲は上記 commit の checkout にある Terminal CLI と `strata_control` 実装です。別 platform の実機更新や Release artifact の実ダウンロードは行っていません。
