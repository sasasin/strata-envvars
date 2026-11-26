# `--output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets show` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

保存済みチューニング preset 1件の表示形式を選びます。`human` は preset 全体を整形した JSON として表示し、`json` は機械処理向けの `schema_version` / `ok` を含む JSON エンベロープで表示します。

## 使い方

```sh
# preset 名または ID を指定し、人向けの表示を得る（既定）
strata presets show "My preset"

# 同じ preset を機械処理向けの JSON エンベロープで表示する
strata presets show --output json 1a2b
```

`preset` には完全な ID、4文字以上の ID prefix、または大文字小文字を区別しない完全一致名を指定できます。

## 値と既定値

- parser は `choices=("human", "json")` を指定し、既定値を `human` としています。短縮別名はありません。
- `show` の引数 `preset` は必須です。
- `--output` に他の値を渡すと `argparse` の選択肢検証で拒否されます。処理本体に進む前の parser エラーです。

## 実行時の動作

- `human` の場合、`presets.find()` が見つけた preset の辞書を、インデント付き JSON として stdout に出します。
- `json` の場合、stdout に `{"schema_version":1,"ok":true,"preset":...}` 形式の JSON を1行出します。`preset` は一覧用の要約ではなく保存データ全体です。
- preset の解決では完全 ID が最初に照合され、続いて ID prefix（4文字以上）と大文字小文字を区別しない完全一致名が調べられます。同名が複数ある場合は名前一致を優先し、該当候補が複数なら失敗します。
- `find()` は preset ディレクトリ内の JSON を読み込み、`active.json` の active ID を参照して返却データに `active` を付与します。保存先は `STRATA_PRESET_DIR` が設定されていればその値、未設定なら profiles ディレクトリの隣の `presets` です。
- このコマンド経路は表示のために保存データを読むだけで、preset の書き換え、モデル起動、ネットワーク処理は行いません。

## 適用条件と副作用

出力形式の違いは標準出力だけです。preset ディレクトリと active index を読み取ります。ディレクトリが存在しない、または読み込める preset がない場合、指定した ID・名前は見つからずエラーになります。不正 JSON や現行 schema と異なる preset ファイルは一覧対象から除外されます。

## 出力とエラー

- 成功時の出力先は stdout です。`human` も JSON 文字列を整形表示するため、両形式とも内容自体は JSON です。
- preset が見つからない場合は終了コード `5`。`human` では `strata: ...` を stderr に出し、`json` では `{"schema_version":1,"ok":false,"error":{"code":5,"message":"..."}}` を stdout に出します。
- 名前または prefix が複数 preset に一致する場合も終了コード `5` となり、ID を使うよう促すエラーになります。
- preset ディレクトリ等の I/O エラーは、捕捉された `OSError` として終了コード `2` で報告されます。`json` ではエラーエンベロープ、`human` では stderr へのメッセージです。
- 無効な `--output` 値など parser エラーは `presets_command()` のエラーハンドラより前に発生します。

## 根拠

- `terminal/strata_cli/tune_commands.py:55-68` — `presets show` の階層、共通 `--output` 登録、値の選択肢と既定値、必須の `preset` 引数。
- `terminal/strata_cli/tune_commands.py:101-114` — 成功時の human / JSON 出力と失敗時の stderr / JSON エンベロープ。
- `terminal/strata_cli/tune_commands.py:472-493` — `show` の分岐、preset 検索、全データ表示、出力形式の選択。
- `terminal/strata_cli/tune_commands.py:527-530` — `PresetError` の終了コード `5` と I/O・値エラーの終了コード処理。
- `terminal/strata_cli/cli.py:515`、`terminal/strata_cli/cli.py:2229-2230` — parser への presets 登録とコマンド処理へのディスパッチ。
- `terminal/strata_control/presets.py:45-50` — preset ディレクトリの決定方法。
- `terminal/strata_control/presets.py:71-75`、`terminal/strata_control/presets.py:236-256`、`terminal/strata_control/presets.py:259-277` — JSON 読み込み、ID/name 解決、無効 schema の除外、active 状態の付与。
