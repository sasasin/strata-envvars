# `strata presets delete`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets delete` |
| 位置引数 | `preset`（保存済みチューニング preset の名前または ID） |
| 実行オプション | `--output human|json`、`--help` / `-h` |

## 役割

保存済みのチューニング preset を削除します。preset はチューナーが測定した設定を保存するもので、Terminal CLI とデスクトップアプリが同じ保存先を共有します。削除処理はサーバーやエンジンを起動せず、引数で指定した preset を確認なしに削除対象として処理します。

## 使い方

```sh
# 名前で削除
strata presets delete "My fast one"

# ID の先頭 8 文字で削除
strata presets delete a1b2c3d4

# JSON 形式で結果を出力
strata presets delete "My fast one" --output json
```

ID は4文字以上の一意な prefix を指定できます。名前は大文字・小文字を区別せず完全一致で検索します。名前が ID prefix とも一致する場合は名前一致を優先し、複数候補に一致する ID prefix はエラーになります。

## 主な動作と副作用

1. `preset` を完全な ID、4文字以上の ID prefix、または大文字・小文字を区別しない完全一致の名前として解決します。見つからない場合と複数候補がある場合は拒否します。
2. preset を参照している全 slot の `active.json` 履歴からその ID を取り除きます。削除対象が active だった slot は、履歴に残っている直前の ID を active に戻し、履歴が空なら active を `null` にします。
3. 更新した `active.json` を保存し、その後 preset の `<id>.json` ファイルを削除します。

保存先は既定で profiles ディレクトリの隣にある `presets/` です。`STRATA_PRESET_DIR` が設定されている場合はそのディレクトリを使います。削除後も同じ選択条件に対応する別 preset が active であれば、その preset が後続の起動時に適用されます。

## 出力と失敗

- 既定の human 出力では `Deleted '<名前>'.` を表示します。`--output json` は成功時に `schema_version: 1`、`ok: true`、削除した preset の完全な ID を含む JSON を stdout に出し、終了コード `0` を返します。
- preset が見つからない、ID prefix が曖昧、または preset store の処理で `PresetError` が起きた場合は終了コード `5` です。human 出力は `strata: <エラー>` を stderr に、JSON 出力は `ok: false` と error code/message を stdout に出します。
- `PresetError` 以外の `OSError` / `ValueError` は終了コード `2` で同じ形式のエラー出力になります。ただし、preset JSON ファイルの unlink は `OSError` を握りつぶす実装です。その場合、index 更新後にコマンドは成功メッセージを返してもファイルが残る可能性があります。
- 引数不足や不正なオプションは `argparse` が処理します。`--help` / `-h` はこのサブコマンドの usage を表示します。

## 注意点

- 削除確認の対話や専用の `--yes` option はありません。実行すると直ちに保存データの更新を試みます。
- 削除対象が active の場合、以前の preset が履歴にあれば active に戻ります。復元される候補がなければ標準設定相当（active ID なし）になります。
- 保存ファイルの unlink エラーが表面化しない経路があるため、成功表示だけではファイル削除の成否を確認できない場合があります。

## 関連文書

- [`strata presets` の概要・関連サブコマンド索引](../../README.md)
- [preset の一覧](../list/README.md)
- [preset の適用](../apply/README.md)
- [preset の undo](../undo/README.md)
- [`--output`](--output.md)
- [`--help` / `-h`](--help.md)
- [CLI 文書索引](../../../README.md)

## 根拠

- `strata_cli/tune_commands.py:49-55,68-70` — `presets delete` parser、必須の `preset` 位置引数、`--output` の値と既定値。
- `strata_cli/cli.py:487,2151-2152` — `presets` parser 登録と `presets_command` への dispatch。
- `strata_cli/tune_commands.py:95-108,317-320,344-347` — 成功出力、削除呼び出し、エラー出力と終了コード。
- `strata_control/presets.py:45-50,218-231` — 保存先と ID / 名前による検索、未検出・曖昧時のエラー。
- `strata_control/presets.py:374-387` — active index の履歴調整、保存ファイルの削除と unlink エラーの扱い。
- `strata_control/presets.py:1-17` — preset が保持する設定・測定情報と、Terminal / デスクトップアプリで共有される保存領域。
