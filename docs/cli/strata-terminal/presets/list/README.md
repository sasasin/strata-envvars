# `strata presets list`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

保存済みのチューニングプリセットを一覧表示します。プリセット ID の先頭 8 文字、名前、有効化状態、測定ゲイン、回答への影響区分を人向けに表示し、JSON 出力では各プリセットの要約を返します。ここで扱うのは `strata tune auto` が保存するチューニング結果です。`strata launch --list-presets` が表示する、起動設定を保存したプリセットとは別の一覧です（parser: `strata_cli/tune_commands.py:49-58`, `strata_cli/launch/cmd.py:141-146`; 処理: `strata_cli/tune_commands.py:295-300`, `strata_cli/launch/cmd.py:644-655`）。

## 使い方

```sh
strata presets list
strata presets list --model qwen --output json
```

このサブコマンドは `strata presets` の必須サブコマンドです。`list` に位置引数はありません（`strata_cli/tune_commands.py:49-58`）。

## 主な動作

- 保存先ディレクトリがなければ空の一覧として扱います。ディレクトリ内の `*.json` をファイル名順に読み、`active.json`、JSON として読めないファイル、想定スキーマ `strata.preset/1` でないファイルは除外します（`strata_control/presets.py:34-35, 45-50, 71-75, 234-252`）。
- `--model TEXT` を指定すると、プリセットの `choices` を JSON 化した文字列に `TEXT` が大文字・小文字を区別せず含まれる項目だけを残します。モデル名や量子化名の完全一致ではありません。空文字列は絞り込み条件として働きません（parser: `strata_cli/tune_commands.py:57-58`; filter: `strata_control/presets.py:247-248`）。
- 結果は作成時刻（`created_epoch`）の降順です。有効かどうかは `active.json` に記録された ID と照合して各項目に付加します（`strata_control/presets.py:202-205, 239-252`）。
- 人向け出力では各項目を `*`（有効）または空白、ID の先頭 8 文字、名前、測定ゲイン（%）、回答への影響区分で表示します。該当項目がなければ `No saved presets yet. Run: strata tune auto <profile>` と表示します（`strata_cli/tune_commands.py:295-300`）。
- JSON 出力では stdout に `schema_version: 1`、`ok: true`、`presets` を含む JSON オブジェクトを1行で出力します。各要約には ID、名前、有効状態、作成日時、選択条件、設定、回答区分、通知、測定値、再確認情報などが含まれます（`strata_cli/tune_commands.py:95-100, 295-300, 351-358`）。

## 適用条件と副作用

一覧処理はプリセットを読むだけで、有効化・削除・エンジン起動・測定は行いません。通常はユーザーのプロファイル領域にある `presets/` を参照し、`STRATA_PRESET_DIR` が設定されている場合はそのパスを使います（`strata_control/presets.py:45-50, 234-252`）。CLI の起動時には `adopt_user_defaults()` も呼ばれますが、これは Windows でプロセスが作成するファイルの既定所有者・ACLを調整する処理で、他OSでは何もしません。この一覧経路自体はファイルを作成しません（`strata_cli/cli.py:2217-2222`; `strata_control/private_files.py:349-357`）。

## 出力とエラー

`--output` は `human` または `json` を受け付け、省略時は `human` です（`strata_cli/tune_commands.py:53-58`）。一覧処理で `PresetError` が発生した場合は終了コード 5 とし、人向けでは stderr に `strata: <メッセージ>`、JSON 形式では `ok: false` とエラー情報を stdout に出します。`OSError` / `ValueError` は `exit_code` 属性があればその値、なければ 2 で同様に報告します。ただし、個々の JSON ファイルを読む際の `OSError` と JSON 解析エラーは空データ扱いで無視されます（`strata_cli/tune_commands.py:103-108, 344-347`; `strata_control/presets.py:71-75, 244-246`）。引数の不足・不正値は argparse の parser が処理します。`--help` は各サブコマンド parser による標準ヘルプです（`strata_cli/tune_commands.py:49-58`; `strata_cli/cli.py:40-45, 2223-2231`）。

## 関連文書

- [`strata presets` の概要](../README.md)
- [`--help`](--help.md)
- [`--model`](--model.md)
- [`--output`](--output.md)
- [`strata launch` の概要](../../launch/README.md)（起動設定プリセットの管理）

## 根拠

- コマンド parser とオプション: `strata_cli/tune_commands.py:49-58`
- CLI への登録と実行 dispatch: `strata_cli/cli.py:487, 2151-2152`
- 一覧の出力・フィルタ適用: `strata_cli/tune_commands.py:95-108, 289-300, 344-347, 351-358`
- 保存先、ファイル読込、除外条件、並び順、有効状態の判定: `strata_control/presets.py:34-35, 45-50, 71-75, 202-205, 234-252`
- 同じ `presets` 名を持つ launch 設定一覧との区別: `strata_cli/launch/cmd.py:141-146, 644-655`
