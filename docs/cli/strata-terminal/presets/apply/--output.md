# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets apply` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

成功時・失敗時の結果を、人向けの短いテキストか JSON のどちらで標準出力へ出すかを選びます。適用する preset は必須位置引数 `preset` で指定します。

## 使い方

```sh
strata presets apply <preset-id-or-name> --output json
```

例では保存済み preset の ID（または名前）を指定します。ID の一部を使う場合は4文字以上が必要です。

## 値と既定値

- `human`: 既定値です。成功時は `'<名前>' is now active...` の形式のメッセージを標準出力へ出します。
- `json`: 成功時は `schema_version: 1`、`ok: true`、`preset`、`notice` を含む JSON オブジェクトを標準出力へ1行で出します。
- それ以外の値は parser の `choices` 検証で拒否されます。`--output` は値を1つ取り、繰り返し指定時は argparse の通常動作により最後の値が残ります。

## 実行時の動作

このオプションは出力形式だけを選び、preset の選択や適用方法を変えません。`apply` は指定値を preset ID、4文字以上の ID prefix、または大文字小文字を区別しない完全一致の名前として検索します。一致しない場合や曖昧な場合は失敗します。

見つかった preset をその選択条件の slot で active にします。すでに同じ preset が active なら保存処理をせず返します。別 preset が active ならその ID を最大20件の履歴へ残し、新しい active と `previous` を記録します。preset JSON と `active.json` は preset store に書かれます。preset store の場所は `STRATA_PRESET_DIR` があればその値、なければ profile directory の隣の `presets/` です。

この CLI 呼び出しはモデルエンジンを起動しません。active preset は後のモデル起動時に構成へ overlay されます。起動時には選択条件や現在のモデル・エンジン等の識別情報を確認し、hard な変更がある場合や安全規則に合わない設定は適用されません。

## 適用条件と副作用

preset store に読み取り・書き込み可能で、指定 preset が存在し一意に特定できる必要があります。`--output` 自体はファイルを作成・上書きしませんが、`apply` 操作は store 内の preset JSON と active index を更新します。置き換えた preset は undo 用履歴に残ります。次のモデル起動時にのみ設定が使われ、適用時点で測定やエンジン起動は行いません。

## 出力とエラー

- 成功時は終了コード `0` です。`human` は短い成功文、`json` は成功 JSON を標準出力へ出します。
- preset が見つからない・曖昧などの `PresetError` は終了コード `5` です。`human` では `strata: ...` を標準エラーへ、`json` では `ok: false` とエラー情報を含む JSON を標準出力へ出します。
- `OSError` / `ValueError` は `presets_command` 内で捕捉され、例外に `exit_code` がなければ終了コード `2` になります。JSON モードではエラー JSON、human モードでは標準エラーへのメッセージです。
- `human` / `json` 以外の値は argparse が usage とエラーを標準エラーへ表示し、終了コード `2` で終了します。

## 根拠

- `strata_cli/tune_commands.py:53-55` — `presets` 配下の共通 parser に `--output` を登録し、値・既定値を定義。
- `strata_cli/tune_commands.py:63-64` — `apply` parser と必須 preset 位置引数。
- `strata_cli/tune_commands.py:95-108,289-314,344-348` — JSON / human の成功・失敗出力、preset 検索と適用呼び出し、例外の終了コード。
- `strata_control/presets.py:45-68,218-231,310-326` — store の場所、preset の検索規則、active 切替え・履歴保持・書き込み。
- `strata_control/presets.py:11-17,441-482` — 起動時 overlay の説明、hard change・安全規則・適用時の例外処理。
- `strata_cli/cli.py:2223-2235` — argparse による引数解析と選択肢外の引数エラー処理。

調査範囲は指定 revision の Python CLI parser と preset 管理実装です。OS ごとの配置先の詳細や、外部の Strata Desktop が同時に store を操作する場合の競合挙動は、このオプション調査では検証していません。
