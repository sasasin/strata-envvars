# `strata timeskip apply`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata timeskip apply` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/time_skip.py` |

## 役割

保存済み Time-skip run から、保持されている checkpoint またはレビュー後に利用者が選んだ revision attempt を workspace に反映します。適用前に run 開始時点の baseline と適用先を照合し、差分があれば上書きせず conflict として拒否します。`--restore` は通常の apply と異なり、run の baseline を適用先へ戻します。

## 使い方

```sh
# 保持された結果の適用内容を確認（ファイルは変更しない）
strata timeskip apply RUN_ID --dry-run

# 保持結果を既定 workspace に適用
strata timeskip apply RUN_ID

# レビューして選んだ revision attempt を適用
strata timeskip apply RUN_ID --attempt 1

# baseline を既定 workspace に復元
strata timeskip apply RUN_ID --restore
```

`RUN_ID` は `strata timeskip run` が表示する ID です。適用後の状態確認には `strata timeskip status RUN_ID` を使えます。

## 実行時の動作

- CLI は state directory から run 記録を読み、そこに記録された workspace、checkpoint、attempt を使って run を再構成します。`--workspace DIR` を指定すれば apply/restore の適用先だけを変更します。省略時は run に記録された workspace が対象です。
- 通常の適用では `--attempt` 省略時に選択済み checkpoint を使い、指定時はその番号の revision attempt を使います。run にその attempt がない、または候補ディレクトリが存在しない場合は失敗します。attempt の選択は利用者が内容を確認して行う前提です。
- 適用先のファイル一覧・サイズ・SHA-256 を baseline の記録と比較します。異なる場合は最初に見つかった差分パスを含む conflict を返し、CLI は終了コード `6` で拒否します。
- 差分がなければ選択結果との差分を計算し、変更・追加対象を書き込み、選択結果にない baseline ファイルを削除します。`.git`、`__pycache__`、`.strata` は inventory と tree copy の対象から除外されます。
- 実適用前に現在の適用先を run の `rollback` ディレクトリへコピーします。書き込み中に例外が起きると rollback copy から復元し、失敗として終了コード `6` を返します。成功時は書き込み一覧、rollback copy のパス、使用した checkpoint を表示します。
- `--dry-run` は conflict 照合と差分計算まで行い、`would write` / `would remove` を表示します。ファイルの適用と rollback copy 作成には進みません。
- `--restore` は通常 apply の baseline 照合や dry-run 分岐を通らず、baseline snapshot を適用先へコピーし、run の選択 checkpoint を baseline に更新して保存します。したがって既定 workspace が run 開始後に編集されていても復元を実行します。`--dry-run` と併用しても restore の preview にはなりません。

## オプションと注意点

このコマンドで受け付けるオプションは `--attempt`、`--dry-run`、`--restore`、`--state-dir`、`--output` と `--help`（`-h` alias）です。各値と parser 定義は索引にある個別文書を参照してください。

通常 apply は適用先の内容を置き換え、baseline にあって結果にないファイルを削除する場合があります。まず `--dry-run` で一覧を確認してください。適用先が run 開始後に変わっていれば通常 apply は拒否されます。`--restore` はこの conflict 保護を通らず baseline をコピーするため、復元先を選ぶ際は特に注意してください。rollback は通常 apply 中の例外から戻すためのコピーであり、コマンド成功後の手動 undo 機能として説明されてはいません。

`--state-dir` が未指定なら `STRATA_TIMESKIP_DIR`、次に OS ごとの state base 配下 `strata/time-skip` が使われます。適用内容は既存 run 記録と snapshot に依存します。異なる OS での実ファイルシステム固有の挙動や、破損した snapshot の復旧結果はこのコード調査では実行確認していません。

## 出力とエラー

- human 出力では成功時に `applied ...` と `rollback copy: ...`、dry-run 時に `would write: ...` と該当すれば `would remove: ...`、restore 成功時に `restored ...` を標準出力へ表示します。
- `--output json` は成功結果を `schema_version` と `ok: true` を含む JSON として出力します。エラーは `ok: false`、`error.code`、`error.message` を含む JSON です。
- run が見つからない、選択した attempt/checkpoint がない場合など `TimeSkipError` は終了コード `2`。workspace が baseline から変わっている conflict、適用失敗・rollback 後の失敗は終了コード `6` です。OS のファイル操作エラーも CLI の共通処理でコード `6` として報告されます。
- parser に必須の位置引数 `RUN_ID` がない、または不正な引数がある場合は argparse の usage/error 経路になります。

## 根拠

- `strata_cli/cli.py:348-393` — `timeskip apply` の登録、`RUN_ID` と各オプションの parser 定義・既定値。
- `strata_cli/cli.py:1467-1485` — state directory の選択優先順位。
- `strata_cli/cli.py:1524-1555` — run 読み込み、restore/apply 分岐、終了コード、human/JSON 出力。
- `strata_cli/cli.py:1605-1618` — 保存済み run の再構成。
- `strata_cli/cli.py:527-542,2177-2183` — CLI 共通エラー形式と OSError 処理。
- `strata_control/time_skip.py:597-664` — attempt/checkpoint 選択、baseline 照合、dry-run、rollback、restore の実処理。
- `strata_control/time_skip.py:241-268,271-284` — inventory の digest 算出対象と tree copy 時の除外項目。
- `docs/cli/README.md:674-718` — `strata timeskip` のコマンド階層と apply 配下の予定文書。
