# `strata components install-file --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components install-file` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` |

## 役割

結果の表示形式を選びます。エンジンのアーカイブを署名検証してインストールする処理自体はどの形式でも同じですが、機械可読形式では進捗イベントの扱いと、実行中エンジンがある場合の対話確認が変わります。

## 使い方

```sh
# 人向けの通常表示
strata components install-file ./strata-engine.tar.gz --output human

# 成功結果またはエラーを JSON として取得
strata components install-file ./strata-engine.tar.gz --output json

# 処理フェーズを JSONL イベントとして受け取り、最後に結果オブジェクトを取得
strata components install-file ./strata-engine.tar.gz --output jsonl
```

## 値と既定値

省略時は `human` です。parser は `human`、`json`、`jsonl` のいずれかに限定し、他の値を `argparse` の選択肢エラーとして拒否します。値は `--output` の次に1つ指定します。別名は定義されていません（`terminal/strata_cli/update_cmd.py:47-56,92-94`）。

## 実行時の動作

- `human` は通常の説明文を表示します。インストール処理が送るフェーズ情報は標準出力へ表示され、完了時は結果の注記、またはエンジンの状態を整形した行を表示します（`terminal/strata_cli/update_cmd.py:117-139,345-354`）。
- `json` は進捗・フェーズイベントを表示せず、完了時に `schema_version: 1` と `ok: true` を含む結果オブジェクトを標準出力へ出します。処理エラーは `ok: false` と `error.code`、`error.message` を含む JSON です（`terminal/strata_cli/update_cmd.py:117-126,309-315,345-354,378-388`）。
- `jsonl` はフェーズイベントごとに `schema_version: 1` を付けた JSON 行を出し、完了時には `schema_version: 1` と `ok: true` を含む最終結果の JSON 行も出します。イベント行は `flush=True` で逐次出力されます。失敗時はイベント行に続いて、`json` と同じ形のエラー JSON 行を出します（`terminal/strata_cli/update_cmd.py:117-139,309-315,345-354,378-388`）。

このコマンドは指定アーカイブを展開し、マニフェストと署名・全ファイルを検証して、この PC に適合するか確認した後、エンジンをテスト起動して切り替えます。`--output` はこの処理を変更しません。入力アーカイブは残されます（`terminal/strata_control/updater.py:1660-1717`, `1560-1564,1641-1649`）。

## 適用条件と副作用

`json` と `jsonl` は内部で機械出力として扱われます。稼働中エンジンがある場合、人向け対話確認を行わず、`--wait` がなければ待機せずに `Busy` エラー（終了コード 7）となります。`human` で端末入出力が可能なら待機するか質問し、肯定時は最大6時間待ちます。`--wait` を指定するとこの質問を省き、指定秒数の待機経路を使います（`terminal/strata_cli/update_cmd.py:504-519,345-349`; `terminal/strata_control/updater.py:383-393,72-83`）。

ファイルが存在しない、形式が `.tar.gz` / `.tgz` / `.tar.xz` / `.zip` でない、読み込み・展開・署名・ハッシュ検証に失敗する、または PC に適合しない場合は、インストールを拒否する経路があります。既により新しいエンジンがあり `--force` がない場合は、成功応答として「変更なし」の結果を返します。これらは `--output` の形式によって変わりません（`terminal/strata_control/updater.py:1652-1717`）。

## 出力とエラー

インストール経路の `UpdateError` と署名エラーは `human` では `strata: ...` を標準エラーへ出し、JSON/JSONL ではエラー JSON を標準出力へ出します。返される終了コードは各エラーのコードを使います。未知の値など parser 段階の拒否は `argparse` による usage/error 出力です（`terminal/strata_cli/update_cmd.py:311-316,378-388`; parser: `terminal/strata_cli/update_cmd.py:56,92-94`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56,92-94` — 共通 parser への登録、値の選択肢、既定値、および `install-file` への適用。
- `terminal/strata_cli/update_cmd.py:117-139` — 人向け、JSON、JSONL のイベント出力。
- `terminal/strata_cli/update_cmd.py:309-354,378-390` — 成功・失敗時の出力と終了コード処理。
- `terminal/strata_cli/update_cmd.py:504-519` — 人向けと機械出力で異なる稼働中エンジンへの対応。
- `terminal/strata_control/updater.py:1652-1717` — 入力ファイル、形式、検証、適合確認、既存版との比較、およびインストール呼び出し。
- `terminal/strata_control/updater.py:1560-1649` — テスト起動、切り替え、状態保存、選択した元アーカイブを削除しない処理。

調査範囲は上記 Strata checkout の parser と処理実装です。`--help` の実行やビルドは行っていません。
