# `--app`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--app` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。既定値は `false` |

## 役割

通常は engine と Control を更新する `strata components update` に、デスクトップアプリの更新インストーラーの取得と検証を追加する。インストーラーの実行・アプリ本体のインストールはこの CLI の処理範囲外で、取得後に利用者がインストーラーを実行する（`strata_cli/update_cmd.py:42-59,213`、`strata_control/updater.py:1226-1229,1250-1257`）。

## 使い方

```sh
strata components update --app
```

engine と Control を更新せずアプリのインストーラーだけ取得する場合は、両方の抑止フラグも指定する。

```sh
strata components update --app --no-engine --no-control
```

`--app` は `strata components update` と `strata update` の双方に個別に登録されている。ここでは索引が指す `components/update` のスコープを説明する。同じ文字列でもトップレベル `update` の文書は別スコープである（`strata_cli/update_cmd.py:42-59`）。

## 値と既定値

- 引数 parser は値なしの `store_true` として登録し、省略時は `false`。指定すると `run_update(..., app=True)` に渡される（`strata_cli/update_cmd.py:50-56,213`）。
- 対象インストール済みアプリのバージョンは `--app-version` が truthy ならその値、そうでなければ `STRATA_APP_VERSION` 環境変数から取得する。どちらもなければ installed version は不明として扱われる（`strata_cli/update_cmd.py:27,53-54,182-184`）。
- feed にアプリ項目があり、この PC の platform 用 entry がある場合、feed のアプリ版が installed version より新しければ取得する。installed version が不明なら版比較をせず取得対象とする。feed にアプリ項目がない場合、または platform entry がない場合は取得しない。現行版以下なら `current` として取得を省略する（`strata_control/updater.py:1210-1223,1230-1234`）。

## 実行時の動作

`--app` は既定で有効な engine / Control 更新を置き換えず、アプリ取得ステップを追加する。`--no-engine` と `--no-control` を併用した場合はアプリだけが対象になる。各ステップは個別に実行され、ひとつが失敗しても残りのステップを試し、失敗時は最初の `UpdateError` の終了コードを返す（`strata_cli/update_cmd.py:213`、`strata_control/updater.py:1274-1297`）。

アプリ対象となった場合は feed のプラットフォーム別 URL、サイズ、SHA-256、署名を使う。ダウンロードは feed 記載のサイズと SHA-256 を照合し、続けて `STRATA_APP_UPDATE_PUBKEY` または同梱 `update_keys.json` の `app_minisign_public` を使って minisign 署名を検証する。成功したインストーラーはコンポーネントディレクトリ配下の `.updates/app/` に保存される。CLI はインストーラーを起動しない（`strata_control/updater.py:1197-1207,1226-1257`、`strata_control/updater.py:470-493`、`strata_control/transfer.py:198-221`、`strata_control/signing.py:294-330`）。

`--check` を付けたときはチェック専用経路になり、`--app` の有無にかかわらず app の更新状態を報告するだけで、インストーラーをダウンロードしない（`strata_cli/update_cmd.py:203-209`、`strata_control/updater.py:624-639`）。

## 適用条件と副作用

- 実更新は明示的な取得操作であり、取得が禁止された環境では拒否される。署名済み feed の読込後、更新ロックを取得して処理する（`strata_cli/update_cmd.py:197-200,225-234`、`strata_control/updater.py:355-366,1277-1281`）。
- 対象 platform 用アプリ entry があると、ネットワークまたはローカル feed からファイルを取得し、コンポーネントディレクトリに `.updates/partial/` と `.updates/app/` を作成・使用する。中断時の部分ダウンロードは次回再開用に保持される。署名不一致のファイルは削除される（`strata_control/updater.py:470-493,1239-1254`、`strata_control/transfer.py:198-221`）。
- app の公開鍵がない場合は取得しない。feed にアプリがない、対象 platform がない、または installed version が feed 版以上の場合もアプリファイルを取得しない（`strata_control/updater.py:1210-1237`）。

## 出力とエラー

- 成功時の人間向け出力には取得した版、保存パス、検証済みでありインストーラーを実行して完了する旨が表示される（`strata_cli/update_cmd.py:125-129`）。`--output json` / `jsonl` では各コンポーネント結果を含む機械可読出力になる（`strata_cli/update_cmd.py:62-84,213-224`）。
- app 公開鍵なし、アプリ署名不一致、feed 記載 SHA-256 との不一致は拒否扱い（終了コード 5）。ネットワーク転送失敗は終了コード 6、中断は 130 で部分ファイルを保持する。app の署名不一致時は取得したファイルを削除する（`strata_control/updater.py:1235-1249,470-493`、`strata_cli/update_cmd.py:225-234`）。
- アプリのインストーラー自体は OS / 配布形式ごとに異なる。実行時のインストール挙動は本オプションの処理ではなく、この調査では検証していない。

## 根拠

- parser、既定値、コマンド間の登録、実行への引き渡し: `strata_cli/update_cmd.py:42-59,163-184,197-234`
- feed に対するアプリ版・platform の判定、ダウンロード・署名検証・保存: `strata_control/updater.py:1195-1257`
- 更新処理順、失敗集約: `strata_control/updater.py:1274-1297`
- サイズ・SHA-256 照合と転送失敗の分類: `strata_control/updater.py:470-493`、`strata_control/transfer.py:198-221`
- minisign 検証: `strata_control/signing.py:294-330`
- `--check` の分岐と出力: `strata_cli/update_cmd.py:203-209`、`strata_control/updater.py:624-639`
- 調査した Strata checkout は commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、作業ツリーは `main...origin/main` で変更なし。安全に実行できる同一 revision の既存 CLI `--help` と Release artifact は確認していないため、この文書は parser と実装ソースに基づく。
