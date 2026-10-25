# `--allow-source-migration`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime restart` |
| オプション | `--allow-source-migration` |
| 別名 | なし |
| 値 | 値を取らない真偽値フラグ。指定すると有効 |

## 役割

稼働中の managed runtime が読んだ run config と同じファイルが編集されている場合に、その編集後の設定で再起動することを許可します。再起動に失敗したとき旧設定で戻せるよう、停止前にホストが旧 run config の起動時バイト列を runtime の private ディレクトリに snapshot として保存します。フラグ単独で profile を変更したり、異なる config ファイルへの切替を許可したりするものではありません。

## 使い方

まず plan で候補の SHA-256 と profile revision を確認し、その値を付けて実行します。以下の例は、稼働中 profile の run config を同じパスのまま編集した場合です。

```sh
strata runtime restart --profile four-gpu --allow-source-migration --plan --output json
strata runtime restart --profile four-gpu --allow-source-migration \
  --if-profile-revision PROFILE_REVISION \
  --if-source-sha256 CANDIDATE_SOURCE_SHA256
```

2 回目のコマンドには plan が返した候補 digest を指定してください。`--if-profile-revision` は plan の候補 revision を固定する追加の実行前提条件です。

## 値と既定値

- Parser は `action="store_true"` を使うため、未指定時は `False`、指定時は `True` です。値引数や短縮別名はありません（`strata_cli/cli.py:238-254`）。
- 実行時にこのフラグ、または `--allow-source-switch` を指定した場合、候補 source の SHA-256 を `--if-source-sha256` で渡す必要があります。指定がなければ restart 前提条件の検証で拒否されます（`strata_control/management.py:292-310`、`strata_control/runtime.py:707-720`）。digest は小文字 16 進数 64 文字でなければなりません（`strata_control/runtime.py:712-714`）。
- `--plan` は候補 digest を表示する確認操作で、実行用の `--if-source-sha256` 等の前提条件を同時指定できません。plan 自体にも `--allow-source-migration` を付けると、snapshot が必要な候補として比較されます（`strata_control/management.py:299-304`、`strata_control/runtime.py:1132-1164`）。

## 実行時の動作

ホストは候補 profile の source path と内容を読み、稼働時の source path・バイト列と比較します。同一 path の内容が変わっていれば migration と判定し、このフラグがなければ `source_config_changed_restart_requires_migration` で再起動を止めます（`strata_control/runtime.py:793-800,1056-1066`）。

フラグを付けて再起動すると、実行前に候補ファイルの SHA-256 と profile revision を確認し、候補 source が plan 後に変わっていれば drain 前に `source_changed_after_preview` で拒否します。さらに、drain 中にも候補ファイルのバイト列を再確認し、変化があれば新しい instance の起動に進みません（`strata_control/runtime.py:1064-1092`）。

migration が必要な場合、ホストは稼働開始時の旧 config バイト列を `<profile>-<owner token>-<UUID>.rollback.json` という新規ファイルに mode `0600` で保存します。候補の有効化に成功した場合は不要になった snapshot を削除し、削除できなければ `rollback_snapshot_cleanup_pending` を返します（`strata_control/runtime.py:813-819,1093-1102`）。有効化に失敗した場合、snapshot の旧 config で旧起動引数を使って再起動を試みます。復旧できれば失敗結果に `rolled_back: true` と `rollback_source_config` を含めます。復旧もできなければ `state: failed`、`rolled_back: false` となります（`strata_control/runtime.py:1103-1130`）。snapshot の作成に失敗した場合は drain 前に `rollback_snapshot_failed` で終了します（同 `1074-1084`）。

## 適用条件と副作用

- このオプションは `strata runtime restart` のみに登録されています。`--plan` では source migration の必要性を確認するためにも使えます（`strata_cli/cli.py:238-254`）。
- 同じ source file の編集を許可するフラグです。保存 profile が別 path の source file を指す変更には別途 `--allow-source-switch` が必要です。旧 source も編集済みの状態で異なるファイルへ切り替える場合は両フラグが必要です。source switch では旧・新ファイルが通常ファイルかつ異なる inode であることも求められます（`strata_control/runtime.py:793-811`）。
- snapshot は operator が編集した候補ファイルを上書きせず、runtime の private ディレクトリに別ファイルとして保存されます（`strata_control/runtime.py:813-819`）。runtime ディレクトリは既定でユーザー状態ディレクトリ下の `strata/runtime`、または `STRATA_RUNTIME_DIR` で指定される絶対パスです（同 `101-112`）。
- CLI の再起動結果は operation journal に記録され、フラグと候補 digest も実行 intent に含まれます（`strata_control/management.py:317-333`、`strata_control/journal.py:136-157`）。

## 出力とエラー

- `--output json` では結果オブジェクトを JSON で stdout に出力します。通常の human 出力では `<profile>: <state>` にエラー文字列等を添えて stdout に出力します。失敗時のエンジンログ案内が取得できる場合は stderr に出力されます（`strata_cli/cli.py:1359-1373`）。
- 無効な digest、source change 時の digest 不足などの引数・前提条件エラーは、通常 `ProfileError` の終了コード（既定 2）で返されます。profile preflight の失敗は exit code 5、runtime が ready でない、source/revision/digest の不一致、snapshot 失敗、restart/rollback の失敗は実装された結果では exit code 6 です（`strata_control/management.py:305-310`、`strata_control/runtime.py:1054-1068,1077-1084,1123-1130`）。

## 根拠

- `strata_cli/cli.py:238-254` — `restart` parser、フラグの型・既定動作・説明。
- `strata_cli/cli.py:1345-1356` — parser の値を `management.runtime_action` に渡す箇所。
- `strata_control/management.py:292-333` — boolean/digest/revision 検証、plan と実行の分岐、journal 記録および runtime への転送。
- `strata_control/runtime.py:793-828` — source change の判定、mode `0600` snapshot の作成と削除。
- `strata_control/runtime.py:1043-1130` — restart 前提条件、digest 検証、drain・再起動・rollback と失敗結果。
- `strata_control/runtime.py:1132-1164` — plan が示す source switch/migration、候補 digest、snapshot の要否。
- `strata_control/runtime.py:101-112,384-399` — runtime ディレクトリと新規 private file の作成。
- `strata_cli/cli.py:1359-1373` — human/JSON の結果出力、終了コードおよび失敗時ログ案内。
