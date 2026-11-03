# `strata components remove --wait`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒数を表す浮動小数点数（`SECONDS`）。parser に範囲検証はない |

## 役割

この option は `_common()` により `remove` parser にも登録されています。ただし現行実装では、remove の削除処理は `--wait` の値を参照せず、実行中の engine が止まるまで待つ動作も行いません。engine 使用中なら削除は拒否されます。

## 使い方

```sh
strata components remove 0.1.54 --wait 30
```

`30` は parser で受理されますが、`remove` では効果がありません。待機が必要な場合は、engine を利用中のモデル／プログラムを停止してから再実行してください。

## 値と既定値

`--wait` は `type=float`、既定値 `None`、値の metavar は `SECONDS` です。数値に変換できない値は argparse の引数エラーになります。明示した秒数に対する範囲や非負条件の検証は parser にありません。共通 parser から作られる `Context.wait` は `a.wait or 0.0` で初期化されますが、remove の処理ではその値を使いません。

## 実行時の動作

`strata_cli/update_cmd.py` の `_common()` が `--wait` を定義し、`remove` parser にも同じ共通 option 群を追加します（`strata_cli/update_cmd.py:47-56,88-91`）。実行時は `run()` が `Context.wait` に値を渡し、`components_command` が `remove` の場合に `_engines_command()` を呼びます（`strata_cli/update_cmd.py:244-256,272-273`）。

`_engines_command()` は `use` 分岐でのみ `_maybe_wait()` を呼び、その後の remove 分岐では直ちに `lib.delete_engine()` を実行します（`strata_cli/update_cmd.py:378-400`）。従って `--wait 0`、正の値、負の値のいずれも削除の待機時間・結果を変えません。`--json` / `--quiet` は one-shot parser 群に後付けされる出力 option であり、待機処理を追加しません（`strata_cli/cli.py:508-515`）。

## 適用条件と副作用

削除処理は component folder の update lock を取り、対象 engine が導入済みか、使用中または実行中プログラムが使っていないかを確認します（`strata_control/engine_library.py:301-309`）。使用中の engine、または実行中プログラムが使う engine は削除できず、終了コード 2 のエラーになります。`--wait` による自動待機や再試行はありません。

削除できる場合、対象 folder を `.deleting-<識別子>` に rename してから削除し、Qwen engine では関連する previous / pinned 状態と履歴も更新します。モデルと設定、および別 family の engine は削除対象ではありません。ファイルが使用中などで rename に失敗すると終了コード 6 で失敗します。rename 後に個別ファイルの削除が失敗しても、その folder は残る場合があり、次回の削除処理で `.deleting-*` を掃除します（`strata_control/engine_library.py:310-334,341-348`）。

## 出力とエラー

成功時は通常出力で削除した engine の版と解放サイズを表示します。JSON 出力では成功結果を含む JSON を出します（`strata_cli/update_cmd.py:395-400`）。使用中／未導入など `UpdateError` は通常出力なら stderr に `strata: ...` と表示し、機械可読出力なら `ok: false` の JSON を stdout に出します。終了コードは例外に設定された値です（`strata_cli/update_cmd.py:237-242,307-311`; `strata_control/engine_library.py:305-316`）。

## 根拠

- parser 定義と remove の登録: `strata_cli/update_cmd.py:47-56,88-91`
- 値の Context への格納とコマンド振り分け: `strata_cli/update_cmd.py:244-256,272-273`
- remove が待機 helper を通らず削除へ進む箇所: `strata_cli/update_cmd.py:378-400`
- 共通 `--json` / `--quiet` の追加: `strata_cli/cli.py:508-515`
- 削除可否、rename と状態更新: `strata_control/engine_library.py:167-176,294-334`
- 削除後の残留 directory 掃除: `strata_control/engine_library.py:341-348`
