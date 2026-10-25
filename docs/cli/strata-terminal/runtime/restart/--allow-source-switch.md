# `--allow-source-switch`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime restart` |
| オプション | `--allow-source-switch` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。指定時 `True`、省略時 `False`。 |

## 役割

保存済み profile が参照する run config のファイルを、現在稼働中の instance が起動時に読んだファイルとは別のファイルへ切り替えて restart することを明示的に許可します。通常の別ファイル切替では、旧ファイルが稼働時の内容のまま rollback に使えることが条件です。parser は `runtime restart` にだけこの引数を登録しています（`strata_cli/cli.py:238-244`）。

## 利用例

まず plan で候補の source digest を確認し、その digest を実行時に渡します。

```sh
strata runtime restart --profile four-gpu --allow-source-switch --plan --output json
strata runtime restart --profile four-gpu --allow-source-switch \
  --if-profile-revision NEW_PROFILE_REVISION \
  --if-source-sha256 CANDIDATE_SOURCE_SHA256
```

別 config の選択は、先に `strata profile use-config` などで保存済み profile に反映しておく必要があります。`--plan` は候補 profile と稼働中 launch を比較し、drain/start は行わず、候補の SHA-256 などを返します（`strata_control/runtime.py:1132-1164`）。

## 値と既定値

値は取りません。`argparse` の `store_true` で、指定しない場合は `False`、指定した場合は `True` です（`strata_cli/cli.py:241-242`）。値を付けて `--allow-source-switch true` のように渡す形式ではありません。

## 実行時の動作

CLI はフラグを `management.runtime_action()` に渡します。同関数は plan 実行時には `runtime.plan_restart()`、通常実行時には `runtime.restart()` へ転送し、journal にも `allow_source_switch` の値を含む intent を記録します（`strata_cli/cli.py:1345-1356`; `strata_control/management.py:292-304,317-333`）。

restart の候補 source が現在の source path と異なるとき、このフラグが省略されていれば `source_switch_requires_opt_in` で拒否します。指定されていても、旧・新 source の両方が通常ファイルで、かつ同じ inode ではないことが必要です。条件を満たさない場合は `source_switch_requires_distinct_regular_files`、旧 source を読めない場合は `rollback_source_unavailable` になります（`strata_control/runtime.py:793-811`）。

有効な切替では、candidate source の内容を plan と照合します。フラグまたは `--allow-source-migration` を指定した実行では `--if-source-sha256` が必須で、実行直前に source bytes の SHA-256 が一致しなければ restart 前の状態を保って拒否します（`strata_control/management.py:295-310`; `strata_control/runtime.py:712-724,1057-1068`）。profile revision の固定には `--if-profile-revision`、稼働 instance の固定には plan で得た owner ID と instance ID の両方を渡せます（`strata_control/management.py:296-316`; `strata_control/runtime.py:1049-1073`）。

## 適用条件と副作用

- `--allow-source-switch` は別ファイルへの切替を許可しますが、同じファイルを編集した場合の migration 許可にはなりません。同じ path の bytes が稼働時と異なる場合は `--allow-source-migration` が必要です。また別 path でも旧ファイルの bytes が稼働時から変わっていれば、rollback 用 snapshot を作るため両方のフラグが必要です（`strata_control/runtime.py:797-811`）。
- migration が必要な場合、drain 前に稼働時の config bytes を owner の private runtime directory に新規 snapshot として保存し、rollback launch の `--config` を snapshot に差し替えます。元の編集ファイルは上書きしません（`strata_control/runtime.py:813-818,1074-1084`）。
- 実行では現在の子 server を停止（drain）して候補 launch を開始します。候補起動が ready になれば成功し、不要な snapshot を削除します。候補ファイルは drain 中にも再読込・照合され、plan 後の変更は候補 launch を拒否します（`strata_control/runtime.py:1085-1102`）。
- 候補起動に失敗すると、旧 launch を元の bytes で再起動して rollback を試みます。migration 時は snapshot を使います。rollback 成功時は `rolled_back: true` と `rollback_source_config` を返し、snapshot の削除が失敗した場合は cleanup pending を示します。旧 bytes を使えない、または rollback 自体が失敗すれば `state: failed`、`rolled_back: false` になります（`strata_control/runtime.py:1103-1130`）。

## 出力とエラー

省略時の既定動作で別 source への切替を試みると `source_switch_requires_opt_in`、SHA-256 の指定漏れは実行前 validation error になります。digest の不一致は `source_changed_after_preview`、profile revision の不一致は `profile_changed_after_preview` として restart 前に拒否されます（`strata_control/management.py:299-310`; `strata_control/runtime.py:1060-1068`）。

runtime の結果は human 出力または `--output json` / `--json` で出力されます。restart 失敗時は結果の `exit_code`（通常の restart 失敗は 6）を返し、human 出力ではエラーに加えて取得できる場合に engine log の案内を stderr に出します（`strata_cli/cli.py:508-515,1359-1373`）。

## 根拠と調査範囲

- parser と CLI scope: `strata_cli/cli.py:238-254,508-515`
- option の転送と execution precondition: `strata_cli/cli.py:1345-1356`; `strata_control/management.py:292-333`
- source 判定・snapshot・restart / rollback: `strata_control/runtime.py:787-818,1043-1164`
- journal intent の boolean/digest validation: `strata_control/journal.py:145-160`
- 利用者向け手順との照合: `docs/TERMINAL.md:78-94`

対象 checkout の parser と実装を確認しました。CLI help や Release artifact は別途照合していません。OS ごとの owner transport の詳細はこのオプション固有の実装差としては確認していないため、ここでは共通の restart 処理に限定しています。
