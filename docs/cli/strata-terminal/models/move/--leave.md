# `--leave`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models move` |
| オプション | `--leave` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時 `False` |

## 役割

中断したモデルフォルダーの移動を再開せず、元のフォルダーを使い続けるための後処理を行います。移動処理が記録した対象ファイルについて、新フォルダー側の部分コピーを削除し、元ファイルがすでに新フォルダーへ移されていた場合は元フォルダーへ戻します（`strata_cli/cli.py:165,690-703`、`strata_control/models_move.py:534-539`）。

## 使い方

移動が中断された後に実行します。引数 `NEW_FOLDER` は不要です。

```sh
strata models move --leave
```

別の元データフォルダーを調べる場合は `--from OLD_FOLDER` を指定できます。対象インストールを限定して run config を更新する場合は `--install-dir` を併用できます（`strata_cli/cli.py:163,167-168,620-622,685-692`）。

## 値と既定値

`argparse` の `store_true` で、値を受け取らず、既定値は `False` です。短縮 alias はありません（`strata_cli/cli.py:162-171`）。

## 実行時の動作

通常の移動先指定経路より先に `--status` / `--resume` / `--leave` のいずれかを検出し、中断移動の処理へ分岐します。`--from` があればそのパス、なければ Strata の既定データフォルダーを調べます。中断状態が確認できると、その記録の `from` と `to` を使って `models_move.leave` を呼び出します（`strata_cli/cli.py:617-622,668-672,690-692`）。状態は `models-move.json` の記録に基づき、実行中プロセスの移動は中断扱いにしません（`strata_control/models_move.py:29-30,303-325`）。

後処理は状態記録に列挙されたファイルだけを対象にします。新フォルダーの `.part` ファイルを削除し、元と新の両方にファイルがある場合は新側を削除します。新側だけにファイルがある場合は元側へ戻し、別ドライブならコピーを検証してから新側を削除します。最後に対象 run config のパスを元フォルダーへ戻し、両フォルダーの移動状態ファイルを消します（`strata_control/models_move.py:534-573`）。

## 適用条件と副作用

- 中断移動が見つからない場合は後処理を行いません。`--from` を誤ったフォルダーにすると、その場所に対応する中断記録が見つからない可能性があります（`strata_cli/cli.py:620-622,679-684`、`strata_control/models_move.py:303-325`）。
- `--status` も指定された場合は `--status` 分岐が先に実行されるため、`--leave` の処理は行われません。`--resume` と `--leave` を同時に指定した場合、状態確認後は `--leave` 分岐に入ります（`strata_cli/cli.py:673-692`）。
- `NEW_FOLDER` を同時に指定しても、未完了処理では保存済みの `to` を使用します。`--plan` と `--cancel-file` もこの経路では参照されません（`strata_cli/cli.py:621-622,668-705`）。
- `--install-dir` を指定すると、そのインストール内の run config を対象にします。未指定なら見つかった全 Strata インストールの config を対象にします。インストール探索時の例外は空リストとして扱われるため、その場合 config のパス更新はありません（`strata_cli/cli.py:685-689`）。
- 共通 parser がこのコマンドにも `--quiet` を追加しますが、`--leave` の処理経路は `a.quiet` を参照しません。そのため、この経路の human 完了・エラー出力は抑制されません（`strata_cli/cli.py:508-515,668-703`）。
- 実際のファイル削除・復元、空ディレクトリの整理、config 書き換え、状態ファイル削除を行います。両フォルダーに同名ファイルがある場合、新側のファイルを削除する動作です（`strata_control/models_move.py:545-572`）。

## 出力とエラー

成功時は human 出力で旧フォルダーにモデルを残し、新側の部分コピーを削除した旨を表示して終了コード 0 を返します。`--output json` / `jsonl` または追加された `--json` では、`ok: true`, `event: "result"`, `left: true` と、削除数・復元数・削除バイト数を含む JSON オブジェクトを1つ出力します（`strata_cli/cli.py:508-515,699-703`）。

中断記録がない場合、human 出力は stderr に `strata: no move was interrupted.`、JSON 系出力は `error.code: "nothing"` を出し、終了コード 5 を返します（`strata_cli/cli.py:679-684`）。復元または削除で `OSError` が発生した場合は `MoveError`（code `io`）として扱い、human は stderr、JSON 系は error object にメッセージと詳細を出して終了コード 5 を返します（`strata_control/models_move.py:35-42,557-565`、`strata_cli/cli.py:693-698`）。

## 根拠

- parser と `--leave` の説明、任意位置引数: `strata_cli/cli.py:162-171`
- 既定データフォルダー、未完了処理への分岐: `strata_cli/cli.py:617-626`
- 状態確認、status 優先、leave 実行、成功・失敗出力: `strata_cli/cli.py:668-705`
- 中断状態の判定: `strata_control/models_move.py:303-325`
- 対象ファイルの削除・復元、config の差し戻し、状態記録削除: `strata_control/models_move.py:534-573`
- `MoveError` のコード・詳細: `strata_control/models_move.py:35-42`

調査範囲は上記 revision の Terminal CLI と `strata_control/models_move.py` の実装です。別 OS の実行環境や Release 配布物での追加差分は確認していません。
