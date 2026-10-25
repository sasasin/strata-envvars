# `--config`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets undo` |
| オプション | `--config` |
| 別名 | なし |
| 値 | profile 名、または run config JSON のパス |

## 役割

run config の選択内容に対応する preset slot を特定し、その slot の変更履歴を一段戻します。undo の対象 preset ID を指定する代わりに設定から slot を決める用途です。オプションを省略した場合は位置引数 `preset` が slot または preset 参照として使われます（`strata_cli/tune_commands.py:321-328`、`strata_control/presets.py:339-358`）。

## 使い方

```sh
strata presets undo ignored --config /path/to/run-config.json
```

`preset` は parser 上必須です。`--config` に空でない値を指定すると、処理ではこの位置引数を使わず、設定から slot を計算します（`strata_cli/tune_commands.py:70-72,321-328`）。`/path/to/run-config.json` は実際の run config のパスに置き換えてください。saved profile 名も指定できます。

## 値と既定値

- 値は必須の文字列で、parser はファイル形式や profile 名を検査しません。省略時の値は `None` です（`strata_cli/tune_commands.py:70-72`）。
- profile 名・JSON パスの解決規則は `profiles.resolve()` に従います。`.json` 拡張子、絶対パス、または `/`・`\\` を含む値はパスとして扱い、それ以外は saved profile 名として読み込みます（`strata_control/profiles.py:382-388`）。相対パスもパスとして解決された後、run config として読み込まれます。
- run config は `args` が文字列配列であること、および空でない `exe` と `tokenizer` を持つことが必要です（`strata_control/profiles.py:135-147`）。空文字列を渡すと `if a.config` が偽になるため、`--config` 無指定と同じく位置引数が使われます（`strata_cli/tune_commands.py:321-328`）。複数回指定した場合の最終値は `argparse` の通常の `store` 動作です。

## 実行時の動作

1. `--config` が truthy なら `_load_target()` が profile 名またはパスを解決し、参照先 run config JSON を読む（`strata_cli/tune_commands.py:111-115,321-324`）。saved profile の場合、この helper は profile の overrides を合成せず、profile が指す元の run config を読みます。
2. run config の選択内容から model、context、KV 形式、vision、速度/空きメモリの希望を取り出し、現在の model shard digest と組み合わせて slot key を作る（`strata_cli/tune_commands.py:324-326`、`strata_control/presets.py:89-117,128-131,136-155`）。実装上 slot key に使われるのは model digest、context、KV 形式、vision の有無、goal です。
3. `presets.undo(slot)` が履歴末尾の preset を active に戻します。履歴がなければ active を `None` にして標準設定に戻します。復元は preset 保存フォルダー内の `active.json` を更新するもので、run config 自体は変更しません（`strata_control/presets.py:202-208,339-358`）。

`--output human|json` は `presets undo` にも共通して登録され、既定値は `human` です（`strata_cli/tune_commands.py:53-55,70-72`）。JSON 出力が必要なら `--output json` を追加できます。

## 適用条件と副作用

- `--config` 指定時は位置引数 `preset` の内容は使われませんが、位置引数自体は parser で必須です。オプションを省略した場合、位置引数は slot key として index に存在すればその slot を使い、そうでなければ preset ID・4文字以上の ID prefix・名前として解決されます（`strata_cli/tune_commands.py:321-328`、`strata_control/presets.py:339-345,218-231`）。
- 実行時に engine を起動したり測定したりはしません。config 指定時には hardware / engine / model identity を調べ、preset の index を読み書きします。identity の取得実装は `strata_control/presets.py:136-155`、index の保存先は `strata_control/presets.py:45-50,202-208` にあります。
- 保存先は `STRATA_PRESET_DIR` があればそのディレクトリ、なければ profile directory の sibling `presets/` です（`strata_control/presets.py:45-50`）。

## 出力とエラー

- 成功時は通常 `Back to '<preset name>'.`、履歴の戻り先が標準設定なら `Back to the standard settings.` を stdout に出します。JSON モードでは `schema_version: 1`、`ok: true`、`active`（復元 preset の概要または `null`）を stdout に出します（`strata_cli/tune_commands.py:95-100,328-330`）。
- 戻せる履歴がない場合は `there is nothing to undo`、参照 preset がない場合は `no preset called ...` などを human モードでは stderr に出して終了コード 5 で失敗します（`strata_control/presets.py:339-348,218-231`、`strata_cli/tune_commands.py:103-108,344-347`）。JSON モードでは `ok: false` と error 情報を stdout に出します。
- config の読み込み失敗は `ProfileError`（`ValueError` の派生）として扱われ、`read_run_config()` が付けた終了コードが使われます。その他の `OSError` / `ValueError` は既定で終了コード 2 です（`strata_control/profiles.py:30-35,135-147`、`strata_cli/tune_commands.py:346-347`）。位置引数不足や不正な引数など parser のエラーも処理前に拒否されます。

## 根拠

- parser と `--output` の共通スコープ: `strata_cli/tune_commands.py:49-55,70-72`
- `--config` による分岐、slot の算出、undo の呼び出し、成功出力: `strata_cli/tune_commands.py:111-115,321-330`
- CLI への登録と dispatch: `strata_cli/cli.py:486-488,2151-2152`
- profile 名・パスの解決と run config validation: `strata_control/profiles.py:135-147,382-388`
- slot の材料と key: `strata_control/presets.py:89-117,128-131,136-155`
- undo の復元と失敗条件、active index の保存: `strata_control/presets.py:202-208,339-358`
