# `strata tune auto --name`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--name` |
| 別名 | なし |
| 値 | 値必須の文字列。指定値の形式・長さを parser では制限しない |

## 役割

チューニング結果を保存するときの preset 名を指定します。preset は保存後ただちに該当する設定枠で有効になります。測定名や作業ディレクトリ名を指定するオプションではありません。

## 使い方

```sh
strata tune auto qwen/IQ3_S --name 'Qwen daily use'
```

対象はインストール済みモデル、保存済み profile、または実行設定 JSON です。`--name` の値を一つの引数として渡します。

## 値と既定値

- 省略時は、対象の量子化名（なければモデル名）、コンテキスト長（不明なら `?`）、希望（`Work` または `Full speed`）から名前を作ります。例: `IQ3_S 32K – Full speed`。
- 空文字列を明示した場合も、保存時の `name or default_name(...)` により自動生成名になります。空白だけの文字列は空とは判定されず、そのまま名前として扱われます。
- 同名判定は大文字小文字を区別しません。重複すると ` (2)`、` (3)` のような番号を付けた名前を選びます。
- `--name` 専用の長さ・文字種 validation はありません。parser で値を省略すると argparse の引数エラーになります。

## 実行時の動作

parser は `default=None` で値を受け取り、通常の tuning 実行で結果を保存する際に `presets.create(..., name=a.name, ...)` へ渡します。明示名がなければ前述の既定名を採用します。preset の ID は別途生成され、名前は一覧表示や名前による検索に使われます。

保存が試みられるのは結果が `improved` または `default_confirmed` で、かつ [`--no-save`](--no-save.md) が付いていない場合だけです。`--plan` は計画を出して tuning を始めずに return するため、名前は保存にも計画出力にも使われません。保存された preset は既定で有効化され、同じ設定枠ですでに有効な preset があれば履歴に残して置き換えます。

名前を含む preset JSON は preset 保存先に書かれ、active 状態は `active.json` に記録されます。保存先は `STRATA_PRESET_DIR` が設定されていればそのディレクトリ、なければ profile ディレクトリの隣の `presets/` です。

## 適用条件と副作用

`--name` 自体は tuning の探索条件や結果の採否を変えません。名前は保存対象の preset にだけ付きます。preset 作成は結果 JSON 等とは別にファイルを書き込み、通常は preset を有効化します。`--no-save` を指定した場合や保存対象外の結果ではこのオプションの値は使用されません。

## 出力とエラー

人間向け出力では、改善結果に保存名があれば `saved as '<name>'` と表示されます。JSON 出力の結果には `preset.name` と `values.preset_name` が含まれます。preset 作成で `PresetError` が発生した場合は例外文を結果の note に追加して処理を続けるため、名前 validation エラーを返す専用経路はありません。成功・失敗の最終的な終了コードは tuning 結果に基づきます。

## 根拠

- `terminal/strata_cli/tune_commands.py:21-50` — `strata tune auto` parser と `--name` の既定値。
- `terminal/strata_cli/tune_commands.py:349-353` — `--plan` が計画出力後に終了する経路。
- `terminal/strata_cli/tune_commands.py:402-425` — 保存条件、`a.name` の受け渡し、PresetError の扱い、出力と終了コード。
- `terminal/strata_control/presets.py:45-50` — preset 保存先。
- `terminal/strata_control/presets.py:120-125` — 既定名の構成。
- `terminal/strata_control/presets.py:280-290` — 大文字小文字を無視した重複判定と番号付け。
- `terminal/strata_control/presets.py:293-334` — 保存データへの名前設定と preset ファイル作成。
- `terminal/strata_control/presets.py:337-353` — preset の有効化と active index の更新。
- `terminal/strata_control/tune_report.py:58-92` — 保存名を tuning report に含める処理。
