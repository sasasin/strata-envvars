# `strata components update --output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` のいずれか |

## 役割

更新処理の進行状況と結果を、人向け表示、単一の JSON 結果、または JSON Lines のイベント列として標準出力へ出し分けます。値の選択は表示形式を切り替えるもので、フィード確認・ダウンロード・検証・更新やモデルの停止／再起動といった処理選択は変えません。

## 使い方

```sh
# 通常の人向け表示（既定値）
strata components update

# 結果を1つの JSON オブジェクトとして受け取る
strata components update --output json

# 進捗イベントと最終結果を JSON Lines で受け取る
strata components update --output jsonl
```

## 値と既定値

- 省略時は `human`。
- `human`、`json`、`jsonl` 以外の値は parser の `choices` により受理されません。値なしでも使えません。
- 出力先ファイルを指定するオプションではなく、結果は標準出力に出ます。
- `strata components update` 自体の option 定義は `strata update` と同じ `_common()` にあり、両コマンドで選択肢と既定値は共通です（`terminal/strata_cli/update_cmd.py:47-56,70-72`）。

## 実行時の動作

- `human` は更新開始・確認結果・進捗・完了結果を人向けに表示します。ダウンロード進捗は端末出力なら同じ行を更新し、端末でなければ概ね10ポイントごとに表示します（`terminal/strata_cli/update_cmd.py:121-139,368-377`）。
- `json` は通常の進捗イベントを抑制し、成功時に `schema_version: 1` と `ok`、更新結果を含む JSON オブジェクトを出力します。`--check` の場合は feed・engine・Control・app の確認レポートを含む JSON オブジェクトになります（`terminal/strata_cli/update_cmd.py:118-126,361-375`）。
- `jsonl` は更新処理から送られるイベントを、各行 `schema_version: 1` 付きの JSON として出力し、最後に更新結果の JSON オブジェクトを出力します。進捗イベントにはコンポーネント、完了／総 byte 数、割合、速度が含まれます。モデル状態や待機・処理段階などのイベントも emit 経由で転送されます（`terminal/strata_cli/update_cmd.py:121-124,371-374`; `terminal/strata_control/updater.py:391-393,434-435,580-587`; `terminal/strata_control/engine_update.py:309,347-355,388-398`）。
- `json` と `jsonl` は machine 出力として扱われ、更新前の対話質問は行いません。モデルが稼働中で停止許可が必要な場合は、`--stop-model` 等の条件を満たさなければ更新を拒否する経路になります（`terminal/strata_cli/update_cmd.py:307-315,404-421`; `terminal/strata_control/engine_update.py:301-323`）。
- 出力形式によらず、通常の update 経路では acquisition 許可を確認し、信頼鍵を読み込んで feed を選択した後、`--check` なら確認、そうでなければモデル状態を考慮した更新処理へ進みます（`terminal/strata_cli/update_cmd.py:355-377`）。このオプション自体は更新内容や副作用を限定しません。

## 適用条件と副作用

この option は `strata components update` の出力形式に適用されます。`json` / `jsonl` を指定しても、更新処理に伴う feed 参照、取得、インストールやモデル停止・再起動の可能性はなくなりません。モデルが動いているときの可否は `--stop-model`、`--start-again` などの更新側条件で決まります（`terminal/strata_cli/update_cmd.py:355-377,418-421`; `terminal/strata_control/engine_update.py:301-323,369-399`）。

## 出力とエラー

- `json` / `jsonl` の捕捉対象エラーは標準出力へ `schema_version: 1`、`ok: false`、`error.code`、`error.message` を持つ JSON オブジェクトとして出力され、対応する終了コードを返します。通常の人向けモードでは `strata: ...` を標準エラーへ出します（`terminal/strata_cli/update_cmd.py:311-316,378-390`）。
- `jsonl` でも失敗はこのエラーオブジェクト1行として出力されます。イベント列の途中で失敗した場合、先行イベント行に続いてエラー行が出ることがあります（`terminal/strata_cli/update_cmd.py:121-124,311-316,378-390`）。
- `--output` に不正な値を渡した場合は、コマンド処理に入る前に parser の選択肢検証で失敗します（`terminal/strata_cli/update_cmd.py:56,70-72`）。
- 更新を停止する確認に対して拒否した場合の `UpdateError` は終了コード 0 の特別経路で、出力形式にかかわらず通常文のまま出力されます（`terminal/strata_cli/update_cmd.py:378-382`）。このため、その経路では `json` / `jsonl` を指定しても JSON だけが出る保証はありません。

## 根拠

- `terminal/strata_cli/update_cmd.py:47-56,70-79` — parser の定義、許容値、既定値、および `components update` への登録。
- `terminal/strata_cli/update_cmd.py:117-139,307-377` — 表示モードの判定、イベント出力、確認結果・更新結果の出力。
- `terminal/strata_cli/update_cmd.py:378-390,404-421` — 失敗時の出力・終了コードと machine 出力時の対話抑止。
- `terminal/strata_control/updater.py:383-403,408-435,580-599` — 待機・処理段階・ダウンロード進捗イベントの生成。
- `terminal/strata_control/engine_update.py:301-323,327-355,369-399` — 稼働モデルの確認、停止、再起動とそのイベント。
- `terminal/strata_cli/cli.py:160-162,2194-2212` — parser 登録と `strata components update` の処理委譲。
