# `strata runtime verify --if-owner-id`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime verify` |
| オプション | `--if-owner-id OWNER_ID` |
| 別名 | なし |
| 値 | owner ID。32 桁の小文字 16 進文字列 |

## 役割

verify の実行対象が、レビュー時に確認した owner のままであることを照合するための前提条件です。指定した ID と現在の owner が異なると検証を拒否します。これは `--if-instance-id` と組み合わせて使います。plan で ID を確認してから実行すれば、plan 後に owner または instance が入れ替わった状態で検証を進めるのを防げます。

## 使い方

まず ready な instance の ID を plan で表示し、その値を両方の前提条件として指定します。下記の値は形式を示す例です。

```sh
strata runtime verify --profile four-gpu --plan --output json
strata runtime verify --profile four-gpu \
  --if-owner-id 0123456789abcdef0123456789abcdef \
  --if-instance-id fedcba9876543210fedcba9876543210
```

直接 CLI では両 ID を省略して実行することもできます。その場合、plan で確認した owner / instance との一致は要求されません。両 ID は Desktop bridge 経由の `runtime.verify` では必須ですが、この制約は直接 CLI の必須条件ではありません（`strata_control/management.py:255-270,539-544`）。

## 値と既定値

- 値を取る文字列オプションで、parser 上の既定値は未指定（`None`）です。別名はありません（`strata_cli/cli.py:216-225`）。
- 実行時には32文字ちょうどの小文字 `[0-9a-f]` のみ受理されます。大文字、短い値、非16進文字は不正です。parser は型変換をせず、管理処理で検証します（`strata_control/management.py:142-147,235-238`）。
- 値が未指定なら owner の一致条件は追加されません。値を指定したときは `--if-instance-id` も必要で、片方だけの指定は `verify requires both reviewed owner and instance IDs` で拒否されます（`strata_control/management.py:255-263`）。
- `--plan` と ID 前提条件は併用できません。plan 時にいずれかの ID が渡されるとエラーになります。plan では条件を付けずに現在の ID を確認してください（`strata_control/management.py:239-254`）。

## 実行時の動作

CLI は引数を `management.runtime_action()` に渡します。実行時に ID が指定されていれば、まず `runtime.status()` で現在の owner ID と instance ID を照合し、owner が異なる場合は `owner_changed_after_verify_plan`、instance が異なる場合は `instance_changed_after_verify_plan` として終了します。一致後は profile revision、待ち時間、両 ID を含む `runtime.verify` 操作を journal に記録し、owner host へ前提条件を渡します（`strata_cli/cli.py:1345-1356`; `strata_control/management.py:255-270`; `strata_control/journal.py:91-92,376-393`）。

owner host 側でも owner / instance ID を再照合してから verify を進めます。したがって CLI 側の status 確認から host 側の検証開始までに対象 instance が変化した場合も拒否されます（`strata_control/runtime.py:1172-1190`）。

このオプション自体は照合条件を加えるもので、ロードや生成プローブの選択は変えません。verify は API identity と launch attestation を確認し、モデルがロード済みなら1 token の生成を試します。モデルが未ロードの場合、`--load` がなければロードせず `unloaded` 状態で成功し、`--load` があれば固定プローブを API に送ってロード・生成を試します（`strata_control/readiness.py:84-120,121-143`）。

## 適用条件と副作用

- 保存済み profile を対象にする `strata runtime verify` のスコープです。`--profile` は必須です（`strata_cli/cli.py:216-225`; `strata_control/management.py:188-200`）。
- 指定時には owner ID と instance ID の両方が必要です。直接 CLI で両方省略する場合は、現在の owner/instance を plan 値に固定する precondition はありません。Desktop bridge の実行要求では双方の ID が必須です（`strata_control/management.py:255-270,539-544`）。
- ID 条件の一致後、verify は読み取り確認だけに限定されず、API への telemetry 要求を行います。ロード済みモデルでは1 token の生成要求も行い、`--load` を併用すれば未ロードモデルを明示的にロードして生成を試みます。CLI の他の設定や外部状態を変更する指定ではありません（`strata_control/runtime.py:1184-1199`; `strata_control/readiness.py:101-126`）。
- 成否は `runtime.verify` 操作として journal に記録されます。journal の結果要約には ok/state、instance、readiness、エラー等が含まれ、owner ID や生成文はこの要約対象に含まれません（`strata_control/management.py:264-270`; `strata_control/journal.py:402-405`）。
- 任意の API monitor が有効な環境で固定 probe request が捕捉される可能性があることは、利用者向け資料に記載されています（`docs/TERMINAL.md:94`）。

## 出力とエラー

- ID の書式不正、片方だけの ID 指定、plan との併用など、CLI 管理層での入力エラーは `ProfileError`（`ValueError` 系）として CLI のエラー経路へ進みます。human 出力では `strata: <message>` を stderr に出し、JSON 出力では schema version、エラーコード、メッセージを出力します（`strata_control/management.py:142-147,239-241,255-257`; `strata_cli/cli.py:527-532,2166-2173`）。
- owner または instance の不一致はエラー結果となり、host 側では exit code 6 です。runtime が ready でない、ready file と child / instance が一致しない、launch attestation や API identity の検証に失敗する場合も検証は失敗します（`strata_control/management.py:258-263`; `strata_control/runtime.py:1184-1205`）。
- 成功時は human 形式で profile 名、state、instance、API URL、launch verification、readiness を表示します。JSON 形式では結果オブジェクトを出力します。結果の `ok` が false の場合、コマンドは返された exit code（通常の runtime 検証失敗では6）で終了します（`strata_cli/cli.py:1357-1373`）。
- 生成プローブは完了 token が1未満、応答形状が不正、API が期限内に応答しない場合などに失敗し得ます。verify の `--wait` は既定300秒、許容範囲1〜600秒で、owner RPC にはその値に5秒を加えた timeout が渡されます（`strata_cli/cli.py:216-225`; `strata_control/management.py:255-270`; `strata_control/runtime.py:687-699`; `strata_control/readiness.py:121-141`）。

## 根拠

- `strata_cli/cli.py:216-225` — `runtime verify` parser と `--if-owner-id` の値名・help。
- `strata_cli/cli.py:1345-1373` — 値の管理層への受け渡し、plan / human / JSON 出力、終了コード。
- `strata_control/management.py:142-147,235-270` — ID 書式、対になる instance 条件、plan 禁止、status 照合と journal / runtime 呼び出し。
- `strata_control/management.py:537-544` — Desktop bridge では両 ID が必須となる範囲。
- `strata_control/runtime.py:687-699,1172-1208` — host RPC の入力検査、再照合、ready 条件と verify 実行。
- `strata_control/readiness.py:84-143` — API identity、launch attestation、未ロード時の扱い、生成 probe。
- `strata_control/journal.py:91-92,376-405` — direct operation intent と結果要約。
- `docs/TERMINAL.md:63-70,94` — 利用例、`--load`、probe と monitor の説明。
