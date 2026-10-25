# `strata update`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| 主な実装 | `strata_cli/update_cmd.py`、`strata_control/updater.py` |

## 役割

署名済み update feed を読み、この PC 向けの推論エンジンと Strata Control を取得・更新します。エンジンは展開後に署名・ファイル・適合性を検査し、テスト起動に成功してから切り替えます。通常の起動・推論処理ではなく、ネットワークからコンポーネントを取得する明示的な更新コマンドです（`strata_cli/update_cmd.py:1-11,42-49`、`strata_control/updater.py:926-927,943-959,977-1025,1274-1285`）。

## 基本的な使い方

```sh
# エンジンと Control を feed に従って更新
strata update

# 更新候補を確認（feed の取得と確認状態の記録は行う）
strata update --check

# デスクトップアプリ用インストーラーも取得して検証
strata update --app

# エンジンを更新せず、Control だけ更新
strata update --no-engine
```

feed の場所は `--feed`、`STRATA_UPDATE_FEED`、前回記録された feed、プロジェクト既定値の順で選ばれます。既定値は Strata の GitHub Releases にある `strata-feed.json` です。信頼された署名鍵がない、署名が不正、または古い feed sequence などの feed は拒否されます（`strata_cli/update_cmd.py:23-25,30-39,87-94,197-200`、`strata_control/updater.py:355-366`、`strata_control/feed.py:312-330`）。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 更新 | `strata update` | エンジン、Control の順で更新を試みます。どちらか一方が失敗しても、他方の処理を続け、結果を個別に報告します。 |
| 確認 | `strata update --check` | feed を読み、エンジン・Control・アプリの候補を表示します。コンポーネントのアーカイブは取得しませんが、feed 状態と `last_check` を component state に保存します。`--app` と併用しても確認モードになり、installer は取得しません。 |
| アプリ installer 取得 | `strata update --app` | 通常の更新対象にアプリ installer も加え、署名とハッシュを確認して `.updates/app` に保存します。Terminal は installer を実行しません。 |
| 対象の限定 | `strata update --no-engine` / `--no-control` | それぞれエンジンまたは Control の更新を省きます。両方指定すると通常更新対象がなくなり、`--app` も指定しなければ feed を読み取った後に更新ステップはありません。 |

`--check` は feed の問い合わせと確認状態の保存を行うため、ファイル・ネットワークに一切触れない dry run ではありません。`--output human|json|jsonl` と、その alias `--json`、`--quiet` で出力を選べます。`--json` と `--quiet` は個別 parser の後に共通で追加されます（`strata_cli/update_cmd.py:39,62-84,203-209`、`strata_control/updater.py:624-640`、`strata_cli/cli.py:508-515`）。

## 更新時の主な動作と副作用

- `--components-dir` を省略すると既定のユーザー component directory を使います。`--backend` はハードウェア検出結果を上書きし、`--model-config` はエンジンのテスト起動に使う run config を指定します。`--force` はテスト起動失敗または rollback 済みとして記録されたバージョンを再試行します（`strata_cli/update_cmd.py:30-39,174-184`）。
- `--feed` を指定しない場合は、環境変数、記録済み feed、プロジェクト既定値から取得元を決めます。feed sequence などを component state に記録し、更新処理は component directory の lock を取得して進めます（`strata_cli/update_cmd.py:23-25,87-94`、`strata_control/updater.py:355-366,1277-1282`）。
- engine / Control / `--app` installer の各対象は順に処理されます。engine は一時領域へ展開し、署名・全ファイル・feed 記載の manifest と適合性を確認してからテスト起動します。切り替え時は前の engine を保持し、保存済み tuning preset はエンジン変更に応じて再確認対象になることがあります（`strata_control/updater.py:656-698,926-1025`）。
- Control は更新後、次の `strata` コマンドから新しい版が使われます。アプリ installer はダウンロードして検証・保存されますが、デスクトップアプリのインストールは行いません（`strata_cli/update_cmd.py:115-124,125-129`、`strata_control/updater.py:1226-1255`）。
- 実行中 engine があると更新は待機または拒否されます。端末対話時は既定で待つか確認し、`--wait SECONDS` を指定すると停止を待つ上限を設定します。JSON/非対話では確認を出さず、実行中なら Busy として失敗します。Strata launch が起動した engine の場合は先にモデルを止めてから再実行します（`strata_cli/update_cmd.py:34-35,237-252`、`strata_control/updater.py:62-71`）。
- 中断時は部分ダウンロードを保持し、次回更新で再開します。更新が禁止された `STRATA_NO_ACQUIRE` 環境では拒否されます（`strata_cli/update_cmd.py:9-11,197-198,231-234`、`strata_control/updater.py:470-492`）。

## 出力と失敗

標準出力には feed sequence と対象ごとの更新結果を表示し、`--output json` / `jsonl` では機械可読形式にします。エラーは human 出力では stderr、機械可読出力では JSON の error として出ます。実装コメントが示す終了コードは、`0` 成功または更新不要、`2` 使用条件エラー、`5` 拒否（署名・hash・downgrade・鍵なし・取得禁止など）、`6` 更新やテスト起動の失敗、`7` engine 稼働中、`130` 中断です。複数対象を処理する場合、失敗した対象を記録して後続対象も試し、最終コードには最初の失敗コードを使います（`strata_cli/update_cmd.py:9-11,62-84,163-172,225-234`、`strata_control/updater.py:1274-1297`）。

## 関連文書

- [`strata components update` の概要](../components/update/README.md) — 同じ更新実装を呼び出す別のコマンド階層です。
- [`strata components rollback` の概要](../components/rollback/README.md) — 更新時に保持された前の engine へ戻します。
- [CLI 索引](../../README.md) — `strata-terminal` のコマンド階層と option 文書。

## 根拠

- Strata `strata_cli/update_cmd.py:1-11,23-59` — コマンドの説明と parser 定義。
- Strata `strata_cli/update_cmd.py:87-94,163-234,237-252` — feed 選択、実行分岐、出力・失敗、稼働中 engine の扱い。
- Strata `strata_cli/cli.py:139-140,508-515,2135-2137` — parser 登録、共通 option 追加、`update_cmd.run` への委譲。
- Strata `strata_control/updater.py:355-366,624-640,656-698,926-1025,1226-1255,1274-1297` — feed/state、確認、engine 更新、アプリ installer、複数対象の実行。
- Strata `strata_control/feed.py:312-330` — feed 署名と sequence / channel / 期限の検査入口。
