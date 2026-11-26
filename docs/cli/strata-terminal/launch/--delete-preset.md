# `strata launch --delete-preset`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--delete-preset` |
| 別名 | なし |
| 値 | プリセット名を1つ取る。parser 上の形式・長さ制限はない |

## 役割

保存済み launch preset を1件削除します。対象はプリセット用 JSON ファイルで、モデルファイルやチューニング結果には触れません。

## 使い方

```sh
strata launch --delete-preset "Office"
```

## 値と既定値

`NAME` は必須の位置値です。省略すると `argparse` が引数不足として終了します。値は `slug()` で小文字化し、英小文字・数字・`-`・`_` 以外をハイフンへ置き換え、先頭を英字にし、48文字までに切り詰めてファイル名に使います。そのため、異なる名前が同じ slug になることがあります。空文字列を明示すると `a.delete_preset` が偽となり削除分岐に入らず、通常の `strata launch` 処理へ進みます。

同じオプションを複数回指定した場合の parser 値は通常の `argparse` の扱いで最後の値です。既定値は `None` です。

## 実行時の動作

`strata launch` の管理操作分岐で `--list-presets` の後、`--delete-preset` の前にある停止・状態表示などより先に削除します。削除値と別の管理オプションを併用すると、一覧指定があれば一覧表示が優先され、それ以外では削除が停止・状態表示等より優先されます。

保存先は通常、プロファイル保存先の親にある `launch-presets/` です。`STRATA_LAUNCH_PRESET_DIR` が設定されていれば、そのディレクトリを使います。指定名を slug 化した `<slug>.json` が存在する場合に限り、そのファイルを削除します。プリセットファイルには API key を含む場合があります。削除成功時は stdout に完了文を出し、終了コード `0` を返します。

## 適用条件と副作用

対象パスに `Path.is_file()` が真を返さない場合は削除せず、未登録エラーになります。プリセット名は `slug()` で正規化されるため、記号・大文字小文字・長さの違いによって別の入力名が同じ保存ファイルを指す場合があります。保存先を切り替える場合は `STRATA_LAUNCH_PRESET_DIR` を確認してください。

副作用は指定されたプリセット JSON ファイルの削除です。モデルとチューニング結果は保持されます。ファイル削除時に `OSError` が発生すると CLI 共通処理に渡され、エラー出力と終了コード `6` になります。

## 出力とエラー

- 成功時: `Deleted the preset 'NAME'. Models and tuning results were not touched.` を stdout に出力し、`0` を返します。
- 対象がない場合: 利用可能なら近い名前、なければ保存済みの名前を添えたエラーを出し、終了コード `2` になります。
- `--output json` 併用時も成功メッセージは人向けの通常テキストです。一方、`PresetError` による失敗は JSON の `ok: false` エラーオブジェクトとして stdout に出力され、終了コード `2` です。ファイルシステムの `OSError` は CLI 共通のエラー経路で JSON 指定時は JSON 出力、終了コード `6` になります。

## 根拠

- `terminal/strata_cli/launch/cmd.py:155-159` — `--delete-preset NAME` の parser 定義と `--list-presets` 等との同じ管理 group。
- `terminal/strata_cli/launch/cmd.py:759-764` — `--output json` 時を含む `PresetError` 用エラー出力と終了コード。
- `terminal/strata_cli/launch/cmd.py:766-786` — 管理操作の分岐順、削除呼び出し、成功メッセージ。
- `terminal/strata_cli/launch/cmd.py:1009-1014` — `PresetError` と `ValueError` の失敗処理。
- `terminal/strata_cli/launch/store.py:28-37` — 保存先ディレクトリと `STRATA_LAUNCH_PRESET_DIR`、名前からファイルパスへの変換。
- `terminal/strata_cli/launch/store.py:153-157` — ファイル存在判定、未登録エラー、削除処理。
- `terminal/strata_cli/launch/settings.py:462-467` — プリセット名をファイル名へ変換する規則。
- `terminal/strata_cli/cli.py:2235-2237,2248-2265` — `strata launch` から実装への振り分けと、その他の `OSError` の終了コード・出力。
