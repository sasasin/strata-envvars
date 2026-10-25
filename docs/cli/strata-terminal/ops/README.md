# `strata ops`（Strata Terminal CLI）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の checkout は `main`（`origin/main` と一致）で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/recipes.py`、`strata_control/journal.py` |

## 役割

保存済み serving profile に紐づく、型付きのローカル operator recipe を初期化・作成・編集・確認し、明示的に実行するコマンドです。recipe は任意の shell コマンドではなく、Strata が許可した操作種別と型付きパラメーターから成ります。トップレベル parser はサブコマンドを必須にし、`init`、`list`、`create`、`show`、`edit`、`set`、`history`、`rollback`、`plan`、`run`、`runs`、`result` を登録します（`strata_cli/cli.py:255-265`、recipe の種別は `strata_control/recipes.py:28`）。

## 代表的な使い方

```sh
# profile に既定の3 recipe を用意して一覧を確認
strata ops init --profile four-gpu
strata ops list --profile four-gpu

# 実行予定を確認してから、revision 条件を付けて再起動 recipe を実行
strata ops plan restart --profile four-gpu --output json
strata ops run restart --profile four-gpu --if-revision RECIPE_REVISION --if-profile-revision PROFILE_REVISION

# コンポーネント検査 recipe の設定を変え、計画・実行
strata ops set check --profile four-gpu live=true --plan
strata ops set check --profile four-gpu live=true
strata ops plan check --profile four-gpu --output json
strata ops run check --profile four-gpu --output json

# 実行記録を一覧・取得
strata ops runs --profile four-gpu --limit 20 --output json
strata ops result OPERATION_ID --profile four-gpu --output json
```

recipe の編集は `set NAME KEY=VALUE`（`--plan` で保存案のみ確認）または `edit NAME`（`VISUAL` / `EDITOR` に設定したエディター）で行います。新規作成では `--kind` に `runtime.restart`、`engine.calibrate.measure`、`components.verify` のいずれかを指定します（parser: `strata_cli/cli.py:258-290`、型・値の検証: `strata_control/recipes.py:93-127,278-326`）。

## 実行モードと動作

| 操作 | 主な動作 |
| --- | --- |
| 準備・参照 | `init` は `restart`、`calibrate`、`check` の recipe を不足分だけ初期化します。`list`、`show`、`history`、`runs`、`result` は recipe または記録を読み出します。 |
| 編集 | `create` は型付き recipe を新規作成し、`set` / `edit` / `rollback` は revision 管理付きで保存します。`edit` の失敗 draft は修復用に残る場合があります。 |
| 計画 | `plan` は recipe 種別に応じた preflight を行い、実行効果を表示しますが、`would_execute: false` です。components の `live=true` では計画時にも GPU inventory を問い合わせます。 |
| 実行 | `run` は recipe の種類に応じて profile restart、engine calibration measurement、または components inspection を呼び出します。受理された実行は profile ごとのローカル operation journal に記録します。 |

既定の recipe は `restart`（`runtime.restart`、`startup_wait_s=300`）、`calibrate`（`engine.calibrate.measure`、profile ディレクトリ配下の `.reports`）、`check`（`components.verify`）です。初期化は既存 recipe を上書きせず、既存名の kind が期待値と異なる場合は失敗します（`strata_control/recipes.py:117-127,153-177`）。

recipe の主な副作用は種別で異なります。restart は現行 instance を drain して新 instance を起動し、activation に失敗した場合は以前の launch に戻す動作を計画に示します。calibration measurement は engine を起動して decode sweep を行い、新しい report ファイルを書きます。結果は別途 review してから適用する必要があります。components verification は保存済み profile の component を読み取り、`live=true` の場合はホスト GPU 情報も照会します（`strata_control/recipes.py:329-360,395-428`）。

## 注意点

- `--profile` は全サブコマンドで必須です。`--output` は `human`（既定）または `json`。`runs --limit` は既定 20、受理範囲は 1〜100 です（`strata_cli/cli.py:262-290`、`strata_control/journal.py:254-256`）。
- recipe は profile ごとのローカル領域に保存され、recipe ファイルは 64 KiB 以下の通常ファイル、POSIX では owner-only mode 0600、recipe directory は owner-only mode 0700 を要求します（`strata_control/recipes.py:38-64,180-196`）。
- recipe revision / profile revision や restart recipe の owner・instance・source digest を `--if-*` 条件で固定できます。確認した値と異なる場合は実行前に失敗します。`--exclusive` は校正計測 recipe のみで有効で、毎回指定が必要です（`strata_cli/cli.py:278-290`、`strata_control/recipes.py:369-396`）。
- operation journal は profile ごとに最大 500 件を保持し、上限時は古い完了済み記録から整理します。未完了記録だけで上限に達している場合は新規 action を拒否します。呼び出し元が中断した記録は `completion_unverified` と表示されることがあり、operation が継続中か安全に停止したかをそれだけで判定できません（`strata_control/journal.py:25,247-273,276-293`）。
- 不正な kind / parameter、欠落・不正な recipe、競合 revision、preflight 不成立などでは失敗します。`_ops` は操作結果を human または JSON で出し、実行結果の `ok=false` では operation が返す終了コード（既定 5）を返します。共通 CLI handler は `ValueError` / `OSError` 等をエラー出力に変換します（`strata_cli/cli.py:1391-1464,2166-2193`）。

## 関連文書

- [CLI オプション索引](../../README.md) — `ops` と各サブコマンドの option スコープ。
- [Engine calibration のコマンド概要](../engine/README.md) — calibration recipe が呼び出す engine 計測の関連コマンド。
- [Components のコマンド概要](../components/README.md) — components verification recipe の関連コマンド。

## 調査範囲

checkout の parser、recipe 実装、journal 実装および Strata checkout の `docs/TERMINAL.md:96-122` の説明を確認しました。Release 配布物や Windows ACL の挙動はこのコマンド概要の調査では実機確認していません。上記の挙動説明は記載した commit のソースに基づきます。

## 根拠

- `strata_cli/cli.py:255-290` — `ops` と各サブコマンド、必須 `--profile`、出力形式、各 parser option。
- `strata_cli/cli.py:1391-1464,2160-2163,2166-2193` — command dispatch、各操作の呼び出し、出力・終了コード、共通エラー処理。
- `strata_control/recipes.py:28-29,93-127,130-177` — 対応 kind、recipe validation、既定値、新規作成・初期化。
- `strata_control/recipes.py:180-237,240-326` — 読み込み、一覧、revision 保存・履歴・rollback、typed assignment と editor。
- `strata_control/recipes.py:329-360,363-439` — plan の実行効果、precondition、run の分岐と journal 記録。
- `strata_control/journal.py:25,247-293` — operation record の読み出し、一覧上限、保持上限と整理。
- `docs/TERMINAL.md:96-122` — 利用者向け利用例、calibration recipe の注意、journal の説明。
