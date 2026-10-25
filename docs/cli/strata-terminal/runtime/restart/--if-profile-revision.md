# `--if-profile-revision`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime restart` |
| オプション | `--if-profile-revision REVISION` |
| 別名 | なし |
| 値 | 保存済み profile の revision。小文字16桁の16進数 |

## 役割

再起動計画を確認した後に profile が変わっていないことを条件に、稼働中の owned runtime を再起動します。値には `strata runtime restart --plan` の `candidate_profile_revision` を指定します。

## 使い方

まず JSON で計画を表示し、その結果の `candidate_profile_revision` を次の実行に渡します。restart の人間向け表示は計画フィールドを出さないため、revision の確認には `--output json` を使います（`strata_cli/cli.py:254,1357-1369`）。

```sh
strata runtime restart --profile PROFILE --plan --output json
strata runtime restart --profile PROFILE --if-profile-revision REVISION_FROM_PLAN
```

`PROFILE` と `REVISION_FROM_PLAN` は実環境の profile 名と計画出力の値に置き換えてください。`--plan` と `--if-profile-revision` は同じ呼び出しでは併用できません。

## 値と既定値

- `REVISION` は必須の値です。CLI parser は `metavar="REVISION"` で受け取り、parser 上の既定値はありません（`strata_cli/cli.py:238-254`）。
- 指定値は小文字16桁の16進数でなければなりません。長さや文字種が合わない場合はエラーになります（`strata_control/management.py:134-139,292-298`）。
- revision は profile ファイルの生バイト列に対する SHA-256 の先頭16桁です。JSON の意味内容が同じでもファイルのバイト列が変われば revision が変わり得ます（`strata_control/profiles.py:58-63,150-166`）。
- 省略時、実行開始時に読み込んだ現在の profile revision が内部的な期待値として使われます。したがって明示指定は、先に確認した計画の revision と一致することを要求するための条件です（`strata_control/management.py:317-328`）。

## 実行時の動作

CLI は値を `runtime_action()` に渡します。restart 実行時、管理層は値を検証し、未指定ならその時点で読み込んだ profile revision を期待値にします。その値を operation journal に記録し、runtime owner へ restart 要求として渡します（`strata_cli/cli.py:238-254,1345-1356`; `strata_control/management.py:292-333`）。

owner は新しい profile の起動計画を作り、計画の `profile_revision` が期待値と異なれば `profile_changed_after_preview`（終了コード6）を返します。この比較は既存 engine の停止より前に行われます。revision が一致し、ほかの事前条件も通れば既存 child を停止して新しい設定を起動し、起動確認を行います。失敗時には旧設定への rollback を試みます（`strata_control/runtime.py:1043-1093,1103-1130`）。

## 適用条件と副作用

- `--profile` で指定する保存済み profile に対する `runtime restart` に適用されます。restart は runtime owner が `ready` の場合だけ進みます（`strata_cli/cli.py:238-239`; `strata_control/runtime.py:1049-1059`）。
- `--plan` は実行 precondition と併用できず、併用すると `restart plan cannot include execution preconditions` で拒否されます。計画に出た candidate revision を使う場合は、計画表示と restart 実行を別々に行います（`strata_control/management.py:299-304`）。
- source 設定の切り替えまたは編集を許す `--allow-source-switch` / `--allow-source-migration` を使う場合は、別途 `--if-source-sha256` も必要です。この revision option は source の内容ハッシュや owner / instance ID の確認を代替しません（`strata_control/management.py:307-310`; `strata_control/runtime.py:1060-1068`）。
- revision が一致して再起動が進むと、既存 server/engine の停止と新しいものの起動が発生します。計画の表示自体は runtime owner に照会しますが、計画は profile や instance を予約しません（`strata_control/runtime.py:734-740,1132-1164`; `docs/MANAGEMENT_PROTOCOL.md:53`）。

## 出力とエラー

- 不正な形式の値や `--plan` との併用など、CLI 層の validation error は human 出力では stderr に `strata: ...` を出し、該当するエラーコードで終了します。JSON 出力では `{schema_version, ok: false, error: {code, message}}` を stdout に出します（`strata_cli/cli.py:527-532,2166-2173`）。
- plan の revision と実行時 candidate revision が異なる場合、human 出力は profile 名・状態・`profile_changed_after_preview` を表示し、終了コード6になります。JSON 出力は実行結果を stdout に出し、終了コード6になります。失敗した `runtime restart` では設定を読み取れる場合に engine log の案内も stderr に追加されます（`strata_control/runtime.py:1067-1068`; `strata_cli/cli.py:1357-1373`）。
- revision 不一致時は owner 内の restart が停止前に戻るため、旧 runtime はこの条件によって停止されません。ただし owner に要求を送る前に operation journal に記録され、結果は failed として記録されます（`strata_control/runtime.py:1067-1088`; `strata_control/management.py:317-333`; `strata_control/journal.py:376-393`）。ほかの失敗条件や、revision 比較後に起きる起動失敗では、rollback の成否に応じて旧 runtime が復元されるか、失敗状態になります（`strata_control/runtime.py:1103-1130`）。

## 根拠

- `strata_cli/cli.py:238-254` — `runtime restart` parser、必須 profile、revision option と出力形式。
- `strata_cli/cli.py:1345-1373,2166-2188` — 値の転送、結果表示、終了コードと validation error の出力。
- `strata_control/management.py:134-139,292-333` — revision 形式、plan との相互作用、未指定時の値、journal と runtime への転送。
- `strata_control/profiles.py:58-63,150-166` — profile revision の計算と profile 読み込み。
- `strata_control/runtime.py:702-731,1043-1130` — owner への要求、revision の照合、drain/restart と rollback 経路。
- `strata_control/runtime.py:1132-1164`; `docs/MANAGEMENT_PROTOCOL.md:53` — restart plan の revision 情報と plan が状態を予約しないこと。

調査範囲は上記 checkout の Python CLI・runtime 実装と管理 protocol 文書です。同一 revision の CLI `--help` および Release 配布物は照合していません。
