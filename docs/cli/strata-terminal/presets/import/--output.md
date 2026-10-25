# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets import` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

インポート結果とエラーの表示形式を選びます。プリセットの読み込み・検証・保存方法は変えません。

## 使い方

```sh
strata presets import ./preset.json --output json
```

`file` はインポートするプリセット JSON のパスです。`--output` は `import` parser に登録されています（`strata_cli/tune_commands.py:76-78`）。

## 値と既定値

- 受理値は `human` と `json`、未指定時は `human` です（`strata_cli/tune_commands.py:53-55`）。
- `--json` の別名は定義されていません。
- 他の値や値なし指定は `argparse` の選択肢・引数エラーになります。実行処理へ進まず、標準エラーに usage とエラーを出して終了コード 2 となります（parser の構築と引数解析: `strata_cli/cli.py:40-45`, `strata_cli/cli.py:2223-2231`）。

## 実行時の動作

`presets_command` は `--output json` のときだけ機械可読出力モードにし、`human` では通常の表示を選びます（`strata_cli/tune_commands.py:289-293`）。成功時の人向け表示は標準出力に `Imported '<名前>'. Apply it with: strata presets apply <ID>` と出ます。JSON 時は `schema_version: 1`、`ok: true`、`preset`（ID、名前、設定概要など）を含む JSON オブジェクトを標準出力に出します（`strata_cli/tune_commands.py:95-100`, `strata_cli/tune_commands.py:338-341`, `strata_cli/tune_commands.py:351-358`）。

この option は出力形式だけを切り替えます。入力ファイルを UTF-8 BOM 付きも許容する `utf-8-sig` で読み、JSON として解析したあと `presets.import_preset` に渡します（`strata_cli/tune_commands.py:338-341`）。プリセットの schema と安全規則を検証し、新しい ID を割り当て、名前が重複すれば一意な名前にし、非アクティブ状態でプリセット保存先へ書き込みます。保存は一時ファイルを使った atomic replace です。インポートだけでは有効化されず、成功メッセージにある `strata presets apply` で適用します（`strata_control/presets.py:45-68`, `strata_control/presets.py:396-409`）。

## 適用条件と副作用

インポート処理は `human` と `json` のどちらでも同じです。成功すればプリセットストアに新規 JSON ファイルを書き込みます。保存先は `STRATA_PRESET_DIR` が設定されていればそのディレクトリ、未設定ならプロファイルディレクトリの隣にある `presets/` です（`strata_control/presets.py:45-50`, `strata_control/presets.py:53-68`, `strata_control/presets.py:403-409`）。環境変数の詳細は本 option の対象外です。

## 出力とエラー

- schema 不一致や安全規則に合わない設定は `PresetError` となり、終了コード 5 です。ファイルの読み込み失敗や不正 JSON は `OSError` / `ValueError` として終了コード 2 です（`strata_control/presets.py:396-402`, `strata_cli/tune_commands.py:344-347`）。
- `human` では `strata: <エラー>` を標準エラーへ出します。`json` では `schema_version: 1`、`ok: false`、`error` を含む JSON を標準出力へ出します。どちらも上記の失敗コードを返します（`strata_cli/tune_commands.py:103-108`, `strata_cli/tune_commands.py:344-347`）。

## 根拠

- parser の値、既定値、`import` の位置引数: `strata_cli/tune_commands.py:49-78`
- 出力モードの選択と成功・失敗表示: `strata_cli/tune_commands.py:95-108`, `strata_cli/tune_commands.py:289-293`, `strata_cli/tune_commands.py:338-358`
- parser エラーの経路: `strata_cli/cli.py:40-45`, `strata_cli/cli.py:2223-2231`
- import の保存先・原子的書き込み・検証・新規保存: `strata_control/presets.py:45-68`, `strata_control/presets.py:396-409`
- 索引上のコマンド階層とリンク: `docs/cli/README.md:891-896`
