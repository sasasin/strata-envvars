# `strata components remove --wait`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components remove` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒数を表す浮動小数点数。parser に追加の範囲検証はない |

## 役割

このコマンドでは `--wait` は parser に登録され、ヘルプ文も「エンジンが serving 中なら停止まで待つ」と説明します。しかし `remove` の処理はこの値を待機処理へ渡さず、削除処理も参照しません。そのため、このコマンドで `--wait` を指定しても待機時間は変わりません。削除対象が現在使用中なら、待たずに拒否されます。

## 使い方

```sh
# 構文例。実行すると指定したインストール済みエンジンを削除する。
strata components remove 0.1.54 --wait 30
```

`0.1.54` は構文例です。実際に実行する場合は `strata components engines` で対象を確認してください。`--wait` は削除の待機を有効にしません。

## 値と既定値

`--wait` は `type=float`、既定値 `None`、値の metavar は `SECONDS` です。CLI は値を `a.wait or 0.0` として共通の更新 context に格納します。`remove` 専用の正数・有限値などの範囲検証はありません。数値に変換できない値は argparse の引数エラーになります。

## 実行時の動作

`update_cmd._common()` が `--wait` を `remove` parser に登録します。実行時には `run()` が値を context に格納し、`_engines_command()` に分岐しますが、`remove` の分岐では `lib.delete_engine()` を直接呼びます。`rollback`、`use` などが呼ぶ `_maybe_wait()` は `remove` 分岐では呼ばれません。また `delete_engine()` 内にも `ctx.wait` や `wait_until_idle()` の参照はありません。したがって省略・指定のどちらでも待機動作はありません。共通 parser のヘルプ文はこの `remove` の実際の動作と一致しません。

削除 helper はインストール済み一覧から対象を特定し、現在選択中のエンジン、または実行中プログラムが使用しているエンジンを拒否します。削除可能な場合は対象ディレクトリを `.deleting-<乱数>` に rename してから削除し、Qwen 系または shape 専用エンジンの state に必要な履歴等を保存します。モデルや設定ファイル自体は削除対象ではありません。

## 適用条件と副作用

`--wait` による適用条件や副作用はありません。削除成功時にはエンジンのファイルが削除されます。現在選択中のエンジンや稼働中プログラムが使うエンジンは削除できません。ディレクトリ rename が失敗した場合は削除を中断し、何も変更しなかった旨をエラーに含めます。ファイルが使用中で rename 後の削除に残った場合、`.deleting-*` は次回の削除時にも掃除されます。

## 出力とエラー

成功時は通常出力に削除したエンジンの版と解放容量を表示し、`--output json` または `jsonl` では成功結果を JSON で出力します。対象が見つからない、対象を削除できない場合は `UpdateError`（終了コード 2）、rename 時の OS エラーは終了コード 6 になります。通常モードでは `strata: ...` を stderr に出し、JSON 系出力ではエラーコードとメッセージを含む JSON を出します。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56` — 共通 parser が `--wait` を浮動小数点数、既定値 `None` で登録し、serving 中の待機と説明。
- `terminal/strata_cli/update_cmd.py:88-91` — `remove` parser に位置引数 `engine` と共通オプションを登録。
- `terminal/strata_cli/update_cmd.py:314-321` — `a.wait or 0.0` を共通 context に格納。
- `terminal/strata_cli/update_cmd.py:337-338,445-497` — `remove` を `_engines_command()` に渡し、削除分岐から直接 `delete_engine()` を呼ぶ。`_maybe_wait()` は `use` 分岐にのみ呼ばれる。
- `terminal/strata_control/engine_library.py:139-149` — 現在使用中または実行中プログラムが使う対象を削除不可にする判定。
- `terminal/strata_control/engine_library.py:317-366` — 対象確認、ディレクトリ rename と削除、state 履歴保存、失敗時の例外。
- `terminal/strata_cli/update_cmd.py:307-312,374-378` — エラーの出力形式と終了コードの返却。
