# `--force`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らないフラグ。未指定時は `False`、指定時は `True`。 |

## 役割

このコマンドでは `--force` は受理されますが、エンジン切り替えの処理には影響しません。parser は共通オプションとして登録し、更新処理向けの「テスト起動に失敗した、または rollback された版を再試行する」という説明を表示します。しかし `use` の実行経路では `force` を参照せず、切り替えの互換性確認や署名・ファイル検証を省略しません。

## 使い方

```sh
strata components use newest --force
```

上の例の `--force` は受理されますが、`strata components use newest` と同じ動作です。切り替え先を指定する位置引数 `engine` には、インストール済みの版、フォルダー名、または `newest` を指定します。

## 値と既定値

`argparse` の `store_true` フラグで、値は不要です。省略時は `False`、指定時は `True` になり、複数回指定しても真偽値のままです。値を後置する形式は定義されていません。`--force` の登録は共通 parser `_common` にありますが、説明文の再試行動作はこのコマンドには適用されません（`terminal/strata_cli/update_cmd.py:47-55,84-87`）。

## 実行時の動作

`run` は parser の値を `updater.Context.force` に格納します（`terminal/strata_cli/update_cmd.py:314-321`）。`components use` は `_engines_command` に分岐し、適合しないエンジンを拒否した後、`engine_library.use_engine` に切り替え先を渡します。この呼び出しには `force` 引数がなく、`use_engine` も context の `force` を参照しません（`terminal/strata_cli/update_cmd.py:337-338,445-471`、`terminal/strata_control/engine_library.py:211-228`）。

したがって、`--force` を付けても非互換エンジンを強制選択できず、署名検証や全ファイル検証も回避できません。通常の切り替えでは、対象エンジンの署名とファイルを検証したうえで、選択状態を保存します（`terminal/strata_control/engine_library.py:249-269,296-312`）。このオプション自体による設定変更、ダウンロード、削除はありません。

## 適用条件と副作用

`--force` は `strata components use` で受理されますが、このコマンド経路での効果はありません。切り替え処理そのものはモデル稼働中には待機または拒否され、選択したエンジンの pin と履歴を更新することがあります。`newest` を選ぶ場合は、更新追従のため pin を置かない動作です（`terminal/strata_control/engine_library.py:211-228,255-272`）。

## 出力とエラー

`--force` 固有の出力・失敗経路はありません。エンジンが見つからない、指定が曖昧、またはエンジンを利用できない場合は、通常の `use` のエラーになります。実行中モデルによる拒否は終了コード 7、選択・検証エラーはコード 2 または 5 で返されます（`terminal/strata_control/engine_library.py:184-197,202-207,221-228,249-254,296-310`）。人向け出力ではエラーを `strata:` 付きで stderr に出し、`--output json` / `jsonl` では JSON エラーを出力します（`terminal/strata_cli/update_cmd.py:303-312,374-384`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-55,84-87` — 共通 parser の `--force` 宣言と `components use` への登録。
- `terminal/strata_cli/update_cmd.py:314-321,337-338,445-471` — context への格納、`use` の分岐、適合性確認と切り替え関数の呼び出し。
- `terminal/strata_control/engine_library.py:211-228,249-269,296-312` — `use_engine` の処理、署名・ファイル検証、状態保存。`force` を参照する処理はこの呼び出し経路にない。
- `terminal/strata_control/engine_library.py:184-207`、`terminal/strata_cli/update_cmd.py:303-312,374-384` — 選択エラー、稼働中モデルによる拒否、および CLI のエラー出力。
