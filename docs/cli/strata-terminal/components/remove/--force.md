# `strata components remove --force`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると `True`、省略時は `False`。 |

## 役割

このコマンドで `--force` は受理されますが、インストール済みエンジンの削除処理には作用しません。削除処理は使用中のエンジンや実行中のプログラムが使うエンジンを引き続き拒否し、`--force` によってそれらの保護を回避することはできません。オプションの説明文はテスト起動に失敗した更新版を再試行する場合のもので、削除コマンドの動作とは結び付きません（`terminal/strata_cli/update_cmd.py:47-56, 88-91, 314-321, 337-338, 445-497`）。

## 使い方

```sh
strata components remove 0.1.54 --force
```

`0.1.54` は削除するインストール済みエンジンのバージョン例です。フォルダー名を指定することもできます。`--force` を付けても削除条件は変わりません（`terminal/strata_cli/update_cmd.py:88-91`）。

## 値と既定値

- `--force` は `argparse` の `store_true` action で登録され、引数値を取りません。既定値は `False` です（`terminal/strata_cli/update_cmd.py:53`）。
- `components remove` はこの共通オプション群を登録するため、`--force` を受理します（`terminal/strata_cli/update_cmd.py:47-56, 88-91`）。
- `--force=true` のような値付き指定は定義されていません。

## 実行時の動作

CLI は `--force` の値を更新コンテキストの `force` フィールドへコピーします。その後 `remove` は、指定されたバージョンまたはフォルダー名と任意の `--family` で対象を特定し、エンジン一覧を再確認したうえで `delete_engine` を呼びます。この削除経路は `ctx.force` を参照せず、削除関数にも渡しません。そのため `--force` の有無で対象選択や削除結果は変わりません（`terminal/strata_cli/update_cmd.py:314-321, 337-338, 445-466, 492-497`; `terminal/strata_control/engine_library.py:184-197, 317-335`）。

削除時はコンポーネント更新ロック内で対象を再検査します。使用中のエンジン、または稼働中プロセスが使うエンジンは拒否されます。削除可能ならエンジンフォルダーを `.deleting-<識別子>` にリネームしてから再帰削除し、Qwen 系エンジンでは更新状態の `previous` / `pinned` / `failed` 情報を必要に応じて整理し、削除履歴を記録します。形状別エンジンでも pin 情報を整理して削除履歴を保存します。どの処理も `--force` では迂回されません（`terminal/strata_control/engine_library.py:139-148, 327-366`）。

## 適用条件と副作用

`--force` 自体に追加の適用条件や副作用はありません。副作用は `remove` コマンド本体によるもので、対象エンジンのファイルと関連状態・履歴を更新します。モデルや設定は削除対象に含めない実装です。稼働中プログラムによる使用確認で使用中と判定されると削除は止まり、リネーム後の再帰削除で開かれているファイルが残った場合は `.deleting-*` に残し、次回の削除時に掃除を試みます（`terminal/strata_control/engine_library.py:91-96, 317-319, 334-366, 373-380`）。

## 出力とエラー

- 削除成功時、人向け出力は削除したバージョンと解放量を表示します。`--output json` または `jsonl` では機械可読モードとして JSON の成功結果を出力します（`terminal/strata_cli/update_cmd.py:305-306, 492-497`）。
- 対象が見つからない、バージョンが複数候補に一致する、使用中のエンジンまたは実行中プロセスが使うエンジンを指定した場合はエラーとなり、これらの選択・保護条件は `--force` で解除されません。対象不明・曖昧・保護条件による拒否はコード 2 です（`terminal/strata_control/engine_library.py:184-197, 327-335`）。
- フォルダーを退避先へリネームできない場合は「何も変更していない」とするエラーを返し、コード 6 です。通常出力は標準エラー、`--output json/jsonl` では JSON エラー形式になります（`terminal/strata_control/engine_library.py:337-342`; `terminal/strata_cli/cli.py:558-563, 2258-2265`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — 共通オプション群での `--force` parser 定義（値なし、`store_true`、ヘルプ文）。
- `terminal/strata_cli/update_cmd.py:88-91` — `components remove` が位置引数と `--family` を登録し、共通オプション群も取り込む箇所。
- `terminal/strata_cli/update_cmd.py:314-321, 337-338, 445-497` — `force` をコンテキストへ格納する箇所、remove の分岐、削除関数呼び出しと成功出力。remove 分岐は `force` を使わない。
- `terminal/strata_control/engine_library.py:184-197, 317-366` — 対象の解決、削除条件、ファイル操作、状態更新と履歴記録。
- `terminal/strata_control/engine_library.py:139-148, 373-380` — 使用中判定と、削除後に残った退避フォルダーの掃除。
- `terminal/strata_cli/cli.py:558-563, 2258-2265` — 人向け／JSON エラー出力とファイル操作エラーの終了コード。
