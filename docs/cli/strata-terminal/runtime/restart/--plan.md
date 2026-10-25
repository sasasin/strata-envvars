# `strata runtime restart --plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime restart` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は `False` |

## 役割

稼働中の管理対象 runtime と保存済みプロファイルの起動内容を比較し、restart の候補と前提条件を確認します。`--plan` 自体は drain や起動を行いません。

## 使い方

```sh
strata runtime restart --profile four-gpu --plan --output json
```

`--profile` は必須です。計画の内容を確認するには `--output json` を指定します。ソース設定ファイルの切り替えや編集中の設定内容の移行を候補に含める場合は、対応する許可フラグを付けて計画します。

```sh
strata runtime restart --profile four-gpu --allow-source-switch --plan --output json
strata runtime restart --profile four-gpu --allow-source-migration --plan --output json
```

## 値と既定値

`argparse` の `store_true` フラグであり、引数値はありません。既定値は `False` です。`--plan` を指定すると preview 経路、指定しないと restart 実行経路に進みます。短縮 alias はありません（`strata_cli/cli.py:238-254`）。

## 実行時の動作

CLI は `--plan` と `--allow-source-switch` / `--allow-source-migration` を runtime 管理処理へ渡します（`strata_cli/cli.py:1345-1356`）。preview 経路は実行用の owner・instance・profile revision・source digest の条件値を受け付けず、指定された場合はエラーにします。その後、`runtime.plan_restart` を呼び出します（`strata_control/management.py:298-304`）。

所有ホスト側では、現在の状態が `ready` であることを確認し、保存済みプロファイルから候補 launch・source config・source bytes を読み取ります。成功時の結果には現在と候補の owner/instance・profile revision・source SHA-256・server argv、差分の有無、rollback snapshot の要否が含まれます。`would_drain` と `would_start` はどちらも `false` です（`strata_control/runtime.py:787-791`, `1132-1164`）。`plan_restart` の RPC timeout は10秒です（`strata_control/runtime.py:734-740`）。

通常の plan は source config の切り替えを自動許可しません。候補が現在と異なるファイルなら `--allow-source-switch` が必要です。同じ source config の bytes が実行中の bytes と異なる場合は `--allow-source-migration` が必要です。source switch では旧・新ファイルが別 inode の通常ファイルであること、旧 source が利用可能であることも確認されます（`strata_control/runtime.py:793-811`）。許可フラグを伴う計画は、実行時に `--if-source-sha256` へ渡す候補 digest を返します。source change を伴う実行で digest を省くと拒否されます（`strata_cli/cli.py:241-244`, `strata_control/management.py:305-310`）。

`--plan` は実行用の drain・起動・rollback を行いませんが、稼働中 host へのローカル RPC、状態確認、候補プロファイルと source config の読み込み・ハッシュ計算は行います。plan は予約ではなく、確認後に profile/source/runtime が変わる可能性があります。実行時に revision、owner/instance ID、候補 source digest を指定して照合できます（`strata_control/runtime.py:734-740`, `1132-1164`; `docs/TERMINAL.md:78-91`）。

## 適用条件と副作用

plan は管理対象 runtime が `ready` の場合に限り成功します。停止中、起動中、失敗状態では `runtime_not_ready` と終了コード 6 になります。保存済みプロファイルから候補 launch/source を作成・読み込みできない場合は `new_profile_preflight_failed`（終了コード 5）です。source change が許可されていない、旧 source を利用できない、同一ファイルへの切り替えになるなどの場合はエラー結果を返し、終了コード 6 になります（`strata_control/runtime.py:1132-1147`, `793-811`）。

成功した計画は operation journal に restart 実行として記録されません。journal 記録は `--plan` を通らない実行経路で作られます（`strata_control/management.py:298-304`, `319-333`）。

## 出力とエラー

`--output` の既定値は `human` です。restart の plan 成功時、human 出力は `<profile>: ready` のような状態表示にとどまり、候補 argv・revision・digest の詳細は表示しません。計画詳細が必要なら `--output json` を指定してください。JSON 成功時は `schema_version` と plan の各フィールドが出力されます（`strata_cli/cli.py:254`, `1357-1369`）。

plan が失敗した場合は結果の `ok` が false となり、終了コードが返ります。`--output json` では CLI が結果オブジェクトを JSON 出力します。例外として上がる validation error は、human では stderr の `strata: ...`、JSON では `error.code` と `error.message` を含むエラー JSON になります（`strata_cli/cli.py:1359-1373`, `527-532`, `2166-2188`）。restart plan の失敗時には、参照可能であれば保存済み run config の engine log パスと末尾の行も stderr に補助表示されます（`strata_cli/cli.py:1370-1372`, `1376-1386`）。

## 根拠

- `strata_cli/cli.py:238-254` — restart parser、`--plan` 宣言、関連 option と既定値。
- `strata_cli/cli.py:1345-1373` — runtime action への引き渡し、human/JSON 出力、終了コード。
- `strata_control/management.py:298-333` — plan 経路と restart 実行・journal 経路の分岐、入力 validation。
- `strata_control/runtime.py:734-740` — preview RPC。
- `strata_control/runtime.py:787-811` — 候補作成と source switch/migration 条件。
- `strata_control/runtime.py:1132-1164` — plan の適用条件、結果フィールド、副作用の有無。
- `docs/TERMINAL.md:78-91` — source switch/migration の利用例と digest を使う手順。
