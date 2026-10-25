# `strata presets status`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets status` |
| POSIX の入口 | `bin/strata`（Terminal CLI） |
| 主な実装 | `strata_cli/cli.py`、`strata_cli/tune_commands.py`、`strata_control/presets.py` |
| 対象 | 保存済み tuning preset と、指定した profile / run config の組み合わせ |

## 役割

指定した設定について、次回起動時に使われる tuning preset、その preset の有効性、同じ選択条件に属する preset 一覧、undo に戻れる状態を表示します。設定や preset を有効化・変更するコマンドではありません。

`presets status` はトップレベル `presets` サブコマンドに登録され、`strata presets status <target>` として実行します。`target` は保存済み profile 名または JSON run config のパスです（parser: `strata_cli/tune_commands.py:49-60`、トップレベルでの登録・dispatch: `strata_cli/cli.py:486-488,2151-2152`）。

## 使い方

```sh
# 保存済み profile の tuning 状態を表示
strata presets status PROFILE_NAME

# run config JSON を指定し、機械処理向け JSON で表示
strata presets status ./run-config.json --output json
```

profile 名は profile store から解決され、JSON 拡張子、絶対パス、または `/`・`\\` を含む値はパスとして扱われます。パス形式の値は profile 名にフォールバックしません（`strata_control/profiles.py:382-388`）。run config は JSON object で、`args` が文字列配列、`exe` と `tokenizer` が空でない文字列である必要があります（同 `:135-147`）。

## 実行モード

`--output` は `human`（既定）または `json` です（`strata_cli/tune_commands.py:53-60`）。human 表示では有効 preset があれば `Active: '<name>' (<state>)`、なければ `No saved tuning for these choices yet.` と出力します。JSON 表示は `schema_version: 1`, `ok: true` と status payload を含みます（同 `:95-100,401-408`）。詳細は [`--output`](--output.md) を参照してください。

## 主な動作と副作用

- 設定を読み、現在の hardware・engine・model identity を取得します。model identity は設定内の `--native` または最初の `.gguf` 引数を対象にし、そのファイルが存在する場合に限って計算します（`strata_cli/tune_commands.py:111-115,391-396`; `strata_control/presets.py:136-155`）。model identity helper はファイル全体ではなく先頭・中間・末尾のサンプルから identity を作る設計です（`strata_control/tune_machine.py:299-309`）。
- preset の選択 slot は model digest、context、KV format、vision、goal から作られます。同じ model file・選択条件に属する preset を抽出し、active index と照合して現在の有効 preset を判定します（`strata_control/presets.py:89-117,128-131`; `strata_cli/tune_commands.py:394-400`）。
- active preset があれば、現在の identity と比較して `fresh`、`soft`、`hard` の状態および理由を返します。変更が検出されない場合は `fresh`、再確認を要する差分は `soft`、設定が自動適用されないほどの差分は `hard` です（`strata_control/presets.py:158-197`）。
- JSON payload は `slot`, `suggested_name`, `choices`, `active`, `state`, `reasons`, `presets`, `can_undo`, `switched_off`, `last_active` を含みます（`strata_cli/tune_commands.py:401-408`）。preset を有効化したり、index や run config を更新したりする処理はこの status 分岐にはありません（同 `:301-303,391-408`）。
- 保存済み profile 名でアクセス権エラーが発生した場合、profile loader は Strata 管理下ファイルのアクセス権を一度修復して再読込する経路を持ちます。その条件では読み取り時にファイル権限が変更されることがあります（`strata_control/profiles.py:150-165`; `strata_control/private_files.py:476-484`）。JSON run config の直接読み込みにはこの profile repair helper は使われません。

## 注意点と失敗

- 保存済み profile 名で対象が見つからない、run config を読めない、JSON/config 形式が不正などの場合は失敗します。status 実装は `PresetError` を終了コード 5 で、`OSError` / `ValueError` をその例外の `exit_code`（なければ 2）で報告します（`strata_cli/tune_commands.py:344-347`; config 検証: `strata_control/profiles.py:135-147`）。human error は stderr に `strata: ...`、JSON error は stdout に `schema_version: 1`, `ok: false`, `error` を出します（`strata_cli/tune_commands.py:103-108`）。
- status は端末や engine の実行・ベンチマークを行いません。ただし hardware identity の取得や設定・model file・preset store の読み取りが行われます（`strata_cli/tune_commands.py:391-408`; `strata_control/presets.py:136-155,202-204,234-252`）。

## 関連文書

- [`strata presets` のオプション索引](../../../README.md#strata-terminal)
- [`strata presets status --output`](--output.md)

## 根拠

- `strata_cli/tune_commands.py:49-60` — `presets status` parser と `target` / `--output`。
- `strata_cli/cli.py:486-488,2151-2152` — parser 登録とコマンド dispatch。
- `strata_cli/tune_commands.py:111-115,289-303,391-408` — target 読み込み、status 分岐、出力項目。
- `strata_control/profiles.py:135-147,382-388` — run config 検証と target 解決。
- `strata_control/presets.py:89-117,128-131,136-155,158-197,202-204,234-252` — choices / slot / identity / staleness / preset store の読み取り。
- `strata_control/tune_machine.py:264-309` — hardware・engine・model identity の構築。
- `strata_control/private_files.py:476-484` — profile 読み込み時のアクセス権修復経路。
