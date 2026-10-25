# `--if-source-sha256`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops run` |
| オプション | `--if-source-sha256 SHA256` |
| 別名 | なし |
| 値 | restart recipe の plan に表示された候補 run-config の SHA-256。小文字16進64文字 |

## 役割

`runtime.restart` recipe を実行する際、レビュー後に候補 run-config の内容が変わっていないことを要求します。`strata ops plan` が出す `operation.preflight.candidate_source_sha256` を指定します。これにより、plan と実行の間に候補設定ファイルのバイト列が変わった場合、現在の稼働 instance を drain する前に実行を拒否します。

## 使い方

まず recipe の plan を確認し、その `candidate_source_sha256` を指定して実行します（`<SHA256_FROM_PLAN>` は plan の値に置き換えます）。

```sh
strata ops plan restart --profile PROFILE
strata ops run restart --profile PROFILE --if-source-sha256 <SHA256_FROM_PLAN>
```

recipe 名 `restart` は例です。`strata ops plan` と `strata ops run` は recipe 名を位置引数に取り、`--profile` は必須です。Parser ではこのオプションを `run` action にだけ登録しています。`ops plan` 側の候補 digest は `runtime.plan_restart()` の preflight から返されます。

## 値と既定値

- Parser は `SHA256` metavar を表示しますが、`type=` や `choices=` を指定していません。引数としては一つの文字列を受け取ります（`strata_cli/cli.py:278-290`）。
- 省略時の既定値は `None` で、source digest の事前条件は実施されません。
- restart 実行時に比較する候補 digest は、小文字16進64文字の SHA-256 表記です。plan が候補 source の読み込んだバイト列を `hashlib.sha256(...).hexdigest()` で計算します（`strata_control/runtime.py:1132-1164`）。
- CLI parser は形式を検証しません。値が plan の digest と一致しなければ、recipe 層で `source_changed_after_preview` として終了コード6で拒否します（`strata_control/recipes.py:375-391`）。一致する値は plan が生成した64文字の小文字16進 digest なので、その後の runtime 側の形式条件も満たします（`strata_control/runtime.py:712-714`）。

## 実行時の動作

1. `strata ops run` は recipe を読み、`runtime.restart` の場合、このオプションが指定されていると `runtime.plan_restart(profile)` で再度 preflight を行います。preflight が失敗した場合は、そのエラーと終了コードで停止します。候補 digest が指定値と異なる場合は `source_changed_after_preview`（終了コード6）で停止します（`strata_control/recipes.py:363-394`）。
2. 事前確認を通ると、recipe の実行を operation journal に記録してから `runtime.restart()` に期待 digest を渡します（`strata_control/recipes.py:397-412`）。runtime は restart 時にも新しい plan と source bytes を読み直し、digest を再比較します。不一致なら `source_changed_after_preview` を返し、停止・再起動処理には進みません（`strata_control/runtime.py:1043-1068`）。
3. 期待値を省略した場合、source digest の比較は行いません。また、この recipe 経路は `runtime.plan_restart(profile)` と `runtime.restart()` を source switch / migration の許可なしで呼びます。そのため source ファイルの切替や内容変更は preflight で拒否され、この digest の指定だけでは許可されません（`strata_control/recipes.py:329-339, 375-412`; `strata_control/runtime.py:793-811`）。
4. この値はレシピ設定を変更せず、CLI からの実行時 precondition として渡されます。restart が実行に進めば、現在の instance の停止と新 instance の起動が行われ、起動失敗時には旧 launch への rollback 経路があります（plan の副作用説明は `strata_control/recipes.py:329-339`、restart の停止前 digest 確認は `strata_control/runtime.py:1060-1088`）。

## 適用条件と副作用

- 適用対象は `kind == "runtime.restart"` の recipe です。owner ID、instance ID、source digest のいずれかを restart 以外の recipe で指定すると `owner, instance and source preconditions require a restart recipe` で拒否されます（`strata_control/recipes.py:375-394`）。
- source digest の preflight には稼働 runtime が `ready` であることと、新しい profile から候補 launch/source を作成・読み出せることが必要です。未 ready なら `runtime_not_ready`、candidate preflight に失敗すれば `new_profile_preflight_failed` になります（`strata_control/runtime.py:1132-1147`）。
- digest は候補設定ファイルの内容を識別します。パスや profile revision、owner/instance の同一性を単独で保証する値ではありません。recipe revision や profile revision、owner/instance の確認が必要なら、それぞれ `--if-revision`、`--if-profile-revision`、`--if-owner-id` と `--if-instance-id` も使用します（`strata_cli/cli.py:281-290`; `strata_control/recipes.py:369-394`）。
- 値が省略されても、コマンド自体を実行すれば restart の通常の副作用が発生し得ます。このオプションは restart を plan-only にするものではありません。plan は別コマンドです（`strata_cli/cli.py:1391-1464`）。

## 出力とエラー

- 成功時は human 出力なら operation JSON、`--output json` なら `schema_version`、`ok`、`operation` を含む JSON を stdout に出します。operation の結果が成功なら終了コード0、失敗なら結果の `exit_code`（未指定時5）です（`strata_cli/cli.py:1448-1464`）。
- 値不一致は recipe の実行前 preflight でエラーとなり、CLI の通常モードでは `strata: ...` を stderr に出して終了コード6、`--output json` ではエラー JSON を stdout に出します（`strata_cli/cli.py:527-532`; `strata_cli/cli.py:2166-2188`）。
- 最初の preflight の後、journal 記録後に再確認で失敗した場合は operation が失敗として journal に記録されます（`strata_control/recipes.py:397-438`）。この場合、restart 実装では source digest 比較を drain より前に行います（`strata_control/runtime.py:1060-1088`）。

## 根拠

- `strata_cli/cli.py:255-290` — `ops` parser と `run` action 専用のオプション定義。
- `strata_cli/cli.py:1391-1464` — ops dispatch、引数の受け渡し、実行結果と終了コードの出力。
- `strata_control/recipes.py:329-360` — restart recipe plan と preflight の結果。
- `strata_control/recipes.py:363-438` — 指定 digest の事前比較、restart 以外での拒否、runtime への転送、operation journal。
- `strata_control/runtime.py:1043-1088` — restart 実行時の digest 再確認と drain より前の失敗経路。
- `strata_control/runtime.py:1132-1164` — plan の readiness/source preflight と候補 SHA-256 の生成。
- `strata_control/runtime.py:712-740` — runtime restart の SHA-256 形式条件、source 変更 opt-in との関係。
