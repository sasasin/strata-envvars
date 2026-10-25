# `--if-revision`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection set` |
| オプション | `--if-revision` |
| 別名 | なし |
| 値 | `REVISION` を1つ取る。保存済み connection の revision 文字列 |

## 役割

`strata connection set` で編集する connection が、確認した revision のままであることを要求します。preview 後に別の更新が入った場合など、古い内容を前提に編集するのを防ぐための事前条件です。connection の編集対象は `url`、`prefix`、`credential_env` のいずれか1つです。

## 使い方

まず `strata connection show NAME --output json` または `strata connection list --output json` で表示された `revision` を使います。

```sh
strata connection set work prefix=/new-strata --if-revision REVISION_FROM_SHOW --plan
```

`--plan` を外すと、条件が一致した場合に保存します。実際の revision 値は対象 connection の出力から取得してください。

## 値と既定値

値は必須です。parser は値を文字列として受け取り、形式検証は行いません。省略時は `None` となり、利用者が指定する revision との事前条件比較は行われません（parser 定義: `strata_cli/monitor_commands.py:86-90`）。

connection の revision は、保存ファイルのバイト列に対する SHA-256 の先頭16文字で、小文字16進数です（`strata_cli/connections.py:124-125,128-145`）。大文字、長さ違い、空文字なども CLI parser では拒否されず、現在の revision と一致しなければ不一致として失敗します。複数回指定した場合の個別検証や重複拒否は実装されていません。

## 実行時の動作

`connection set` は最初に `connections.propose(name, assignment)` を呼び、保存済み connection とその revision を読み、候補値を検証します。その後、`--if-revision` が指定されていれば候補作成時の revision と文字列比較します。一致しなければ保存処理へ進みません（`strata_cli/monitor_commands.py:140-160`）。

`--plan` を併用すると、revision 照合後に候補と `would_save` を表示して終了し、ファイルは更新しません。通常実行では `connections.save()` に候補作成時の revision が渡されます。保存処理は connection ごとのロックを取得して最新 revision を再読込し、値が変わっていれば終了コード6で拒否します。revision が変わっていない場合、候補が現行値と同じならファイルを変更せず、異なる場合は一時ファイルから置換保存します（`strata_cli/connections.py:167-187,190-218,256-270`）。

したがって、明示した `--if-revision` は利用者が確認した状態との一致を検査し、保存時の内部 revision 照合は候補作成後の競合を検出します。オプションを省略しても保存時の内部競合検出は実行されますが、利用者が事前に確認した revision との一致条件はありません。

## 適用条件と副作用

このオプションは `strata connection set` 専用です。`strata connection show` / `list` の revision を編集前確認に使えます。別の connection や別時点の revision は一致せず、候補は保存されません。

revision は connection ファイルの内容に基づきます。成功時は assignment に応じた connection ファイル更新（または値が同じ場合は更新なし）があり、稼働中の接続先・サーバーを直接変更する処理ではありません（`strata_cli/connections.py:124-145,256-270`）。

## 出力とエラー

一致して `--plan` を指定した場合、選択した human/JSON 出力形式で候補 connection、revision、`would_save` が出力されます。通常実行では保存後の connection と revision、および `previous_revision` が出力されます（`strata_cli/monitor_commands.py:155-163`）。出力形式は `--output human|json`（既定値 `human`）または `--json` で選べます（同ファイル `91-94`）。

指定 revision が候補作成時点の revision と異なる場合、エラー `connection changed since preview; inspect it again`、終了コード6です。人向け出力では `strata: ` を付けて stderr に出し、JSON 出力では stdout に `ok: false`、`error.code: 6` とメッセージを出します（`strata_cli/monitor_commands.py:124-129,152-154,231-236`）。候補作成後、保存ロック取得までに他の更新があった場合も、保存側の再確認で同じ競合エラーになります（`strata_cli/connections.py:262-265`）。

## 根拠

- parser と option scope: `strata_cli/monitor_commands.py:75-94`。root parser への登録は `strata_cli/cli.py:486-493`。
- 候補作成、指定 revision 比較、plan/save 分岐、成功時出力: `strata_cli/monitor_commands.py:140-164`。
- revision の計算・読込: `strata_cli/connections.py:124-145`。
- 保存時の revision 形式検証、ロック中の再確認、同値時の無変更、保存: `strata_cli/connections.py:256-270`。
- エラーの形式と終了コードの伝播: `strata_cli/monitor_commands.py:124-129,231-236`。
- 利用者向け例: `docs/TERMINAL.md:30-41`。例は `--if-revision` を示しますが、値の仕様は上記ソースを根拠にしています。
- この調査ではソース checkout と文書内資料を確認しました。別途ビルド済み CLI や Release 配布物との比較は行っていません。
