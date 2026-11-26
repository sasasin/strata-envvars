# `strata presets export --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets export` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json`。省略時は `human` |

## 役割

export の結果通知と、処理失敗時のエラー表現を人向けまたは JSON にします。ただし、出力先を省略してプリセット本体を stdout に表示する経路は常に整形 JSON であり、`--output` の値では切り替わりません。

## 使い方

```sh
# JSON形式のプリセット本体を stdout に表示する（この経路では --output の指定は結果形式を変えない）
strata presets export "Preset name" --output json

# export ファイルを書き、成功通知を JSON にする
strata presets export "Preset name" --file ./preset-copy.json --output json
```

## 値と既定値

`human` と `json` のみ受け付けます。既定値は `human` です。値は `argparse` の choices で検証されるため、それ以外の値は parser エラーになります（`terminal/strata_cli/tune_commands.py:59-61`）。短縮別名はありません。

## 実行時の動作

この option は `presets` の各サブコマンドに共通登録されます。`export` はプリセット参照を位置引数に取り、任意の `--file` とともに `--output` を使えます（`terminal/strata_cli/tune_commands.py:55-61,79-81`）。

export 処理はまず ID・ID prefix・名前からプリセットを検索し、保存データから `active` フィールドを除いた内容を得ます（`terminal/strata_control/presets.py:243-256,417-420`）。`--file` が空でない場合、内容を UTF-8 のインデント付き JSON として指定先へ書き込みます。ファイルへの書き込み後、`human`（既定）なら `Wrote <path>` を表示し、`json` なら `{"schema_version":1,"ok":true,"file":"<path>"}` 形式の成功応答を stdout に表示します（`terminal/strata_cli/tune_commands.py:514-518,101-106`）。

`--file` を省略した場合はプリセット本体をインデント付き JSON として stdout に出して終了し、`--output human` と `--output json` のどちらでも同じ経路です（`terminal/strata_cli/tune_commands.py:514-520`）。

## 適用条件と副作用

`--output` 自体はプリセットや設定を変更しません。ファイル書き込みの副作用は `--file` を空でない値で指定したときに発生します。実装は `Path.write_text` を直接呼ぶため、指定先に既存ファイルがあれば内容を置き換えます。親ディレクトリの作成や一時ファイル経由の書き込みはこの処理にはありません（`terminal/strata_cli/tune_commands.py:514-518`）。

明示的に空文字列 `--file ""` を渡した場合は条件判定が偽になり、ファイルには書かず stdout 出力経路になります（同:517-520）。

## 出力とエラー

- 不明または曖昧なプリセット参照は stderr に `strata: ...` を出し、終了コード `5` になります。`--output json` の場合は stderr ではなく、`ok:false` と `error.code` / `error.message` を含む JSON を stdout に出します（`terminal/strata_control/presets.py:243-256`; `terminal/strata_cli/tune_commands.py:109-114,527-530`）。
- 出力先の書き込みに失敗した場合は `OSError` を捕捉し、同じ human/JSON エラー経路に入ります。終了コードは例外の `exit_code` 属性があればそれを使い、なければ `2` です（`terminal/strata_cli/tune_commands.py:517,529-530`）。
- `--output` に許可されていない値を指定すると parser が拒否します（`terminal/strata_cli/tune_commands.py:59-61`）。usage 表示とその場合の終了コードは Python `argparse` の処理に委ねられており、この Strata 側ソースだけから個別の出力文面は確認できません。

## 根拠

- `terminal/strata_cli/tune_commands.py:55-61,79-81` — `presets` 配下の共有 `--output` parser 定義と `export` の引数。
- `terminal/strata_cli/tune_commands.py:472-476,514-531` — 出力モードの判定、export の stdout/file 分岐、例外処理。
- `terminal/strata_cli/tune_commands.py:101-114` — 成功・失敗時の human/JSON 出力。
- `terminal/strata_control/presets.py:243-256,417-420` — 参照の解決と export データ（`active` を除去）の生成。
- `terminal/strata_cli/cli.py:514-515,2229-2230` — parser 登録と `presets_command` への dispatch。
- 索引 `docs/cli/README.md:804-808` — `presets/export` の階層と `--output` の掲載。索引上の scope と現行 parser 定義は一致。
