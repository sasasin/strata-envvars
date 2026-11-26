# `strata presets apply --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets apply` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

プリセットを有効化する `strata presets apply` の結果を、人間向けテキストまたは機械処理向け JSON で表示します。`--output` は有効化の対象や設定内容を変えず、結果の形式を選びます。

## 使い方

```sh
strata presets apply preset-name --output json
```

`preset-name` はプリセットの正確な名前、ID、または4文字以上の一意な ID 接頭辞です。適用するプリセットを位置引数で指定します（`terminal/strata_cli/tune_commands.py:67-70`、`terminal/strata_control/presets.py:243-256`）。

## 値と既定値

- `--output` は値を1つ取り、`human` と `json` だけを受け付けます。既定値は `human` です（`terminal/strata_cli/tune_commands.py:59-61,67-70`）。
- 値を省略した場合や選択肢外の値（空値を含む）を指定した場合は、処理開始前に `argparse` が引数エラーとして拒否します。`--output` の反復指定に対する独自処理はありません。

## 実行時の動作

コマンド処理は `a.output == "json"` で機械出力を選び、`presets.activate_preset(a.preset)` を呼び出してから結果を出力します（`terminal/strata_cli/tune_commands.py:472-476,493-496`）。このオプション自体はプリセット選択・有効化処理に渡されません。

有効化はプリセットの slot 単位で `active.json` を更新し、置き換え前の有効 ID を履歴に保存します。すでに同じプリセットが有効なら追加更新せず、そのプリセットを返します（`terminal/strata_control/presets.py:227-233,337-353`）。プリセットの設定はこのコマンドでモデル起動時に即時適用されるのではなく、後の起動経路が active preset を overlay するときに反映されます。overlay はモデル・選択条件の slot を照合し、ハードな環境差や設定検証失敗がある場合は適用を見送ります（`terminal/strata_control/presets.py:488-546`）。

## 適用条件と副作用

- `human` では有効化完了の案内を標準出力に表示します。`json` では標準出力に `schema_version: 1`、`ok: true`、`preset`（要約）、`notice` を含む JSON オブジェクトを1行で出します（`terminal/strata_cli/tune_commands.py:493-496,101-106`）。
- `--output` の選択によるファイル・ネットワーク・モデル起動の副作用はありません。ただし `apply` 自体はプリセットファイルと `active.json` を更新します。有効化時に以前の active ID があれば履歴に追加し、最大20件を保持します（`terminal/strata_control/presets.py:337-352`）。
- 指定名・IDが見つからない、または曖昧な場合は `PresetError` となり終了コード `5` です。`human` では `strata: ...` を標準エラーへ、`json` では `ok: false` と `error.code` / `error.message` を含む JSON を標準出力へ出します。I/O エラーは終了コード `2`（例外に `exit_code` があればその値）で同じ出力分岐を通ります（`terminal/strata_control/presets.py:243-256`、`terminal/strata_cli/tune_commands.py:527-530,109-114`）。

## 根拠

- `terminal/strata_cli/tune_commands.py:55-70` — `presets apply` の parser 階層、位置引数、共通 `--output` の選択肢と既定値。
- `terminal/strata_cli/tune_commands.py:472-476,493-496` — JSON モード判定、プリセット有効化呼び出しと成功結果。
- `terminal/strata_cli/tune_commands.py:101-114,527-530` — 成功・失敗の stdout/stderr 形式と終了コード処理。
- `terminal/strata_control/presets.py:243-256,337-353` — プリセット参照の解決と active 状態・履歴の永続化。
- `terminal/strata_control/presets.py:488-546` — 後の起動時 overlay と、適用を見送る条件。
