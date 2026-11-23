# `strata components remove` の `--model-config`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--model-config` |
| 別名 | なし |
| 値 | `RUN_CONFIG.json` として表示される値を1つ取る。parser 上は文字列で、形式やファイルの存在を検証しない |

## 役割

このオプションは共通 parser から `remove` にも登録されています。説明文は更新時のテスト起動に使う run config を示しますが、`remove` の実行経路では config を読み込まず、エンジン削除にも使いません。したがって `remove` に付けても削除対象や削除動作は変わりません（登録は `terminal/strata_cli/update_cmd.py:47-56,88-91`、共通 Context への格納は `terminal/strata_cli/update_cmd.py:314-321`、削除分岐は同 `:445-497`）。

## 使い方

構文上は次のように指定できます。これは引数の形を示す例であり、実行すると `<engine>` に一致するインストール済みエンジンを削除します。

```text
strata components remove <engine> --model-config <RUN_CONFIG.json>
```

`<engine>` はバージョンまたはフォルダー名です。削除対象の選択に run config は関与しません（`terminal/strata_cli/update_cmd.py:88-91,466,492-497`）。

## 値と既定値

- `argparse` の値引数で、指定時は後続の1値を `a.model_config` に格納します。別名、`type`、`choices`、独自 validator は定義されていません（`terminal/strata_cli/update_cmd.py:54-56`）。
- 省略時の値は `None` です。`default=None` として登録されています（同 `:54-55`）。
- 値を省略すると `argparse` の引数エラーになります。文字列の内容やパスの存在確認はこの parser では行われません。
- 同じ引数を複数回指定した場合の独自処理はありません。標準の `argparse` の `store` 動作が適用されます。

## 実行時の動作

`remove` parser は `_common(remove)` を呼ぶため `--model-config` を受理します。実行時には CLI dispatcher がこのサブコマンドを `update_cmd.run(a)` に渡し、同関数は `a.model_config` を `updater.Context.run_config` に格納します（`terminal/strata_cli/update_cmd.py:88-91,314-321`、`terminal/strata_cli/cli.py:2210-2212`）。

その後 `remove` は `_engines_command` に入り、エンジン一覧から位置引数 `engine` と任意の `--family` で対象を選び、`lib.delete_engine(...)` を呼びます。この分岐では `ctx.run_config` を参照しません（`terminal/strata_cli/update_cmd.py:337-338,445-466,492`）。`delete_engine` も run config を引数に取らず、インストール済みエンジンの削除と関連状態の更新を行います（`terminal/strata_control/engine_library.py:317-366`）。

従って、値が有効な JSON か、存在するファイルかに関係なく、`--model-config` 自体は `remove` の結果に影響しません。run config が利用されるテスト起動側の挙動は `remove` のスコープ外です。

## 適用条件と副作用

- `--model-config` は `strata components remove` で parser により受理されますが、機能上の適用条件はなく、削除処理には作用しません。
- 削除対象は `engine` と `--family` に基づいて特定されます。現在使用中のエンジンや実行中プログラムが使用するエンジンなど、削除不可の項目は拒否されます（`terminal/strata_cli/update_cmd.py:88-91,466,492`、`terminal/strata_control/engine_library.py:317-335`）。
- 削除が成功すると対象フォルダーを一時名へ移動して削除し、Qwen 系または shape engine の状態・履歴を更新します。モデルと設定は変更しません（`terminal/strata_control/engine_library.py:337-366`）。この副作用は `--model-config` の値によるものではありません。

## 出力とエラー

- 成功時は通常出力で削除したエンジンのバージョンと解放容量を表示し、`--output json` または `jsonl` の場合は JSON を出力します（`terminal/strata_cli/update_cmd.py:305,492-497`）。
- 対象が見つからない、または削除不可の場合は `UpdateError` になります。対象フォルダーの移動に失敗した場合は「何も変更されなかった」とするエラー（終了コード 6）になります（`terminal/strata_control/engine_library.py:331-342`、エラーの出力処理は `terminal/strata_cli/update_cmd.py:307-312,374-378`）。
- `--model-config` の値を理由とする検証エラーや警告は、確認した `remove` 経路にはありません。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — 共通オプション parser 定義。`--model-config` の値表示と既定値。
- `terminal/strata_cli/update_cmd.py:88-99` — `components remove` の parser と共通オプションの登録。
- `terminal/strata_cli/cli.py:2210-2212` — `components remove` の dispatcher。
- `terminal/strata_cli/update_cmd.py:314-321,337-338,445-466,492-497` — Context 作成後の remove 分岐と、config を参照せず削除する処理。
- `terminal/strata_control/engine_library.py:317-366` — 削除対象の検証、ファイル操作、状態更新、返却値。
