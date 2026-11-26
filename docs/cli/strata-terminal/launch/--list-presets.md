# `strata launch --list-presets`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--list-presets` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`）。未指定時は `False` |

## 役割

保存済み launch preset を一覧表示する管理モードです。通常の guided setup やサーバー起動には進まず、一覧を出力して終了します。保存先は profiles ディレクトリに隣接する `launch-presets/` で、`STRATA_LAUNCH_PRESET_DIR` が設定されている場合はそのディレクトリです。

## 使い方

```sh
# 保存済み preset を人間向けの形式で表示
strata launch --list-presets

# 機械処理向け JSON で表示
strata launch --list-presets --output json
```

## 値と既定値

`--list-presets` 自体は値を取らず、既定値は `False` です。繰り返し指定や値の指定について個別の処理はありません。出力形式は同じ `launch` parser の `--output` で選択され、既定値は `human`、受理値は `human` または `json` です（`terminal/strata_cli/launch/cmd.py:154-156`）。

## 実行時の動作

`run_launch()` はこのフラグを検出すると `store.list_presets()` を呼び、通常の起動処理に進まず終了コード 0 を返します（`terminal/strata_cli/launch/cmd.py:766-782`）。preset は `STRATA_LAUNCH_PRESET_DIR` があればその値、なければ profiles の親ディレクトリにある `launch-presets/` から読みます（`terminal/strata_cli/launch/store.py:28-34`）。ディレクトリが存在しなければ空の一覧です。`.json` ファイルを読み込み、`last_used` または `created` の文字列が新しい順に並べます。読み込み時の `OSError` または JSON の `ValueError` が起きたファイルは一覧からスキップされます（`terminal/strata_cli/launch/store.py:128-150`）。

既定の human 出力では、preset ごとに名前、モデル、context、並列数（または `fit to card`）、tuning 状態、最終使用日時を表示します。空の場合は保存方法の案内を表示します（`terminal/strata_cli/launch/cmd.py:771-781`）。`--output json` では stdout に `schema_version: 1`、`ok: true` と `presets` 配列を含む JSON オブジェクトを出力します。各 preset の `api_key` は値そのものを出さず、設定済みなら文字列 `set`、未設定なら `null` です（`terminal/strata_cli/launch/cmd.py:768-770`; `terminal/strata_cli/launch/settings.py:161-165`）。

## 適用条件と副作用

一覧取得では preset ファイルを読み取るだけで、preset の保存・削除、モデルの変更、tuning、サーバー起動は行いません。preset ディレクトリがない場合もエラーにはならず空一覧として扱います（`terminal/strata_cli/launch/store.py:128-150`）。一覧結果は `last_used` / `created` の文字列の降順です。時刻文字列の形式が異なる場合の意味的な時系列比較までは、この並べ替え処理からは保証できません。

## 出力とエラー

human 出力は stdout に書き込まれます（`terminal/strata_cli/launch/cmd.py:495-497, 771-781`）。JSON を選んだ場合も成功オブジェクトを stdout に出します（`terminal/strata_cli/launch/cmd.py:768-770`）。個々の preset ファイルが読めない、または JSON として壊れている場合は、そのファイルを飛ばして残りを表示します（`terminal/strata_cli/launch/store.py:139-150`）。ディレクトリの列挙自体に失敗した場合は `is_dir()` が false となるか、キャッシュ用の走査キーが `None` となり、実装上は結果が空になる場合があります（`terminal/strata_cli/launch/store.py:119-150`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:73-80, 155-156` — `launch` parser と `--list-presets` の引数定義、`--output` の選択肢・既定値。
- `terminal/strata_cli/launch/cmd.py:753-782` — 一覧モードの分岐、human / JSON 出力、終了コード。
- `terminal/strata_cli/launch/store.py:28-34, 119-150` — preset 保存先、読み込み・キャッシュ・破損ファイルのスキップ・並べ替え。
- `terminal/strata_cli/launch/settings.py:161-165` — JSON で API key の値を伏せる変換。

