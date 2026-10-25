# `--if-owner-id`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime restart` |
| オプション | `--if-owner-id OWNER_ID` |
| 別名 | なし |
| 値 | owner ID。32文字の小文字16進数（`[0-9a-f]{32}`） |

## 役割

`--plan` で確認した稼働中 runtime の owner が、実行時にも同じであることを要求する条件指定です。確認後に別の owner の runtime へ入れ替わっていた場合、誤った instance を再起動せずに失敗します。単独では指定できず、同じ計画に表示された `--if-instance-id` も必要です。

## 使い方

まず現在の状態と restart 候補を JSON で確認し、表示された `current_owner_id` と `current_instance_id` を実行条件として渡します。

```sh
strata runtime restart --profile my-profile --plan --output json
strata runtime restart --profile my-profile \
  --if-owner-id 0123456789abcdef0123456789abcdef \
  --if-instance-id fedcba9876543210fedcba9876543210
```

2行目の ID は形式を示す例です。実際には直前の計画出力の値を使用してください。restart の `--plan` は `current_owner_id` と `current_instance_id` を返します（`strata_control/runtime.py:1132-1164`）。このオプションを `--plan` と同時に指定すると、計画用の呼び出しには実行前提条件を含められないためエラーになります（`strata_control/management.py:299-304`）。

## 値と既定値

値は必須です。parser は `OWNER_ID` を受け取り、値自体の形式検証は runtime 管理層で行います。受理される値は32文字の小文字16進数です。大文字、桁数違い、空文字などは無効です（`strata_cli/cli.py:238-253`、`strata_control/management.py:142-147`）。

省略時の値は `None` で、owner の一致条件は適用されません。ただし `strata runtime restart` では owner ID と instance ID の片方だけを指定できません。`--if-owner-id` を付ける場合は `--if-instance-id` も必要です（`strata_control/management.py:297-308`）。重複指定の特別な処理は Strata 側に定義されていません。

## 実行時の動作

CLI は値を `management.runtime_action()` の `if_owner_id` に渡します（`strata_cli/cli.py:1345-1356`）。管理層は形式を検証し、plan でない restart では `runtime.status(profile)` が返す現在の owner ID と指定値を比較します。異なる場合は `owner_changed_after_restart_plan`、終了コード6で失敗します。同じ値の場合、owner ID と instance ID の両方を journal に記録する restart 操作へ渡し、runtime host へ転送します（`strata_control/management.py:292-333`、`strata_control/runtime.py:702-731`）。

host 側でも drain の前に現在の status を取得して owner ID を照合します。差し替わっていれば `owner_changed_after_restart_plan`、終了コード6を返し、ready 状態であることの確認、候補 profile の準備、停止・再起動処理には進みません（`strata_control/runtime.py:1043-1059`）。owner ID は host の起動時にランダムな UUID から作られ、status に含めて返されます（`strata_control/runtime.py:743-756,933-938`）。

## 適用条件と副作用

この条件は `strata runtime restart` の実行時に限り、計画確認後も同じ owner が管理する runtime であることを確認します。ID の一致自体は再起動を抑止せず、他の preflight 条件も通れば通常どおり旧 instance を drain し、新しい設定で起動します。再起動中に起動が失敗した場合は旧設定での rollback を試みます（`strata_control/runtime.py:1049-1073,1085-1130`）。

この値は owner の同一性を照合するための確認値で、認証資格情報として使われる処理は確認できません。owner 条件を省略した場合はこの同一性照合がなくなります。`--if-instance-id` との組み合わせや profile revision・source digest の条件はそれぞれ別に検証されます。

## 出力とエラー

無効な ID 形式、`--if-instance-id` の欠落、または `--plan` との併用は `ProfileError` となり、通常出力では `strata: <message>` を stderr に出して終了コード2になります。JSON 出力では `{"schema_version":1,"ok":false,"error":{"code":2,"message":"..."}}` 形式です（`strata_control/management.py:142-147,299-308`、`strata_control/profiles.py:30-35`、`strata_cli/cli.py:527-532,2166-2173`）。

計画後に owner が変わった場合は `owner_changed_after_restart_plan` で終了コード6です。CLI は失敗結果を human 表示なら標準出力に profile/state/error を表示し、restart 失敗時は取得できる engine log の場所と末尾も stderr に案内します。JSON 表示では結果オブジェクトを標準出力に出します（`strata_control/management.py:311-316`、`strata_control/runtime.py:1049-1053`、`strata_cli/cli.py:1357-1373,1376-1388`）。

## 根拠

- `strata_cli/cli.py:238-253` — `runtime restart` parser におけるオプション定義と help 文。
- `strata_cli/cli.py:1345-1356` — runtime 管理関数への引き渡し。
- `strata_control/management.py:142-147,292-333` — ID 形式、plan 制約、必須の instance 条件、owner 比較と runtime への転送。
- `strata_control/runtime.py:702-731` — runtime restart の RPC パラメーター構築。
- `strata_control/runtime.py:743-756,933-938` — owner ID の生成と runtime status への掲載。
- `strata_control/runtime.py:1043-1059` — host 側の owner 照合と restart 前段の失敗経路。
- `strata_control/runtime.py:1132-1164` — `--plan` の `current_owner_id` / `current_instance_id` 出力。
- `strata_cli/cli.py:527-532,1357-1373,2166-2173`、`strata_control/profiles.py:30-35` — エラー出力と終了コード。
