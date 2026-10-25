# `strata presets`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets` とそのサブコマンド |
| 主な実装 | `strata_cli/tune_commands.py`、`strata_control/presets.py` |

## 役割

`tune auto` が計測して保存した推論設定を一覧・確認し、対象となるモデル設定で有効化、切り替え、取り消し、入出力するための管理コマンドです。preset はモデルファイル、context、KV 形式、画像対応、速度優先／メモリー余裕の選択などで決まる slot ごとに管理されます。同じ選択条件に複数 preset を保存でき、有効な preset は次回以降の起動時に適用されます。Terminal CLI と Strata desktop app は同じ保存領域を使います（`strata_control/presets.py:1-17,89-131`）。

ここで扱うのは**チューニング結果の preset**です。`strata launch` の対話設定を保存する launch preset とは別の管理面です（[`strata launch` の概要](../launch/README.md)）。

## 使い方

```sh
# 保存済み tuning preset を一覧
strata presets list

# 名前または ID で内容を確認し、有効化
strata presets show "Model 128K – Full speed"
strata presets apply "Model 128K – Full speed"

# 対象 profile で実際に使われる設定と適用状態を確認
strata presets effective my-profile
strata presets status my-profile

# 同じ slot で直前に有効だった preset（または標準設定）へ戻す
strata presets undo "Model 128K – Full speed"

# preset を JSON ファイルへ出力・取り込み
strata presets export "Model 128K – Full speed" --file ./tuning.json
strata presets import ./tuning.json
```

`my-profile` は保存済み profile 名、または run configuration JSON を指します。`status`、`effective`、`off`、`recheck` も対象を必要とし、`recheck` はさらに preset を指定します（parser: `strata_cli/tune_commands.py:57-90`）。

## 実行モード

| サブコマンド | 用途 | 主な動作 |
| --- | --- | --- |
| `list [--model TEXT]` | 一覧 | 保存済み preset を作成日時の降順で表示。`--model` は preset の choices 内に指定文字列を含むものに絞ります。 |
| `status TARGET` | 状態確認 | 対象設定の slot、active preset、古さの状態、切替履歴などを返します。 |
| `show PRESET` | 詳細確認 | 1件の preset 全体を表示します。 |
| `effective TARGET` | 起動時の実効値確認 | 対象設定に active preset を重ねた args/env/sampling と、変更点を表示します。 |
| `apply PRESET` | 有効化 | preset を同じ slot の active にし、置き換えた active は undo 用履歴に残します。 |
| `off TARGET` | 一時無効化 | 対象 slot の active を解除します。preset と履歴は保持され、再度有効化できます。 |
| `rename PRESET NAME` | 名前変更 | preset 名を変更します。 |
| `delete PRESET` | 削除 | preset ファイルを削除し、active/history の参照も更新します。active を削除した場合は履歴の最後の preset があれば戻します。 |
| `undo PRESET` または `undo TARGET --config TARGET` | 切り替え取消 | slot の一つ前の active に戻します。履歴がなければ標準設定へ戻します。 |
| `export PRESET [--file PATH]` | 書き出し | `--file` があれば JSON ファイルへ書き、なければ JSON を標準出力へ表示します。 |
| `import FILE` | 取り込み | Strata preset JSON を検証し、新しい ID と重複しない名前で保存します。取り込みだけでは active にしません。 |
| `recheck PRESET TARGET` | 再計測 | 対象構成で engine を動かして短い性能再確認を行い、結果を preset に記録します。 |

各サブコマンドに `--output human|json` があり、既定は `human` です。通常の JSON 応答は `schema_version: 1` と `ok: true` を含みます。ただし `export PRESET` は `--file` を省略すると `--output` に関係なく preset JSON 本体を標準出力へ出します（parser: `strata_cli/tune_commands.py:49-90`; dispatch/output: `strata_cli/tune_commands.py:95-108,289-348`）。

`PRESET` は完全 ID、4文字以上の ID prefix、または大文字小文字を区別しない完全一致の名前で指定できます。複数件に一致する名前や不明な参照は拒否されます（`strata_control/presets.py:218-231`）。

## 主な動作と副作用

- 保存領域は既定で profiles directory の隣の `presets/` です。`STRATA_PRESET_DIR` が設定されている場合はそのパスを使います。preset は JSON ファイル、active slot と履歴は `active.json` に保存されます（`strata_control/presets.py:43-68,202-208`）。
- `apply`, `off`, `undo`, `rename`, `delete`, `import` は保存状態を更新します。`export` は `--file` を指定するとそのファイルを書き込み、既存パスの上書き確認は行いません（`strata_cli/tune_commands.py:310-341`; store operations: `strata_control/presets.py:310-409`）。
- `recheck` は単なる表示操作ではありません。対象 profile/config から engine と実行条件を解決し、worker session で再計測して結果を書き戻します。処理中の進捗を標準エラーまたは `--status-file` に記録できます（`strata_cli/tune_commands.py:411-447`）。
- 通常の起動では、対象の選択条件に合う active preset が server 起動前の config に overlay されます。設定値が安全規則に合わない場合や PC/model の identity に hard change がある場合は適用されません。soft change は適用し、再確認対象として状態を示します。overlay 自体は計測をせず、preset store の読み込み失敗でも起動設定を変えずに処理を続けます（`strata_control/presets.py:441-482`）。
- `import` は schema と tuning 設定の安全規則を検証し、拒否時には preset を保存しません。重複名には連番を付けます（`strata_control/presets.py:396-409`）。

## 注意点

`strata presets` だけでは通常 engine を起動しませんが、`recheck` は engine を起動して計測します。計測が必要なコマンドは、`--gpu-lock`、`--serve-dir`、`--work-dir`、`--status-file`、`--boot-timeout`、`--no-quiet-check` を持ちます。計測条件や失敗は環境・engine に依存するため、この文書では性能結果を保証しません。

`undo PRESET` は preset の値を直接巻き戻すのではなく、その preset が属する slot の active 履歴を戻します。`undo TARGET --config TARGET` の `--config` 指定時は、位置引数の preset 文字列を slot 解決の代わりに使わず、対象設定から slot を算出します（`strata_cli/tune_commands.py:70-72,321-330`）。

CLI の parser と処理はソースで確認しました。コマンド help の実行および別 platform の配布済み Release artifact はこの調査では検証していません。

## 関連文書

- [CLI オプション索引](../../README.md) — `strata presets` および各サブコマンドのオプション文書。
- [`strata launch` の概要](../launch/README.md) — 起動設定を保存する launch preset の利用方法。

## 根拠

- `strata_cli/cli.py:40-46,487-488,2151-2155` — トップレベル parser、`presets` 登録と command dispatch。
- `strata_cli/tune_commands.py:49-90` — `presets` の必須サブコマンドと各位置引数・option。
- `strata_cli/tune_commands.py:95-108,289-348` — human/JSON 出力、操作ごとの handler、preset/file error の失敗処理。
- `strata_cli/tune_commands.py:361-408,411-447` — 実効設定・slot 状態・再計測処理。
- `strata_control/presets.py:43-68,202-265,310-409` — 保存先、ID/name 解決、一覧、active 履歴、import/export、更新処理。
- `strata_control/presets.py:441-482` — 起動時 overlay、staleness/safe-rule 判定と store error 時の fallback。
- `docs/cli/README.md:826-923` — この概要およびサブコマンドの索引上の command scope。
