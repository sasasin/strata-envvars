# `strata components remove --force`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時 `False`、指定時 `True`。 |

## 役割

このオプションは `remove` でも受理されますが、削除処理には効果がありません。共通 parser `_common()` が `action="store_true"` で登録し、help 文には「テスト起動に失敗した版、または rollback された版を再試行する」とあります。しかし `strata components remove` は削除経路へ進み、`--force` を参照しません。再試行の意味は update 経路に限られます（`strata_cli/update_cmd.py:47-56,88-91,254-256,272-273`、`strata_control/updater.py:637-641,1103,1682`）。

## 使い方

```sh
strata components remove 0.1.54 --force
```

`0.1.54` は削除対象の導入済み engine の版番号例です。コマンドは対象 package を削除するため、実行前に `strata components engines` で対象を確認してください。`--force` を付けても、削除対象の選び方や削除の可否は変わりません（`strata_cli/update_cmd.py:88-91,378,395-400`）。

## 値と既定値

値を取らない `store_true` フラグで、既定値は `False` です。値を続けて指定する形式は定義されていません。`--force` が省略・指定のいずれでも、remove 処理が削除関数へ渡すのは engine の family、folder、root であり、force 値ではありません（`strata_cli/update_cmd.py:53,88-91,378,395`）。

対象 engine は位置引数 `engine` に版番号または folder 名で指定します。`--family` は `qwen` / `deepseek` を選び、既定値は `None`（どちらの family も検索）です。該当なし、または複数候補に一致した場合は `UpdateError`（終了コード 2）になります（`strata_cli/update_cmd.py:88-91`、`strata_control/engine_library.py:198-211`）。

## 実行時の動作

`strata components remove` の parser は `_common()` を呼び、そこから `--force` を受理します。実行時には共通 `Context` の `force` フィールドへ値を格納しますが、`remove` は `_engines_command()` に分岐し、`find_entry()` で対象を解決した後、`delete_engine()` を呼びます。削除関数の処理に `ctx.force` の参照はありません。そのためこのコマンドでは、`--force` は構文上受理されるだけで、保護条件の解除、削除の再試行、対象の自動選択を行いません（`strata_cli/update_cmd.py:47-56,88-91,254-256,272-273,358-360,378,395`、`strata_control/engine_library.py:294-334`）。

`--force` が有効になるのは updater の更新判定経路です。例えば failed-before / skipped の更新を再度試す条件や、available な版を試す条件に `ctx.force` が使われています（`strata_control/updater.py:637-641,1103,1682`）。これは `remove` の削除条件には適用されません。

## 適用条件と副作用

オプション自体に OS / backend 条件はありません。削除可否は `--force` ではなく engine の状態で決まります。現在使用中の engine と実行中プロセスが使用している engine は削除を拒否し、終了コード 2 になります。拒否理由はそれぞれ「別の engine に切り替えてから」「model を停止してから」と案内されます（`strata_control/engine_library.py:167-176,294-309`）。

削除可能な場合、対象 directory を `.deleting-<乱数>` に rename してから再帰削除し、残った `.deleting-*` directory も sweep します。開いたままのファイルなどで削除できないものは `.deleting-*` に残り、次回の削除処理で再 sweep されます。Qwen family では前回版・pin・失敗記録を必要に応じて更新し、履歴を保存します。DeepSeek family では stale pin があれば解除します。モデル、設定、および別 family のファイルはこの処理で変更しないと実装されています（`strata_control/engine_library.py:294-334,341-348`）。

## 出力とエラー

成功時は人向け出力で削除版と解放容量を表示します。`--output json` / `--output jsonl`（または root parser が追加する `--json`）では成功結果を JSON で出力します（`strata_cli/update_cmd.py:56,395-400`、`strata_cli/cli.py:508-515`）。

対象が未導入、曖昧、使用中、または稼働中のプログラムに使用されている場合は `UpdateError` で失敗します。directory の rename が OS error で失敗した場合は、何も変更していない旨を含む説明と終了コード 6 になります。エラーは人向け出力では stderr の `strata: ...`、machine output では `ok: false` と error code / message を含む JSON になります（`strata_control/engine_library.py:198-210,301-316`、`strata_cli/update_cmd.py:233-242`）。この失敗経路でも `--force` による上書きはありません。

## 根拠

- `strata_cli/update_cmd.py:47-56` — `_common()` の `--force` parser 定義、値の型・既定値・help。
- `strata_cli/update_cmd.py:88-91` — `remove` parser と位置引数、`--family`、共通 option の登録。
- `strata_cli/update_cmd.py:254-256,272-273,358-360,378,395-400` — Context への格納、remove 分岐、対象解決、削除呼び出しと出力。
- `strata_control/engine_library.py:167-176,198-211,294-334,341-348` — 削除ガード、対象の曖昧性検査、rename・削除・状態更新。
- `strata_control/updater.py:637-641,1103,1682` — `force` が更新の再試行判定に使われる箇所。
- `strata_cli/cli.py:508-515` — one-shot parser に追加される `--json` / `--quiet`。

