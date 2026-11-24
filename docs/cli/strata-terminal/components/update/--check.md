# `strata components update --check`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--check` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。既定値は `False` |

## 役割

署名済み更新 feed を読み、現在の PC に対して Engine・Control・アプリの更新がどう見えるかを報告します。feed と署名の取得は行いますが、コンポーネント本体のダウンロードやインストールには進みません。成功時には確認結果を更新状態へ保存するため、状態ファイルへの書き込みはあります。

## 使い方

```sh
# 既定の feed を確認し、人向けの結果を表示
strata components update --check

# feed の場所を指定し、JSON で結果を受け取る
strata components update --feed ./update-feed --check --output json
```

同じ `--check` は `strata update --check` にも登録されていますが、文書の対象は `components update` スコープです。別 parser の定義であり、同じ処理へ合流します（`terminal/strata_cli/update_cmd.py:59-79, 361-367`）。

## 値と既定値

`argparse` の `store_true` で、引数値を取りません。指定しなければ `False` となり通常の更新処理へ進みます。複数回指定しても真偽値が真のままなので効果は変わりません。parser 上の同じコマンド階層には `--check` の別名はありません（`terminal/strata_cli/update_cmd.py:70-79`）。

## 実行時の動作

`strata components update` は `update_cmd.run` に渡されます。共通引数から component directory、backend、feed、出力形式などを設定し、ハードウェアと状態をもとに feed の場所を決めます。`--check` が真なら `updater.check(ctx)` を呼び、Engine・Control・アプリの選択・版比較と稼働中モデルの情報を含む報告を作って、通常のインストール処理には進まず終了コード 0 を返します（`terminal/strata_cli/cli.py:2210-2212`; `terminal/strata_cli/update_cmd.py:47-56, 318-325, 355-377`; `terminal/strata_control/updater.py:778-790`）。

feed は `--feed`、`STRATA_UPDATE_FEED`、状態に記録された HTTPS feed、既定 feed の順で選ばれます。ローカルパスや HTTP feed は後続実行の feed として記憶されず、次回も明示が必要です（`terminal/strata_cli/update_cmd.py:142-158`）。feed 本体と署名を読み、信頼鍵・署名・channel・有効期限・受理済み sequence を検証します（`terminal/strata_control/updater.py:451-470`; `terminal/strata_control/feed.py:650-677, 691-717`）。

`--backend` はハードウェア検出と Engine 候補に、`--app-version` または `STRATA_APP_VERSION` はアプリ版の比較に使われます。`--force` は Engine の過去の失敗記録による候補状態に影響します（`terminal/strata_cli/update_cmd.py:320-325`; `terminal/strata_control/updater.py:628-630, 700-729, 2002-2015`）。一方、`--app`、`--no-engine`、`--no-control` は `--check` 分岐より後の更新処理で参照されるため、この確認報告の対象を切り替えません（`terminal/strata_cli/update_cmd.py:361-372`）。`--wait`、`--yes`、`--stop-model`、`--start-again` も確認経路ではモデルを停止・待機・再起動しません。

## 適用条件と副作用

- `STRATA_NO_ACQUIRE` で取得が禁止されている場合は拒否されます。feed の確認も acquisition として扱われます（`terminal/strata_cli/update_cmd.py:355-358`; `terminal/strata_control/updater.py:438-440, 451-457`）。
- コンポーネント directory 内の `.updates/update.lock` を作成または開いてロックします。同じ directory で別 updater がロック中なら失敗します（`terminal/strata_control/updater.py:191-214, 780-782`）。
- 成功すると `.updates/state.json` に feed の sequence・source・確認時刻と `last_check` の結果を保存します。feed に署名済みモデル一覧があれば `.updates/feed-models.json` にキャッシュし、一覧がない feed なら古いキャッシュを削除します（`terminal/strata_control/updater.py:462-469, 778-789, 792-800`; `terminal/strata_control/feed_models.py:55-84`）。
- Engine・Control・アプリのパッケージ本体はダウンロードせず、インストール、Engine 切り替え、モデル停止、テスト起動もしません。アプリの版が不明な場合、報告上の installed version は不明として扱います（`terminal/strata_control/updater.py:778-789, 2002-2015`）。

## 出力とエラー

既定の `human` 出力は feed sequence/channel/署名鍵、PC 向け Engine 候補と不採用理由、Control とアプリの状態、稼働中モデルを標準出力へ表示します。`--output json` は結果全体を JSON で出し、`jsonl` は確認中の phase イベントと最終 JSON を行単位で出します（`terminal/strata_cli/update_cmd.py:117-139, 217-254, 361-367`）。

usage error は `argparse` により終了コード 2 です。feed 到達不能・読み取り失敗は通常 6、署名・信頼性・sequence の拒否は 5、同じ component directory のロック競合は 7 となり、失敗メッセージは human では標準エラー、JSON 系では `ok: false` の error object に出ます（`terminal/strata_cli/update_cmd.py:311-316, 378-390`; `terminal/strata_control/feed.py:50-65, 691-717`; `terminal/strata_control/updater.py:206-214`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:59-79` — `strata update` と `strata components update` の parser 定義、`store_true`、共通引数。
- `terminal/strata_cli/cli.py:2210-2212` — `components update` を `update_cmd.run` に委譲。
- `terminal/strata_cli/update_cmd.py:142-158, 307-390` — feed 選択、実行コンテキスト、`--check` の分岐、出力と例外処理。
- `terminal/strata_control/updater.py:451-470, 628-630, 778-800` — feed 取得・検証、Engine 判定、確認報告と状態保存。
- `terminal/strata_control/feed.py:650-677, 691-717` — 署名・channel・期限・sequence 検証、feed と署名の読み込み。
- `terminal/strata_control/feed_models.py:55-84` — 署名済みモデル一覧キャッシュの保存・削除。
