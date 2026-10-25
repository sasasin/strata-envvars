# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets undo` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

undo の結果を人向けの短い文、または機械処理向け JSON のどちらで標準出力へ出すかを選びます。この指定は undo 対象の選択やプリセット履歴の更新方法を変えません。

## 使い方

```sh
strata presets undo 0123abcd --output json
strata presets undo ignored --config my-profile --output human
```

`--config` を指定しない場合、位置引数 `preset` はプリセット参照またはスロットキーとして使われます。`--config` を指定する場合も位置引数は構文上必須ですが、処理では使われず、設定から特定したスロットが対象になります（`strata_cli/tune_commands.py:70-72,321-328`）。

## 値と既定値

`strata_cli/tune_commands.py` の `common()` が各 `presets` サブコマンドに `choices=("human", "json")`、`default="human"` で登録します。したがって省略時は `human` です。別名は登録されていません（`strata_cli/tune_commands.py:53-55,70-72`）。

choices 外の値は `argparse` が処理前に拒否し、usage とエラーを標準エラーへ出して終了コード 2 で終了します（`strata_cli/tune_commands.py:53-55`; parser 実行は `strata_cli/cli.py:2223-2231`）。

## 実行時の動作

`presets_command()` は `a.output == "json"` を出力モードとして使います。undo の場合、`--config` があればプロファイル名または run configuration を解決し、その設定の identity と選択項目からスロットキーを計算します。なければ位置引数をそのまま `presets.undo()` に渡します（`strata_cli/tune_commands.py:111-114,321-328`; スロットキー構成は `strata_control/presets.py:89-116,128-131`）。

`presets.undo()` は保存済み active index の履歴から直前の active preset に戻すか、履歴がなければ標準設定に戻して `active.json` を更新します。履歴の参照先 preset ファイルが存在しない場合は active を `None` にします。ファイル更新には一時ファイルと atomic replace を使います（`strata_control/presets.py:202-208,339-358,53-68`）。この変更は保存済みの有効 preset を切り替えるもので、実行中のモデル設定をその場で書き換える処理ではありません。

- `human`（既定）: 復元先があれば `Back to '<名前>'.`、標準設定なら `Back to the standard settings.` を標準出力へ出します。
- `json`: 標準出力へ `schema_version: 1`、`ok: true`、`active` を含む JSON を出します。`active` は復元 preset の要約、標準設定の場合は `null` です（`strata_cli/tune_commands.py:95-100,328-330`）。

## 適用条件と副作用

`--output` は成功・失敗とも表示形式のみを選びます。undo の永続的な副作用は preset store の `active.json` の更新です。store は `STRATA_PRESET_DIR` があればそのディレクトリ、なければ profile ディレクトリの隣の `presets/` です（`strata_control/presets.py:45-50,202-208,339-358`）。

`--config` による対象指定は undo 処理にだけ関係します。`--output` が `--config` や位置引数の解釈、保存先を変える分岐はありません（`strata_cli/tune_commands.py:321-330`）。この parser に `--json` alias は追加されていません。one-shot 共通の `--json` は `strata_cli/cli.py:508-515` の登録対象一覧に presets を含みません。

## 出力とエラー

- human mode の成功結果は標準出力、失敗メッセージは `strata: ...` の形式で標準エラーに出ます。
- JSON mode の成功時は `schema_version: 1`, `ok: true` を含む JSON を標準出力へ出し、失敗時も `schema_version: 1`, `ok: false`, `error` を含む JSON を標準出力へ出します（`strata_cli/tune_commands.py:95-108,344-347`）。
- 「undo するものがない」等の `PresetError` は終了コード 5 です。その他の `OSError` / `ValueError` は通常終了コード 2（例外に `exit_code` があればその値）です（`strata_control/presets.py:346-348`; `strata_cli/tune_commands.py:344-347`）。
- `--output` の値が不正な場合は command 処理に入る前の argparse エラーです。`--config` の解決失敗、プリセット参照エラー、store 更新エラーは処理中の失敗経路になります（`strata_cli/tune_commands.py:321-347`; `strata_cli/cli.py:2223-2231`）。

## 根拠

- `strata_cli/tune_commands.py:49-80` — `presets undo` parser と共通 `--output` 定義、値の choices と既定値。
- `strata_cli/tune_commands.py:95-114,289-348` — 成功・失敗の出力、undo 分岐、`--config` の適用、例外処理。
- `strata_control/presets.py:45-68,89-131,202-215,339-358` — store の場所、config 由来の slot、index 読み書き、undo 履歴更新。
- `strata_cli/cli.py:2223-2231` — parser 実行と argparse の未認識引数経路。

調査範囲は上記 commit の checkout 内ソースです。同一 revision の CLI help や Release 配布物との照合は行っていません。
