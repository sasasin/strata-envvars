# `strata presets apply`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の Strata checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets apply` |
| 役割 | 保存済み tuning preset を、対応する選択条件の有効 preset にする |
| 主な実装 | `strata_cli/tune_commands.py`、`strata_control/presets.py` |

## 役割

`strata tune auto` などで保存された tuning preset を、その preset が属する slot の有効 preset に切り替えます。変更は次回以降のモデル起動時に反映されます。このコマンド自体はエンジンを起動せず、既存プロファイルの設定も書き換えません。切り替え前に有効だった preset は履歴に残り、`strata presets undo` で戻せます（`strata_control/presets.py:310-327`）。

## 使い方

```sh
# ID の先頭 8 文字を使って有効化
strata presets apply 0123abcd

# JSON 出力を選択
strata presets apply "Office 128K" --output json

# 切り替えを戻す
strata presets undo 0123abcd
```

`preset` には ID 全体、4 文字以上の一意な ID prefix、または preset 名を指定できます。名前は大文字・小文字を区別せず完全一致で解決します。prefix や名前が複数 preset に一致すると拒否されます（`strata_control/presets.py:218-231`）。

## 実行時の動作

Parser は位置引数 `preset` と共通オプション `--output {human,json}` を受け付け、出力形式の既定値は `human` です。`apply` に短縮別名はありません（`strata_cli/tune_commands.py:53-55,63-64`）。

処理は preset を解決し、その `slot` の `active` を対象 preset の ID に更新します。そこに別の preset が有効なら、その ID を最大 20 件までの履歴に追加し、対象 JSON の `previous` も更新します。preset ファイルと `active.json` は一時ファイル経由で書き込まれます（`strata_control/presets.py:53-68,310-327`）。すでに同じ preset が有効な場合は preset の切り替え・履歴更新をせず、その preset を返します（同: `315-316`）。

slot は preset 作成時に選択条件とモデルファイルの digest から設定され、apply 時にはその保存済み slot の active ID を切り替えます（`strata_control/presets.py:268-287,310-323`）。このコマンドはモデルの適合性を再測定しません。次回起動時の `presets.overlay` が現在のモデル等の identity を照合し、identity の hard change があれば適用を見送り、soft change は適用対象として re-check を促す状態にします。また設定が安全規則を満たさない場合はその preset を適用しません（同: `441-479`）。

適用可能な preset の設定は、起動時に engine 引数・環境変数・request 単位の sampling 設定へ overlay されます。適用の実処理は server 起動経路に委譲され、この apply コマンドを実行した時点ではその overlay や再起動は発生しません（`strata_control/presets.py:11-17,441-479`）。

## 実行モードと出力

これは preset の有効状態を更新する管理操作です。human 出力では有効化した名前、次回のモデル起動で使われること、undo 用コマンドを表示します。`--output json` では `schema_version: 1`、`ok: true`、preset の要約と notice を含む JSON を stdout に出します（`strata_cli/tune_commands.py:95-100,310-313`）。

この操作自体には engine 実行、性能測定、設定の即時適用はありません。成功時の更新先は通常、profile directory の隣にある `presets/` です。`STRATA_PRESET_DIR` が設定されている場合はそのパスが使われます（`strata_control/presets.py:45-50,310-327`）。

## エラーと注意点

- 未知の preset、形式不正な preset ID、曖昧な名前または ID prefix は `PresetError` になり、human 出力では `strata: ...` を stderr に表示して終了コード 5 を返します。JSON モードでは `ok: false` と error code/message を stdout に出します（`strata_control/presets.py:78-81,211-215,218-231`; `strata_cli/tune_commands.py:103-108,344-347`）。
- ファイル操作などの `OSError` / `ValueError` は通常終了コード 2 で同じエラー出力経路に入ります（`strata_cli/tune_commands.py:344-347`）。
- 有効化は次のモデル起動から効きます。起動時に identity または安全規則の確認で適用されないことがあるため、状態確認には `strata presets status <profile-or-config>`、実際に適用される値の確認には `strata presets effective <profile-or-config>` を使えます（`strata_cli/tune_commands.py:59-64,78-81`; `strata_control/presets.py:441-479`）。
- apply 時に現在の engine 状態、モデルの起動可能性、性能は確認されません。これらの検証が行われるとは推測できません。

## 関連文書

- [`strata presets` コマンドと各オプションの索引](../../../README.md)
- [`strata launch` コマンド概要](../../launch/README.md)（起動時に有効 preset が使われる経路）

## 根拠

- Strata `strata_cli/tune_commands.py:49-55,63-64` — `presets apply` の parser と共通 `--output` 定義。
- Strata `strata_cli/tune_commands.py:289-313,344-348` — apply の dispatch、成功出力、失敗処理。
- Strata `strata_control/presets.py:45-50,53-68,78-81,202-231` — 保存場所、atomic 書き込み、ID と名前の解決。
- Strata `strata_control/presets.py:310-327` — active preset と undo 履歴の更新。
- Strata `strata_control/presets.py:441-482` — 起動時の identity / 安全性確認と overlay。
- Strata `strata_cli/cli.py:2151-2152` — Terminal CLI から preset command への dispatch。

調査範囲は上記 commit の checkout 内の parser と Python 実装です。Release 配布物や各 OS の実行環境での動作確認は行っていません。
