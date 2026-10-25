# `--if-source-sha256`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime restart` |
| オプション | `--if-source-sha256 SHA256` |
| 別名 | なし |
| 値 | 候補 run-config の生バイト列に対する SHA-256。小文字16進数64文字 |

## 役割

restart の実行時に、`--plan` で確認した候補 run-config の内容が同じかを照合する前提条件です。source ファイルの切り替えや編集を許可するオプションではありません。変更を許可する場合は `--allow-source-switch` または `--allow-source-migration` と併用し、plan が示した候補 digest を渡します。parser は値を必須とし、既定値はありません（省略時は `None`）。

## 使い方

まず plan で `candidate_source_sha256` を確認し、その値を restart に渡します。source の変更を伴うときは、plan と実行の両方に同じ許可 option を指定します。以下の `DIGEST_FROM_PLAN` は plan 出力の64文字の値に置き換えてください。

```sh
strata runtime restart --profile local --plan
strata runtime restart --profile local --if-source-sha256 DIGEST_FROM_PLAN
```

run-config の編集を伴う移行を明示的に許可する場合の形は次のとおりです。

```sh
strata runtime restart --profile local --allow-source-migration --plan
strata runtime restart --profile local --allow-source-migration --if-source-sha256 DIGEST_FROM_PLAN
```

## 値と既定値

- `SHA256` は `[0-9a-f]{64}` に一致する必要があります。大文字、短い値、空文字、その他の文字は受理されません。
- 値は候補 source config のファイル内容そのものの SHA-256 と比較されます。JSON の再整形や意味上の同値性ではなく、バイト列の一致が条件です。
- 未指定時は digest 比較をしません。ただし、`--allow-source-switch` または `--allow-source-migration` を指定する場合、この option も必要です。
- `--plan` と実行時の前提条件は併用できません。したがって plan 呼び出しにこの option を渡すと拒否されます。

## 実行時の動作

`strata_cli/cli.py` の restart parser が `SHA256` を受け取り、`_runtime` から `management.runtime_action` へ渡します（`strata_cli/cli.py:238-254`, `strata_cli/cli.py:1345-1356`）。management 層で形式を再検証し、実行では `expected_source_sha256` として runtime に転送します（`strata_control/management.py:126-131`, `strata_control/management.py:292-333`）。

runtime は現行 profile から候補 launch と source ファイルの生バイト列を読み込み、その SHA-256 を指定値と比較します。不一致の場合は `source_changed_after_preview`、終了コード 6 で返し、現在の実行が ready の段階で終了します。照合は drain・再起動を始める前に行われ、drain の途中でも source バイト列が変化していないか再確認します（`strata_control/runtime.py:1049-1073`, `strata_control/runtime.py:1085-1092`）。

この値だけで source 変更を許可することはありません。別ファイルへの切り替えは `--allow-source-switch` が必要で、旧 source が別個の通常ファイルとして利用可能であることも確認されます。同一ファイルの編集は `--allow-source-migration` が必要です。どちらの変更を伴うケースでも候補 digest が要求されます（`strata_control/runtime.py:793-811`; 必須条件は `strata_control/management.py:307-310`, `strata_control/runtime.py:719-720`）。

## 適用条件と副作用

restart は ready 状態の管理対象 runtime に対して実行されます。plan は現在状態が ready であることと候補 launch を確認し、現在・候補の source digest を出力しますが、drain や start は行いません（`strata_control/runtime.py:1132-1164`）。plan で source 変更を許可する flag を付けることはできますが、実行前提条件である `--if-source-sha256` は付けられません（`strata_control/management.py:299-304`）。

digest が一致して候補 preflight も通ると、runtime は旧 server を停止し、新候補を起動して ready を待ちます。移行を許可して旧設定ファイルの内容が変わっている場合、停止前に rollback 用の private snapshot を作成します。新 instance が ready になれば不要になった snapshot/source を整理し、整理に失敗した場合は cleanup pending を結果に記録します。新 instance の起動・ready 待ちに失敗した場合は旧 launch への rollback を試みます（`strata_control/runtime.py:1074-1128`）。

## 出力とエラー

- 不正な形式は validation error になります（`strata_control/management.py:126-131`, `strata_control/runtime.py:712-720`）。
- plan とこの option の併用、または source change 許可 flag と digest の欠落は拒否されます（`strata_control/management.py:299-310`）。
- plan 後の候補ファイル変更は `source_changed_after_preview`、終了コード 6 です。source 切替・移行の条件不成立、owner/instance の不一致、profile revision の変化なども実行前に拒否されます（`strata_control/runtime.py:1050-1068`）。
- 通常出力では `_runtime` が profile、state、error を標準出力に表示し、restart の失敗時には利用可能なら engine log の案内を標準エラーに出します。`--output json` では result object を JSON で標準出力に出します。最終終了コードは result の `exit_code` です（`strata_cli/cli.py:1357-1373`）。

## 根拠

- parser と help 文言: `strata_cli/cli.py:238-254`
- CLI から management への値の受け渡し: `strata_cli/cli.py:1345-1356`
- 形式検証、plan との併用制約、source change flag との相互作用: `strata_control/management.py:126-131`, `strata_control/management.py:292-333`, `strata_control/runtime.py:702-730`
- 候補 source bytes の digest 比較と source change の前提条件: `strata_control/runtime.py:793-811`, `strata_control/runtime.py:1043-1073`
- drain 前後、起動・rollback・snapshot cleanup: `strata_control/runtime.py:1074-1128`
- plan が提示する候補 digest と plan 中の副作用なし: `strata_control/runtime.py:1132-1164`

調査は上記 revision の Python Terminal CLI と `strata_control` 実装に限定しました。別 platform の実行環境や Release 配布 artifact 上での追加挙動は確認していません。
