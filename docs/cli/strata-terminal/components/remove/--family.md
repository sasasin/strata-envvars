# `--family`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。Strata checkout は `main` = `origin/main` で、調査時点の working tree に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--family` |
| 別名 | なし |
| 値 | `qwen` または `deepseek` |
| 既定値 | `None`（family を限定しない） |

## 役割

削除対象の engine family を指定します。同じ版番号の engine が Qwen 系と DeepSeek 系の両方にある場合に、対象を一方へ絞れます。`qwen` は Qwen だけでなく、それ以外の通常 engine family も含む一覧上の分類名です。`deepseek` は DeepSeek engine を指します（`strata_control/engine_library.py:30-33,180-195`）。

## 使い方

```sh
strata components engines
strata components remove <版番号またはフォルダー名> --family deepseek
```

`remove` は指定した導入済み engine package を削除する操作です。先に `strata components engines` で family と版番号・フォルダー名を確認してください。位置引数 `engine` は版番号またはフォルダー名です（`strata_cli/update_cmd.py:88-90`）。

## 値と既定値

- parser は `choices=("qwen", "deepseek")` を指定しており、この2つだけを受理します。値の大文字小文字変換や別名は定義されていません（`strata_cli/update_cmd.py:88-91`）。
- 省略時は `None` です。全 family の一覧から `engine` に合う項目を探します（`strata_cli/update_cmd.py:90`、`strata_control/engine_library.py:198-211`）。
- `--family` を付けると、候補一覧を指定 family に絞ってから、まず完全一致するフォルダー名、見つからなければ版番号で照合します（`strata_control/engine_library.py:198-206`）。

## 実行時の動作

parser 定義の `a.family` は `strata components remove` の handler から `find_entry(..., a.family)` に渡り、選択された項目の family とフォルダー名を使って `delete_engine()` が呼ばれます（`strata_cli/update_cmd.py:88-91,358-362,378,395`）。したがって、このオプションは削除先の family を絞るもので、engine の版・backend・導入元を選ぶものではありません。

family を指定しないで同じ版番号に複数項目が一致すると、曖昧として失敗し、フォルダー名を使うよう案内されます。同じ family 内に同じ版番号の複数 package がある場合も同様です。一致する engine がなければ、family を絞った候補の版番号一覧（候補なしなら `none`）を含むエラーになります（`strata_control/engine_library.py:198-211`）。

削除はローカルの component directory に対して行われ、更新 feed の取得やダウンロードはこの `remove` 分岐では行われません（`strata_cli/update_cmd.py:244-256,272-273,358-378,395`）。`--components-dir` を併用した場合は、その directory が走査・削除対象になります（同 `update_cmd.py:244`）。

## 適用条件と副作用

- `qwen` / `deepseek` のどちらでも、使用中の engine は削除できません。また、実行中のプログラムが使っている engine も削除対象として拒否されます。`delete_engine()` はロック取得後に一覧を再取得し、`can_delete` を再確認します（`strata_control/engine_library.py:167-177,294-309`）。
- 削除対象フォルダーを `.deleting-<短い乱数>` へ rename してから再帰削除し、親 directory の古い削除残骸を掃除します。rename に失敗すると「何も変更していない」とするエラーになります。開いたファイル等が残って再帰削除できない場合、残りは `.deleting-*` に保たれ、次回の削除時に掃除される設計です（`strata_control/engine_library.py:294-318,341-348`）。
- `qwen` package の削除では update state の `previous` / `pinned` を対象フォルダーに応じて更新し、同じ版の package が他に残らなければその版の `failed` 記録を消します。削除履歴も保存します（`strata_control/engine_library.py:319-330`）。
- `deepseek` package の削除ではモデル設定は変更しません。削除した package が属する root に有効な pin がなく、`.chosen` ファイルが残っている場合は stale pin を消します（`strata_control/engine_library.py:331-332`）。engine library の説明では、モデル・設定と他 family のファイル／state は削除対象外です（`strata_control/engine_library.py:13-17`）。
- `--backend` は共通 option として併用できますが、`--family` の代わりにはなりません。一覧の `fits` / active 判定に hardware backend が使われますが、`remove` handler は `fits` を削除条件にせず、family と engine 名で選んだ後 `can_delete` を検査します（`strata_cli/update_cmd.py:47-58,244-251,358-378`、`strata_control/engine_library.py:91-123,136-162,167-177,294-309`）。

## 出力とエラー

- 成功時の人間向け出力は、削除した engine の版番号と解放 byte 数を表示します。`--output json` または alias の `--json` では、削除結果を `schema_version` / `ok` を含む JSON に出力します（`strata_cli/update_cmd.py:395-400`、`strata_cli/cli.py:508-515`）。
- 未導入・曖昧な指定、使用中 package の削除拒否など `UpdateError` は終了コード 2 で返されます。rename 時の OS error は終了コード 6 です。人間向け出力では `strata: ...` を stderr に、JSON mode では error object を stdout に出します（`strata_control/engine_library.py:198-211,294-316`、`strata_cli/update_cmd.py:237-242,307-311`）。
- `argparse` の `choices` にない値は parser 定義で受理対象外です。Strata のコードからは無効値の個別メッセージや終了処理を定義していないため、その詳細はここでは記載しません（`strata_cli/update_cmd.py:90`）。

## 根拠

- parser と位置引数: `strata_cli/update_cmd.py:88-91`
- handler での family の転送と削除結果の出力: `strata_cli/update_cmd.py:358-400`
- family による候補絞り込み、版番号／フォルダー名照合、エラー条件: `strata_control/engine_library.py:198-211`
- 使用中・実行中 engine の拒否条件と削除処理: `strata_control/engine_library.py:167-177,294-334`
- Terminal CLI から `update_cmd.run()` への委譲、共通 `--json` / `--quiet`: `strata_cli/cli.py:508-515,2136-2138`
