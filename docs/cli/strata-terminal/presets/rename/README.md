# `strata presets rename`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets rename` |
| 主な実装 | `strata_cli/tune_commands.py`、`strata_control/presets.py` |

## 役割

保存済みの tuning preset の名前を変更します。preset は ID を維持したまま JSON ファイル内の `name` を更新します。改名だけを行い、preset の設定を有効化したり、モデルやエンジンを起動したりはしません。

ここで扱う tuning preset は `strata launch` のセットアップ内容を名前付きで保存する launch preset とは別のデータです。tuning preset はモデル起動時の設定に使われることがありますが、このコマンドは launch preset 自体の名前を変更しません。

## 使い方

```sh
# 名前または ID（4文字以上の ID prefix も可）で指定
strata presets rename "Old name" "New name"

# JSON 形式で結果を受け取る
strata presets rename 1a2b3c4d "New name" --output json
```

`PRESET` には ID 全体、ID の先頭4文字以上、または名前を指定できます。名前の照合は大文字小文字を区別しません。`--output` は `human`（既定）または `json` です。

## コマンドの動作

1. preset の新しい名前を前後の空白を除いて検証します。
2. `PRESET` を既存 preset に解決します。完全一致 ID を先に探し、次に名前の大文字小文字を無視した一致を探します。名前が一致しない場合は ID prefix（4文字以上）を調べます。複数候補に一致する指定は拒否されます。
3. 同じ名前（大文字小文字を無視）が別の preset に使われていなければ、該当 preset の JSON を原子的な置換で書き換えます。
4. 成功時は human 形式なら `Renamed to '…'.` を標準出力に、JSON 形式なら `schema_version: 1`、`ok: true`、更新後 preset の要約を含む JSON を標準出力に出します。

名前は trim 後に1〜80文字で、改行・復帰・NUL を含められません。長さは Python の `len` で検査されます。同一 preset の現在の名前を再指定することは、別 preset との重複ではないため許可されます。

## 保存先と副作用

既定ではプロファイル格納場所の親にある `presets/` が保存先です。`STRATA_PRESET_DIR` が設定されている場合は、その値を展開したパスを使います。対象 preset の `<id>.json` のみを書き換え、preset ID と他の記録値を保ちます。書き込みは同じディレクトリ内の一時ファイルを作り、flush と `fsync` の後に置換し、失敗時には残った一時ファイルを削除します。

アクティブ状態・履歴を持つ `active.json` はこの rename 処理では更新しません。改名結果は既定で即時に共有 preset データへ反映されますが、preset の適用状態や推論実行には影響しません。

## 出力とエラー

- 成功時の終了コードは `0` です。
- preset が見つからない、参照が曖昧、新しい名前が無効、または別 preset と名前が重複する場合、`strata: <理由>` を標準エラーに出し、終了コード `5` を返します。`--output json` の場合は標準出力に `schema_version: 1`、`ok: false`、`error.code` と `error.message` を含む JSON を出します。
- ファイル操作の `OSError` は共通エラー処理に渡されます。JSON 出力ならエラー JSON、human 出力なら標準エラーに理由を出し、明示された `exit_code` がなければ終了コード `2` です。
- 必須位置引数がない場合など parser の構文エラーは `argparse` が処理します。終了コードと usage 表示は標準の `argparse` の経路です。

## 関連文書

- [Strata CLI 文書索引](../../../README.md) — `strata presets` 以下のコマンド・オプション一覧
- [Terminal CLI の概要](../../../../TERMINAL.md)
- [Terminal launch の概要](../../../../TERMINAL_LAUNCH.md) — `strata launch` の保存 preset との関係

## 根拠

- Strata `strata_cli/tune_commands.py:49-55,65-67` — `presets rename` parser、必須位置引数、`--output` の選択肢と既定値。
- Strata `strata_cli/tune_commands.py:95-108,289-293,314-316,344-347` — 成功出力、失敗出力・終了コード、rename 呼び出し。
- Strata `strata_cli/cli.py:486-490,2151-2155` — `presets` parser の登録と CLI dispatch。
- Strata `strata_control/presets.py:45-50,53-68` — 保存先決定、一時ファイルを使う原子的書き込み。
- Strata `strata_control/presets.py:218-231,234-250` — preset の参照解決、一覧・名前照合の範囲。
- Strata `strata_control/presets.py:255-257,361-371` — 重複名判定、名前の検証、preset JSON の更新。
- Strata `strata_cli/launch/store.py:1-6,32` — launch preset の別ストアと保存場所。
