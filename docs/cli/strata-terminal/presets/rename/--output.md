# `strata presets rename --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata presets rename` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

プリセット名の変更結果を、人向けの短いメッセージか、機械処理向けの JSON で標準出力へ出します。名前を変更する処理自体はどちらの形式でも同じです。

## 使い方

```sh
# 人向けの出力（既定）
strata presets rename "旧プリセット名" "新プリセット名"

# JSON 出力
strata presets rename 1a2b3c4d "新プリセット名" --output json
```

## 値と既定値

`--output` は `human` と `json` のみを受け付け、既定値は `human` です。別の値を指定すると argparse の選択肢検証で拒否されます。rename parser にこのオプションの別名はありません。オプションは `presets` の各サブコマンドに共通登録されていますが、この文書の対象は `rename` です。`strata presets rename` にはプリセット参照と新しい名前の二つの位置引数が必要です。

## 実行時の動作

`human` の場合、成功時は `Renamed to '<名前>'.` を標準出力へ出します。`json` の場合は `schema_version: 1`、`ok: true` と、変更後プリセットの要約を含む JSON オブジェクトを一行で標準出力へ出します。いずれも成功終了コードは `0` です。

rename はプリセット ID を維持したまま、そのプリセットの JSON ファイルに新しい名前を書き込みます。書き込みは一時ファイルを作成して置換する方式です。アクティブ状態の索引ファイルを更新する処理はこの経路にはありません。

## 適用条件と副作用

プリセット参照には完全な ID、4 文字以上の ID prefix、または大文字小文字を区別しない完全一致の名前を使えます。該当なし、または複数のプリセットに一致する参照は拒否されます。

新しい名前は前後の空白を除いてから検証され、空でないこと、80 文字以下であること、改行または NUL を含まないことが必要です。他のプリセットと大文字小文字を区別しない同名も拒否されます。有効な名前なら、保存済みプリセット JSON が書き換わります。

## 出力とエラー

名前の検証、参照解決、同名検査に失敗すると、`human` では `strata: <理由>` を標準エラーへ、`json` では `schema_version: 1`、`ok: false` とエラー情報を標準出力へ出し、終了コード `5` を返します。保存時の `OSError` は同じ出力形式で報告され、通常は終了コード `2` になります。`--output` 自体に無効な値を指定した場合は parser が処理関数の実行前に拒否します。

## 根拠

- `docs/cli/README.md:788-791` — `strata presets rename` のコマンド階層と `--output` の索引リンク。
- `terminal/strata_cli/tune_commands.py:55-61,71-73` — `presets` の子 parser に共通の `--output` を登録し、rename の位置引数を定義。
- `terminal/strata_cli/cli.py:514-515,2229-2230` — parser 登録と `presets_command` へのディスパッチ。
- `terminal/strata_cli/tune_commands.py:101-114,472-499,527-531` — 人向け/JSON の成功・失敗出力と終了コード、rename 呼び出し。
- `terminal/strata_control/presets.py:243-256,280-281,388-398` — 参照の解決規則、名前の検証と重複判定、プリセット JSON の更新。
- `terminal/strata_control/presets.py:53-68` — JSON 保存時の一時ファイル書き込みと置換。
