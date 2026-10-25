# `--model`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets list` |
| オプション | `--model` |
| 別名 | なし |
| 値 | 任意の文字列。parser に型・選択肢・形式の制約はない |

## 役割

保存済み tuning preset の一覧を、preset の選択情報（model、quant など）に指定文字列を含むものへ絞り込みます。preset 名だけを検索するオプションではありません。

## 使い方

```sh
strata presets list --model Q4_K
```

`--model` を省略すると、保存済み preset を絞り込まずに一覧します。出力形式を選ぶ場合は同じコマンドに `--output human|json` を指定できます。

## 値と既定値

- 値は1つの文字列で、省略時は `None` です。この場合フィルターを適用しません。
- 大文字小文字を区別しない部分一致です。実装は各 preset の `choices` を JSON 文字列化し、その中に検索文字列があるかを調べます。そのため model 名や quant だけでなく、`choices` 内の他の値にも一致する可能性があります。
- 空文字列は parser に拒否されません。実装上は空文字列が偽として扱われるため、絞り込みを行いません。
- `--model` を複数回指定した場合は argparse の通常動作で最後の値が使われます。

## 実行時の動作

`strata presets list` は preset 保存ディレクトリにある `*.json` を読み、schema が `strata.preset/1` のものを対象にします。`active.json` は一覧項目から除外されます。`--model` を指定した場合は各 preset の `choices` の JSON 表現に対して部分一致フィルターを行い、結果を `created_epoch` の降順に並べます。これは読み取り処理で、preset や active index を更新せず、モデルエンジンも起動しません。

保存先は環境変数 `STRATA_PRESET_DIR` が設定されていればそのパス、未設定なら profile directory の隣にある `presets/` です。保存ディレクトリが存在しない場合は空の一覧になります。

人向け表示では active 状態、ID の先頭8文字、名前、計測 gain、回答 class を表示します。一致する preset がない場合は空の一覧と `No saved presets yet...` の案内を表示します。JSON 表示は preset の summary 一覧を `presets` に格納します。

## 適用条件と副作用

このオプションは `strata presets list` のみに属し、別コマンドの同名オプションとはスコープが異なります。副作用は preset store の読み取りです。preset ディレクトリ内の不正 JSON、JSON として読めないファイル、schema が一致しないファイルは一覧から除外されます。

## 出力とエラー

- 既定の `--output human` は一覧または空一覧の案内を標準出力へ表示し、成功時の終了コードは `0` です。
- `--output json` は `schema_version: 1`、`ok: true`、`presets` を含む JSON を標準出力へ1行で表示します。
- ディレクトリ走査などで `OSError` / `ValueError` が発生した場合、コマンド handler が捕捉します。human では `strata: <message>` を標準エラーへ出し、JSON では `ok: false` のエラー JSON を標準出力へ出します。既定の終了コードは `2` です。
- `--model` に値を付けない場合や、`--output` に `human` / `json` 以外を指定した場合は argparse が usage とエラーを標準エラーへ表示し、終了コード `2` で終了します。

## 根拠

- `strata_cli/tune_commands.py:49-58` — `presets list` parser、共通 `--output`、`--model` の既定値と help。
- `strata_cli/tune_commands.py:95-108,289-300,344-348` — human/JSON の出力、一覧処理の呼び出し、例外の出力と終了コード。
- `strata_control/presets.py:45-50,71-75` — preset 保存先と JSON 読み取り時のエラー処理。
- `strata_control/presets.py:234-252` — ファイル選択、schema 判定、`--model` のフィルター、active 状態と並び順。
- `strata_cli/cli.py:487-488,2151-2153,2217-2231` — parser 登録、`presets` への dispatch、引数解析と parser error の処理。
- `docs/cli/README.md:832-838` — `strata presets list` の階層と `--model` の索引リンク。

調査範囲は上記 commit の Terminal CLI parser と preset 管理実装です。CLI help と配布済み Release artifact は補助資料として実行・検証していません。調査対象 Strata checkout は `main`（`origin/main` と同期）で、`git status --short --branch` に未コミット変更はありませんでした。
