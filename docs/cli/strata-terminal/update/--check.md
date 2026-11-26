# `strata update --check`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--check` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`、既定値 `false`） |

## 役割

署名済み更新 feed を読み、現在の PC に対する Engine・Control・アプリの更新候補や、稼働中モデルの有無を報告します。更新処理の実行、Engine/Control/アプリのパッケージ取得、切り替えは行いません。ただし feed 本体と署名ファイルの読み込み、および確認状態・feed 内モデル一覧キャッシュの更新は行います。

## 使い方

```sh
# 既定の更新 feed を確認する
strata update --check

# 指定した feed を確認する
strata update --check --feed https://example.invalid/strata-feed.json

# 機械処理向け JSON で結果を得る
strata update --check --output json
```

`--feed` には URL またはローカルのファイル／フォルダーを指定できます。省略時は `STRATA_UPDATE_FEED`、前回記録された HTTPS feed、プラットフォームに応じたプロジェクト既定 feed の順で選ばれます（`terminal/strata_cli/update_cmd.py:33-44,142-158`）。

## 値と既定値

`--check` は `argparse` の `store_true` であり、値を受け取りません。省略時は通常の更新経路に進み、指定時は feed 確認経路に分岐します（`terminal/strata_cli/update_cmd.py:59-69,361-367`）。同じコマンドの複数回指定について個別の拒否処理はなく、いずれも真として扱われます。`--check=false` のような値付き指定はフラグ構文ではないため parser が受理しません。

## 実行時の動作

コマンド実行時に `--components-dir` 等からコンポーネント保存先を決め、`--backend` があればその指定を使ってハードウェア情報を組み立てます。次に取得禁止ポリシーを確認し、信頼鍵を読み込んで feed の場所を決めます。その後 `updater.check()` を呼び、対象コンポーネントフォルダー単位のロックを取り、署名付き feed とその署名ファイルを読みます。署名・feed 形式・channel・有効期限・既に受理した sequence より古くないことを検証したうえで、ローカル状態とハードウェアに照らして Engine、Control、アプリの差分を計算します（`terminal/strata_cli/update_cmd.py:307-367`; `terminal/strata_control/updater.py:451-470,628-630,778-789`; `terminal/strata_control/feed.py:650-677,691-717`）。

Engine の判定は PC の platform/backend/GPU 等に合う feed 項目を選び、未導入・更新可能・現行・この PC 向け候補なし等を報告します。Control とアプリもインストール済み／実行環境のバージョン情報と feed のバージョンを比較します。ここでの選択は結果表示用で、インストールや切り替えはしません（`terminal/strata_control/updater.py:628-630,672-740,1886-1899,2002-2015`）。

`--output human`（既定）は候補と状態を行ごとに表示します。`json` はレポートを JSON で出力し、`jsonl` は進捗イベントと結果を JSON Lines で出力します。出力形式の許容値は `human`、`json`、`jsonl` です（`terminal/strata_cli/update_cmd.py:47-56,117-139,217-254,361-367`）。

## 適用条件と副作用

- `STRATA_NO_ACQUIRE` 等で取得が禁止されているプロセスでは、feed を読む前に拒否されます（`terminal/strata_cli/update_cmd.py:355-358,387-388`; `terminal/strata_control/updater.py:438-440,451-457`）。
- ネットワーク feed の場合、feed と署名ファイルを取得します。ローカルパス／URL feed も指定できます。HTTP(S) 読み込みは `read_small` のサイズ上限（8 MiB）と通信ポリシーの対象です（`terminal/strata_control/feed.py:691-717`; `terminal/strata_control/transfer.py:109,298-334`）。Engine、Control、アプリ本体のアーカイブはこの分岐ではダウンロードされません（`terminal/strata_cli/update_cmd.py:361-377`; `terminal/strata_control/updater.py:778-789`）。
- 確認は完全な読み取り専用ではありません。成功時は `<components>/.updates/state.json` に受理した feed 情報と `last_check` を保存します。また、署名済み feed にモデル一覧があれば `.updates/feed-models.json` を保存し、一覧がなければ既存キャッシュを削除します。モデルキャッシュの更新失敗は警告ログに留まり、確認処理自体を失敗させません（`terminal/strata_control/updater.py:227-267,451-470,778-789`; `terminal/strata_control/feed_models.py:55-84`）。
- 同じコンポーネント保存先で別の updater がロック中なら確認も失敗します（`terminal/strata_control/updater.py:195-224,778-782`）。
- 共通オプション `--feed`、`--components-dir`、`--backend`、`--output` は確認処理にも影響します。`--app`、`--no-engine`、`--no-control`、`--yes`、`--stop-model`、`--start-again` 等は `--check` 分岐より後の更新処理で参照されるため、この経路ではダウンロード対象やモデル停止を変更しません（`terminal/strata_cli/update_cmd.py:47-69,361-377`）。

## 出力とエラー

成功時の終了コードは `0` です。人向け出力では feed sequence/channel/署名鍵、Engine の選択と不採用理由、Control・アプリの状態、稼働中モデルの情報などを表示します。`json`／`jsonl` では成功レポートを出力します（`terminal/strata_cli/update_cmd.py:217-254,361-367`）。

取得禁止は終了コード `5`、feed に到達できない場合は `6` です。署名・信頼鍵・feed 検証エラーは `FeedError` の終了コード（既定 `5`）、受理済み feed より古い sequence は拒否されます。人向けエラーは標準エラーへ `strata:` 接頭辞付きで出力し、機械向け形式ではエラー情報を JSON にします（`terminal/strata_cli/update_cmd.py:311-316,378-390`; `terminal/strata_control/feed.py:50-66,650-677,691-717`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-69` — 共通 parser と `strata update --check` の宣言、他の update 専用オプション。
- `terminal/strata_cli/update_cmd.py:142-158,307-367` — feed 優先順位、実行コンテキストの構築、取得許可確認、`--check` 分岐、結果出力。
- `terminal/strata_control/updater.py:451-470,628-630,672-740,778-789` — feed 読み込み・状態記録、Engine 判定、確認処理のロックとレポート生成。
- `terminal/strata_control/feed.py:650-677,691-717` — 署名・形式・channel・期限・sequence の検証と feed／署名読み込み。
- `terminal/strata_control/updater.py:227-267` — updater 状態ファイルの読み書き。
- `terminal/strata_control/feed_models.py:55-84` — モデル一覧キャッシュの保存・削除と失敗時の扱い。
- `terminal/strata_control/transfer.py:109,298-334` — 小さな feed ファイルの上限と読み込み・通信エラー。

索引には `strata components update --check` も別のコマンド階層で掲載されています（`docs/cli/README.md` の `strata components update` 節）。parser も同じ `--check` を別コマンドに登録していますが、本書の対象は `strata-terminal/update` のみです（`terminal/strata_cli/update_cmd.py:70-79`）。
