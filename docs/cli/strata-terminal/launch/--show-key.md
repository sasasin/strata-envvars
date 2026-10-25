# `strata launch --show-key`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--show-key` |
| 別名 | なし |
| 値 | 取らないフラグ。指定すると有効（既定値は `False`）。 |

## 役割

保存 preset または稼働中の `strata launch` から API key を取得して表示します。キーが存在しない共有設定では利用できません。API key は接続資格情報なので、表示結果を端末ログ、共有画面、シェルの記録などに残さないよう扱ってください。

## 使い方

```sh
# 稼働中 launch のキーを表示
strata launch --show-key

# Office preset のキーを表示（稼働中でなくても保存 preset を参照）
strata launch --show-key --preset Office
```

## 値と既定値

`argparse` の `store_true` フラグです。値は不要で、既定値は `False` です。値の形式や範囲検証はありません。`--preset` は任意で名前を取ります。オプション同士の排他制約は parser では設定されていません。

## 実行時の動作

- `--preset NAME` がある場合、稼働中 launch の一覧から名前を `settings.slug()` で正規化した ID と一致するものを探します。一致がなくても、同名の保存 preset があればその preset のキーを使います。そのため、この形式はサーバーが稼働していなくても保存キーを表示できます。
- `--preset` がない場合、稼働中 launch の先頭を選びます。稼働中 launch がなければ表示対象はありません。
- 稼働中 launch が選ばれると、その launch の source config JSON から `api_key` を読みます。ファイルを読めない場合や JSON が不正な場合は空設定として扱い、キーを取得できません。config の値が空または文字列 `none`（前後空白を除き大文字小文字を無視）なら、指定 preset がある場合は保存 preset のキーへフォールバックします。
- キーが得られた場合、キーだけを標準出力へ出して終了コード `0` で戻ります。サーバーの起動・停止や preset の更新は行いません。
- 管理フラグが複数指定された場合、`--list-presets`、`--delete-preset`、`--stop`、`--status` の分岐が `--show-key` より先に処理されます。parser は併用を拒否しないため、これらと一緒に指定すると先行する管理操作が実行され、キー表示には進まないことがあります。

## 適用条件と副作用

対象は Terminal CLI の `strata launch` です。同じ表記の `strata connect --show-key` は別 parser・別コマンドのオプションであり、この文書の対象外です。

この分岐は preset と launch 状態・source config を読み取ります。キーを取得できない場合、通常形式では `strata: There is no API key for that launch.` を標準エラーへ出し、終了コード `5` で戻ります。`--preset` を省略した場合はメッセージ末尾に preset 名を指定する案内が付きます。指定名について稼働中 launch と保存 preset のどちらも見つからない場合も同じ失敗経路です。保存 preset が破損して読み込めない場合は `PresetError` として処理され、通常形式ではその内容を標準エラーへ出して終了コード `2` になります。

## 出力とエラー

成功時は `_say()` がキーを標準出力へそのまま書き出します。`--output json` を併用しても成功出力は JSON 化・マスキングされず、キーの平文が出ます。キーがない場合は、`--output json` により `{"schema_version":1,"ok":false,"error":{"code":5,"message":"..."}}` 形式の JSON を標準出力へ出します（終了コード `5`）。スクリプトで JSON 出力を期待する場合も成功時と失敗時の形式が異なるため注意してください。

## 根拠

- `strata_cli/launch/cmd.py:141-146` — `launch` 管理 parser における `--show-key` の `store_true` 定義と説明。`strata_cli/launch/cmd.py:148-165` は同名の `connect` フラグが別 parser にあることを示します。
- `strata_cli/launch/cmd.py:416-418` — `_say()` は標準出力へ行を書き出します。
- `strata_cli/launch/cmd.py:567-592` — 稼働中 launch の列挙、対象条件、source config の参照元。
- `strata_cli/launch/cmd.py:605-627` — preset 名の slug 照合、保存 preset への fallback、config/preset の API key 選択。
- `strata_cli/launch/cmd.py:630-641,643-677` — 管理分岐の優先順、キー表示・キーなしエラー、JSON エラー形式と終了コード。
- `strata_cli/launch/cmd.py:832-837` — preset 読み込み等の `PresetError` / `ValueError` と中断時の失敗処理。
- `strata_cli/launch/store.py:88-103` — 保存 preset の読み込み、見つからない場合・破損時の挙動。
- `strata_cli/launch/settings.py:310-315` — preset 名と稼働中 launch 名の slug 正規化。
