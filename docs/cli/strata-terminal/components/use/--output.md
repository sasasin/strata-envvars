# `strata components use --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` のいずれか |

## 役割

エンジン切替の結果を人向けの文章、JSON オブジェクト、または JSON Lines で標準出力へ出します。出力形式は切替対象や切替の意味を変えません。機械出力では対話プロンプトを出さず、エラーも機械可読な形になります。

## 使い方

```sh
# 人向けの標準出力（既定）
strata components use newest

# 結果を JSON オブジェクトとして受け取る
strata components use 0.1.54 --output json

# 稼働中エンジンの終了を最大 60 秒待ち、待機イベントと結果を JSON Lines で受け取る
strata components use 0.1.54 --wait 60 --output jsonl
```

## 値と既定値

`--output` は `human`、`json`、`jsonl` のみを受け付け、省略時は `human` です。値は `argparse` の `choices` で検証されるため、他の値はコマンド処理に入る前に usage とエラーを標準エラーへ出して終了コード 2 になります。`strata components use` の parser は `--json` を登録していません（`--output json` を指定してください）。共通の登録箇所は `terminal/strata_cli/update_cmd.py:47-56`、`use` への適用は同ファイル `:84-87` です。

## 実行時の動作

`human` では切替の成否や状態を文章で標準出力へ出します。`json` は成功時に `schema_version: 1`、`ok: true` と切替結果を含む JSON オブジェクトを出し、失敗時は `schema_version`、`ok: false`、`error.code`、`error.message` を含む JSON を出します。`jsonl` も機械出力として扱われ、待機中に発生したイベントを1行ずつ（各行に `schema_version: 1`）出した後、成功または失敗の JSON オブジェクトを出します。通常の切替でイベントがなければ、結果の1行だけです。出力先はいずれも標準出力です（`terminal/strata_cli/update_cmd.py:117-139, 309-315, 449-477`）。

機械出力では対話を無効にします。`--wait` を指定せずエンジンが稼働中の場合、人向けの対話実行では待つか尋ねますが、`json` / `jsonl` または非対話端末では尋ねず、待機時間 0 のまま busy エラーになります。`--wait SECONDS` を指定した場合はその時間まで待ち、待機イベントは `jsonl` に出ます（`terminal/strata_cli/update_cmd.py:504-520`、`terminal/strata_control/updater.py:383-394`）。

出力形式にかかわらず、選択されたエンジンがこの PC で動作可能かを確認してから切替を行います。通常の Qwen エンジンでは状態に pin / active / previous 等を記録し、最新版を選ぶ場合は最新版追従に戻します。別形状のエンジンは形状固有の状態へ記録します。既に有効なエンジンを選んだ場合は変更なしです。切替でエンジンをダウンロードまたは削除することはありません（`terminal/strata_cli/update_cmd.py:470-495`、`terminal/strata_control/engine_library.py:211-228, 231-274, 296-313`、`terminal/strata_control/updater.py:1723-1773`）。

## 適用条件と副作用

- 引数の選択・エンジンの解決に失敗すると終了コード 2、エンジンがこの PC に適合しない場合や再検証・切替後の解決確認に失敗すると終了コード 5 です。稼働中のモデルがあり待機時間内に停止しない場合は、切替せず終了コード 7 になります（`terminal/strata_control/engine_library.py:184-197, 202-213, 221-228, 239-269`、`terminal/strata_cli/update_cmd.py:471-475`）。
- 切替にはローカルのコンポーネント状態ファイルへの記録が伴います。`--output` 自体はファイルを作成・変更せず、ネットワーク取得も行いません（状態更新は `terminal/strata_control/updater.py:1723-1773`、`use` の呼び出しは `terminal/strata_cli/update_cmd.py:470-477`）。
- 同じバージョンのエンジンが複数ある場合は `--family` で対象を絞れます。`--family` がないまま曖昧な指定をすると終了コード 2 になります（`terminal/strata_cli/update_cmd.py:84-87`、`terminal/strata_control/engine_library.py:184-197`）。

## 出力とエラー

無効な `--output` 値は parser が標準エラーへ usage/error を出し、終了コード 2 で終了します。実行後の既知の失敗は `human` なら `strata: ...` を標準エラーへ、`json` / `jsonl` ならエラーオブジェクトを標準出力へ出します。返却コードは各失敗コードを維持します（`terminal/strata_cli/update_cmd.py:311-316, 378-388`）。成功時は `human` が説明文、機械出力が JSON です（同ファイル `:476-495`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56, 84-87` — 共通 `--output` parser の値・既定値と、`use` コマンドへの登録。
- `terminal/strata_cli/update_cmd.py:117-139, 309-315, 449-495` — 人向け表示、JSONL イベント、機械出力判定、`use` の成功・失敗出力。
- `terminal/strata_cli/update_cmd.py:504-520`、`terminal/strata_control/updater.py:383-394` — 対話を行わない条件、待機とイベント通知。
- `terminal/strata_control/engine_library.py:184-228, 231-274, 296-313` — 対象エンジンの解決、稼働中の拒否、Qwen / 形状別切替。
- `terminal/strata_control/updater.py:1723-1773` — 状態ファイルへの切替記録と最新版追従の扱い。
