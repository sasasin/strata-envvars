# `--if-instance-id`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops run` |
| オプション | `--if-instance-id` |
| 別名 | なし |
| 値 | `INSTANCE_ID`。restart plan が示す runtime instance ID |

## 役割

保存済みの `runtime.restart` recipe を実行するとき、確認済み plan の runtime instance ID がまだ現在の instance と一致することを要求します。別の instance に入れ替わった状態で、古い plan に基づく restart を進めないための前提条件です。`--if-owner-id` と必ず一緒に指定します。

## 使い方

まず `strata ops plan restart --profile PROFILE` の出力を確認し、`preflight.current_instance_id` と `preflight.current_owner_id` を実値に置き換えて実行します。

```sh
strata ops run restart --profile PROFILE \
  --if-owner-id OWNER_ID \
  --if-instance-id INSTANCE_ID
```

recipe の revision、profile revision、候補設定の digest も preview 時点に固定したい場合は、plan で確認した値をそれぞれ `--if-revision`、`--if-profile-revision`、`--if-source-sha256` に渡せます。

## 値と既定値

値は必須で、省略時は `None`（条件なし）です。parser は文字列として受け取り、長さや文字種をそこで検証しません（`strata_cli/cli.py:287-288`）。空文字も parser では拒否されません。

restart recipe では `--if-owner-id` と `--if-instance-id` の片方だけを渡すと、実行前に `restart recipe needs both reviewed owner and instance IDs` で失敗します（`strata_control/recipes.py:375-378`）。両方渡した場合、ID は plan の値との完全一致で比較されます。現行 plan に一致しない値（空値や不正な形式を含む）は `instance_changed_after_restart_plan` などの stale 条件として扱われ、終了コード 6 になります（`strata_control/recipes.py:381-388`）。runtime の restart RPC 自体も instance ID を32文字の小文字16進数として検証します（`strata_control/runtime.py:1247-1254`）。

## 実行時の動作

`strata ops run` は受け取った値を `recipes.run` の `expected_instance_id` に渡します（`strata_cli/cli.py:1448-1457`）。対象 recipe が `runtime.restart` の場合、owner ID とのペア指定を確認した後、いずれかの owner / instance / source digest 条件が指定されていれば restart preflight を取得します。preflight が失敗すれば restart は行わず、そのエラーと終了コードを返します。成功時は `current_instance_id` と指定値を比較し、一致しなければ restart を開始しません（`strata_control/recipes.py:375-391`）。

事前照合を通過した場合、instance ID は `runtime.restart` にも引き渡されます（`strata_control/recipes.py:397-412`）。runtime owner は restart 開始時に現在の状態を照合し、候補 plan の作成後にも instance ID を再確認します。どちらかの時点で変わっていれば `instance_changed_after_restart_plan`、終了コード 6 で中止します（`strata_control/runtime.py:1043-1073`）。plan が返す現在の owner ID / instance ID は `strata_control/runtime.py:1148-1157` にあります。

この option 自体は server に ID を設定したり、restart の効果を変えたりしません。一致して restart が進むと、restart recipe 本来の効果として現在の instance の drain と新 instance の起動が行われます。activation に失敗した場合の旧 launch rollback も plan の効果として示されています（`strata_control/recipes.py:332-339`）。

## 適用条件と副作用

- 適用先は `runtime.restart` recipe だけです。他の recipe kind に指定すると `owner, instance and source preconditions require a restart recipe` で拒否されます（`strata_control/recipes.py:392-394`）。
- `--if-owner-id` とのペア指定が必要です。`--if-owner-id` の詳細は [`--if-owner-id`](--if-owner-id.md) を参照してください。
- preflight の ID 不一致は journal の operation record を作る前に検出されます。照合後に restart を開始する段階まで進むと record が開始され、後続失敗も結果として記録されます（`strata_control/recipes.py:381-400`, `429-437`）。
- 一致した場合には recipe の restart が実行されるため、現在の server を drain して新 instance を起動する副作用があります。plan 表示だけでは実行されません（`strata_control/recipes.py:329-339`, `397-412`）。

## 出力とエラー

不一致などの例外は、`--output human` では `strata: <message>` を stderr に出し、該当コードを終了コードとして返します。`--output json` では標準出力へ `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` を出します（`strata_cli/cli.py:527-532`, `2166-2173`）。preflight 後に operation が始まり、restart が失敗結果を返した場合は operation の JSON または整形表示を出して、結果の `exit_code` を返します（`strata_cli/cli.py:1458-1464`）。

確認できた stale ID の失敗コードは 6、runtime RPC に到達した場合の不正な instance ID のコードは 2 です。単独指定の `ProfileError` は明示コードなしで生成されるため、既定のコード 2 になります（`strata_control/recipes.py:377-378`; 既定値の定義は `strata_control/profiles.py` の `ProfileError` を参照）。

## 根拠

- parser 定義と help 文: `strata_cli/cli.py:278-290`
- CLI から recipe 実行への引き渡し、出力と終了コード: `strata_cli/cli.py:1448-1464`
- recipe kind の前提条件、preflight 比較、runtime への引き渡し、journal 記録: `strata_control/recipes.py:329-339`, `363-412`, `429-439`
- restart 前後の instance ID 再確認と stale 時の失敗: `strata_control/runtime.py:1043-1073`
- restart RPC の instance ID 形式検証: `strata_control/runtime.py:1247-1257`
- 現在の ID を plan に含める箇所: `strata_control/runtime.py:1148-1157`

索引と同じ Strata revision の parser・実装を確認しました。release artifact を用いた挙動確認は行っていません。
