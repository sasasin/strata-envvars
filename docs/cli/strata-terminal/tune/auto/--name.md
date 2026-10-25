# `--name`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune auto` |
| オプション | `--name` |
| 別名 | なし |
| 値 | preset 名を表す文字列。必須値 |

## 役割

自動チューニング結果を保存するときの preset 名を指定します。名前は表示・検索に使われ、測定する設定や preset の適用枠を決める値ではありません。

## 使い方

```sh
strata tune auto my-profile --name "Coding on this PC"
```

`my-profile` は対象の保存済み profile 名または run configuration（JSON）です。

## 値と既定値

- 値を取るオプションです。parser には `choices`、型変換、必須指定がなく、既定値は `None` です。値を省略すると、preset 作成時にモデルまたは量子化名、context、目的（`Work` / `Full speed`）から名前を組み立てます。context が不明なら `?` を使います。
- `--name ""` のように空文字列を渡した場合も、保存処理の `name or default_name(...)` により既定名になります。
- `strata tune auto` の保存経路には名前の長さ・改行・NUL などの検証はありません。重複名は大文字小文字を区別せず判定し、既存名に一致すれば ` (2)`、` (3)` などを付けて一意化します。

## 実行時の動作

parser が値を `a.name` に格納し、チューニング本体はこの値を測定設定に含めません。結果が `improved` または `default_confirmed` で、かつ `--no-save` が指定されていない場合に限り、`presets.create(..., name=a.name, mode=a.mode)` へ渡します。それ以外の結果では preset は作成されず、名前も使われません。

作成された preset は既定で直ちに有効化されます。同一 slot の以前の active preset は履歴に残ります。slot はモデル digest、context、KV 形式、vision、目的から作られ、名前は slot 判定に含まれません。保存したチューニング設定は `strata launch` などの起動時に適用されます。

## 適用条件と副作用

このオプション単独ではファイルや設定を変更しません。上記の保存条件を満たすと、共用 preset store（profiles の隣にある `presets/`）へ JSON preset と active index が書き込まれ、同じ slot で前に有効だった preset が履歴に入ります。`--no-save` はこの保存・有効化を抑止します。

名前指定による preset 作成が安全設定の検査に失敗すると、`PresetError` の文面は結果の notes に追加されます。CLI は preset を `null` として結果を出力し、測定結果に応じた終了コードを返します。parser レベルで不正な名前を拒否する経路は確認できません。

## 出力とエラー

人向け出力では保存した preset 名が結果文に表示され、JSON 出力では `result.preset.name` と `result.values.preset_name` に入ります。preset を保存できなかった場合は両方とも `null` です。通常の preset 作成時、重複名だけを理由としたエラーはなく、名前に番号が付加されます。

## 根拠

- `strata_cli/tune_commands.py:20-46` — `auto` parser の位置引数、`--name` の既定値・宣言、隣接する `--no-save`。
- `strata_cli/tune_commands.py:246-261` — 保存条件、`a.name` の引き渡し、preset 作成エラーの扱い、human/JSON 出力と終了コード。
- `strata_control/presets.py:120-125` — 既定名の組み立て。
- `strata_control/presets.py:128-131` — preset slot の構成要素（名前を含まない）。
- `strata_control/presets.py:255-265,268-307` — 大文字小文字を区別しない重複判定、連番付与、名前の保存、作成後の既定有効化。
- `strata_control/presets.py:310-325` — active preset の更新と以前の preset の履歴保持。
- `strata_cli/launch/runner.py:1-11` — チューニング結果を共有 preset store に保存し、起動ごとに適用する旨。
