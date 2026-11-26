# `strata presets list --model`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets list` |
| オプション | `--model` |
| 別名 | なし |
| 値 | 任意の文字列。model の部分名・quant 名などの検索語 |

## 役割

保存済みの tuning preset 一覧を絞り込みます。指定した文字列を preset の選択情報に含む項目だけを表示します。プリセットの適用や変更は行いません。

## 使い方

```sh
# 選択情報に IQ3_S を含む保存 preset を表示
strata presets list --model IQ3_S

# JSON 形式で検索結果を取得
strata presets list --model qwen --output json
```

## 値と既定値

`--model` は `strata presets list` 専用の引数で、値を1つ取ります。既定値は `None` で、この場合は絞り込みません。任意の文字列を受け付け、空文字列も parser 上は拒否されませんが、実装では空文字列を未指定と同様に扱うため全件が対象になります。大文字小文字を区別しない部分一致です。形式や文字種の追加検証はありません。複数回指定した場合は `argparse` の通常の単一値引数として最後の値が使われます。

## 実行時の動作

parser は `presets list` の共通 `--output` とともに `--model` を登録し、実行分岐はその値を `presets.list_presets(model=a.model)` に渡します（`terminal/strata_cli/tune_commands.py:55-65`, `472-483`）。一覧処理は preset ディレクトリ内の `*.json` を読み、`active.json` として予約されたファイル、JSON として読めないファイル、`strata.preset/1` 以外の schema を持つファイルを除外します（`terminal/strata_control/presets.py:71-75`, `236-240`, `259-276`）。

指定値は各 preset の `choices` 全体を JSON 文字列化した内容に対し、大文字小文字を無視した部分文字列検索として適用されます（`terminal/strata_control/presets.py:269-274`）。help は「model または quant に含む」と説明していますが、現行実装は `choices` 内の特定フィールドだけには限定しません。たとえば `model_file` など別の選択値に一致しても結果に含まれます。逆に、preset 名や測定値など `choices` の外側にある値は検索対象ではありません。

検索結果には active 状態を付け、作成時刻の降順で返します。人間向け出力では各 preset の active 印、ID の先頭8文字、名前、gain、回答クラスを表示します。該当項目がない場合は、保存 preset がない場合と同じ `No saved presets yet. Run: strata tune auto <profile>` という案内が出ます（絞り込み後の不一致でもこの文面です）。JSON 出力では `presets` 配列に要約を格納し、共通出力処理が `schema_version` と `ok` を付けます（`terminal/strata_control/presets.py:259-277`, `terminal/strata_cli/tune_commands.py:101-106`, `472-483`, `534-541`）。`--output` の既定は `human`、選択可能値は `human` と `json` です（`terminal/strata_cli/tune_commands.py:59-64`）。

## 適用条件と副作用

対象は `strata presets list` のときだけです。同じ文字列 `--model` は別コマンドにもありますが、ここでは `presets/list` の索引スコープに従います（`docs/cli/README.md:767-771`）。プリセット保存先は `STRATA_PRESET_DIR` が設定されていればそのパス、そうでなければ profile ディレクトリの隣の `presets` です（`terminal/strata_control/presets.py:45-50`）。一覧取得は保存データを読み出すだけで、エンジン起動、preset の変更、ファイル書き込みは行いません。ディレクトリが存在しない場合は空一覧になります（`terminal/strata_control/presets.py:259-263`）。

## 出力とエラー

成功時は標準出力に人間向け一覧または JSON を出し、終了コード `0` を返します（`terminal/strata_cli/tune_commands.py:101-106`, `472-483`）。無効な指定値を独自に拒否する validation はありません。値を付け忘れた場合など parser が構文を受理できないときの表示・終了処理は `argparse` および CLI 共通処理に委ねられます（`terminal/strata_cli/cli.py:2325-2334`）。個別の preset JSON が読めない場合や schema が一致しない場合、そのファイルは一覧から静かに除外されます（`terminal/strata_control/presets.py:71-75`, `269-271`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:55-65` — `presets list` の parser、共通 `--output`、`--model` の既定値と help。
- `terminal/strata_cli/tune_commands.py:472-483` — `--model` を一覧関数へ渡す処理、人間向け・JSON 出力。
- `terminal/strata_control/presets.py:45-50`, `259-277` — 保存場所の決定、preset の読み込み・除外・部分一致・並べ替え。
- `terminal/strata_control/presets.py:71-75`, `236-240` — 不正 JSON や不正 schema の扱い。
- `terminal/strata_cli/cli.py:2325-2334` — parser 実行と共通の未認識引数処理。
- `docs/cli/README.md:767-771` — `strata presets list` の階層と対象文書リンク。
