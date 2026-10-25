# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets rename` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json`。省略時は `human` |

## 役割

名前を変更したプリセットの成功結果を、人向けテキストまたは JSON で標準出力へ出します。rename の操作そのもの（対象の解決、名前の検証、保存方法）は出力形式で変わりません。

## 使い方

```sh
strata presets rename <プリセット名またはID> "新しい名前" --output json
```

人向け出力が必要なら `--output` を省略するか、`--output human` を指定します。`rename` は `strata presets` の必須サブコマンドの一つで、位置引数 `preset` と `name` を取ります（`strata_cli/tune_commands.py:49-67`）。

## 値と既定値

parser は `choices=("human", "json")`、`default="human"` で定義しています。別名や省略値の自動検出はありません（`strata_cli/tune_commands.py:53-55`）。`human` / `json` 以外の値は argparse が拒否します。トップレベルでは parser 実行時に引数を解析し、未知の引数もエラーにします（`strata_cli/cli.py:2223-2231`）。

## 実行時の動作

`presets_command` は `a.output == "json"` を機械可読モードとして扱い、`rename` 分岐で `presets.rename(a.preset, a.name)` を呼び出します（`strata_cli/tune_commands.py:289-293,314-316`）。

対象は完全な ID、4文字以上の ID prefix、または大文字小文字を区別しない完全一致の名前で指定できます。名前一致があれば prefix より優先されます。該当なし、または複数一致の場合は拒否します（`strata_control/presets.py:218-231`）。

新しい名前は前後空白を除去してから検証され、空文字、80文字超、改行（CR/LF）または NUL を含む値は拒否されます。同じ名前（大文字小文字を無視）が別プリセットに使われている場合も拒否されます（`strata_control/presets.py:255-256,361-367`）。有効な場合、対象 ID の JSON ファイルに名前を保存し、更新後のプリセットを返します（`strata_control/presets.py:368-371`）。

`--output json` の成功時は `schema_version: 1`、`ok: true`、`preset`（`id`、`name`、active 状態などを含む要約）を含む JSON オブジェクトを標準出力へ1行で出します。`human`（既定）の成功時は `Renamed to '<名前>'.` を出します（`strata_cli/tune_commands.py:95-100,314-316,351-358`）。

## 適用条件と副作用

名前変更は保存済みプリセットのメタデータだけを更新します。プリセットの設定を実行したり、有効化・解除したりはしません。データは `STRATA_PRESET_DIR` が設定されていればそのディレクトリ、未設定ならプロファイルディレクトリの親にある `presets/` に置かれます（`strata_control/presets.py:45-50`）。保存時は同じディレクトリに一時ファイルを書き、置換します（`strata_control/presets.py:53-68,361-371`）。

## 出力とエラー

プリセット不存在・参照名の曖昧さ・新しい名前の不正・名前重複は `PresetError` となり、JSON モードでは `ok: false` とエラー情報を標準出力へ、人向けモードでは `strata: <理由>` を標準エラーへ出し、終了コード `5` を返します（`strata_cli/tune_commands.py:103-108,344-345`）。ファイル等の `OSError` は通常終了コード `2` で同様に報告します（`strata_cli/tune_commands.py:346-347`）。不正な `--output` 値は rename 処理に入る前に argparse が拒否します。

## 根拠

- `strata_cli/tune_commands.py:49-67` — `presets` / `rename` の parser 階層、位置引数、子コマンド共通の `--output` 定義。
- `strata_cli/tune_commands.py:95-108,289-316,344-347,351-358` — 出力形式、rename 呼び出し、成功応答、失敗応答と終了コード。
- `strata_control/presets.py:45-68,218-231,255-256,361-371` — 保存先、参照方法、名前 validation、重複確認、JSON 更新。
- `strata_cli/cli.py:487,2151-2152,2223-2231` — parser 登録、トップレベル dispatch、引数解析と未知引数の扱い。
