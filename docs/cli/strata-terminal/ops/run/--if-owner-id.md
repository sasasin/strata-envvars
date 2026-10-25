# `--if-owner-id`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops run` |
| オプション | `--if-owner-id OWNER_ID` |
| 別名 | なし |
| 値 | runtime restart recipe の計画に表示された owner ID。実行経路では32桁の小文字16進数として照合される |

## 役割

restart recipe の実行前に、計画時に確認した runtime owner が現在も同じであることを要求します。現在の owner が変わっていた場合に、別の owner が管理する server を誤って drain・再起動するのを防ぐための事前条件です。これは `strata ops run` のオプションで、`strata runtime restart` の同名オプションとは別の parser scope です。

## 使い方

まず restart recipe の計画を JSON で表示し、出力の `plan.operation.preflight.current_owner_id` と `plan.operation.preflight.current_instance_id` の値を確認します。実行時には owner ID と instance ID の両方を渡します。

```sh
strata ops plan restart --profile four-gpu --output json
strata ops run restart --profile four-gpu \
  --if-owner-id OWNER_ID_FROM_PLAN \
  --if-instance-id INSTANCE_ID_FROM_PLAN
```

`OWNER_ID_FROM_PLAN` と `INSTANCE_ID_FROM_PLAN` は説明用の置換値です。計画で確認した実値に置き換えてください。

## 値と既定値

オプションは値を1つ取ります。省略時は owner ID の事前条件を検査しません。parser では文字列をそのまま受け取り、`argparse` 段階で形式検証や既定値の補完はしません。

recipe 実行層では `--if-owner-id` と `--if-instance-id` の片方だけを指定すると拒否されます。owner、instance、source SHA-256 のいずれかを指定した場合は restart 計画を取得して照合します。runtime restart の実行層では owner ID と instance ID はそれぞれ32桁の小文字16進数でなければなりません。

## 実行時の動作

`strata ops run` は保存済み recipe を読み、revision 等の先行確認後に `recipes.run` へ値を渡します。recipe が `runtime.restart` の場合、owner ID を指定すると `runtime.plan_restart` の `current_owner_id` と一致するかを実行前に比較します。一致しない場合は `owner_changed_after_restart_plan` で終了します。owner ID はこのときだけ有効で、別種の recipe に owner・instance・source のいずれかの事前条件を渡すと「restart recipe が必要」として拒否されます。`--if-instance-id` と `--if-source-sha256` は関連する別の事前条件です。

照合に通ると recipe の operation record を作成し、owner ID と対応する instance ID を runtime restart 呼び出しへ渡します。runtime host は再起動処理の開始時に現在の owner ID と instance ID を再確認し、owner が異なる場合は drain より前に失敗を返します。計画時の値を渡さない場合、これらの ID による照合は行われません。

## 適用条件と副作用

このオプション自体は runtime restart recipe の owner 照合にのみ適用されます。restart recipe の実行が続行されれば、通常の restart 動作として現行 instance の drain と新 instance の起動が試みられます。owner 照合は操作対象の同一性を固定する条件であり、restart の実行を読み取り専用にはしません。

recipe-level の事前照合で不一致や無効な組み合わせとなった場合は、operation record 作成前に拒否されます。runtime host で再確認中に owner が変わった場合は restart の結果が失敗となり、CLI は返された operation record を出力します。先行照合後の race に対しては host 側の再確認が働きます。

## 出力とエラー

- owner が計画後に変わっていた場合、recipe 層は `owner_changed_after_restart_plan`、終了コード `6` で失敗させます。これは operation record を開始する前のエラーで、通常出力では `strata: ...` を stderr に出し、`--output json` ではエラー JSON を stdout に出します。
- owner ID と instance ID の片方だけを指定した場合は、両方が必要という検証エラーになります。owner 条件を非 restart recipe に指定した場合も拒否されます。
- host 側の再確認で owner が変わった場合は、restart 結果に `owner_changed_after_restart_plan` と終了コード `6` が記録されます。CLI は成功時・失敗時とも run 結果を出力し、結果の終了コードを返します。
- 成功した `ops run` は run journal に recipe/profile revision、intent、開始・終了イベントおよび結果を保存します。owner 条件の事前照合で拒否された場合は、この run の記録は作られません。

## 根拠

- Strata `strata_cli/cli.py:255-267,278-290` — `ops` 階層と `run` parser。`--if-owner-id` に metavar 以外の型・既定値指定はなく、restart recipe plan の owner を要求する説明がある。
- Strata `strata_cli/cli.py:1448-1464` — recipe の読込、オプション値の `recipes.run` への受け渡し、結果出力と終了コード。
- Strata `strata_control/recipes.py:363-394` — recipe/profile revision の先行照合、owner/instance の併用条件、restart recipe 限定、plan 時の owner 一致確認。
- Strata `strata_control/recipes.py:397-412,429-438` — run journal の開始、owner と instance の runtime restart への転送、成功・失敗結果の記録。
- Strata `strata_control/runtime.py:702-731` — restart API の owner/instance ID 形式検証と RPC パラメータへの転送。
- Strata `strata_control/runtime.py:1043-1073` — runtime host の owner/instance 再確認と、restart による drain より前の失敗経路。
- Strata `strata_control/runtime.py:1132-1164` — restart plan が `current_owner_id` と `current_instance_id` を返し、plan 自体は drain/start を行わないこと。
- Strata `strata_cli/cli.py:527-532,2166-2173` — `ProfileError`（`ValueError` 派生）の人間向け stderr / JSON エラー出力と終了コード。
- Strata `strata_control/profiles.py:30-35` — `ProfileError` が `ValueError` を継承し、終了コードを保持する定義。
- Strata `docs/TERMINAL.md:105-120` — ops の利用例、plan/run の説明、operation record に関する利用者向け記述。
