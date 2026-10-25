# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

`strata connect` の標準出力を、人向けの説明形式か機械処理向け JSON 形式に切り替えます。アプリ名を省略した場合は接続可能なアプリ一覧、指定した場合はそのアプリ向けの設定内容が出力対象です。

## 使い方

```sh
strata connect opencode --output json
strata connect --output human
```

## 値と既定値

- parser が受け付ける値は `human` と `json` のみで、既定値は `human` です。別名はありません（`strata_cli/launch/cmd.py:148-165`）。
- 値は選択肢で検証されます。その他の値は `argparse` の引数エラーとなり、コマンド処理には進みません（同 `strata_cli/launch/cmd.py:164`）。

## 実行時の動作

- 実装は `a.output == "json"` を JSON 出力モードとして扱います（`strata_cli/launch/cmd.py:842-845`）。
- `strata connect --output json` は、アプリ一覧を `schema_version: 1`、`ok: true`、`harnesses` を持つ JSON オブジェクトとして標準出力に出し、終了コード `0` を返します。`human` では表形式の一覧と補足案内を出します（同 `strata_cli/launch/cmd.py:845-856`）。
- アプリ名を指定した JSON 出力は、設定ファイル・環境変数などを `files` / `env` 等に含めた JSON オブジェクトです。設定中の API key は JSON 内でマスクされ、`--show-key` を同時指定しても JSON 経路ではマスクされたままです（同 `strata_cli/launch/cmd.py:864-879`; `strata_cli/launch/harness.py:263-268,310-311`）。
- `--output json` の通常経路は JSON を出力して `return 0` するため、その後にある `--write` 処理を実行しません。これは `--write` 単独の場合の動作と異なります（同 `strata_cli/launch/cmd.py:872-879,930-948`）。
- `--check` を併用すると、設定されたアプリの通信形式でサーバーへ prompt と tool call を1回ずつ送信し、その結果を JSON の `checks` に加えます。2つとも成功すれば `ok: true` / 終了コード `0`、いずれか失敗なら `ok: false` / `error` と終了コード `1` です。チェック実行後も JSON 経路は戻るため、`--write` は実行されません（同 `strata_cli/launch/cmd.py:880-896`; `strata_cli/launch/check.py:1-7,111-143`）。

## 適用条件と副作用

- `--output` 自体は出力形式を選びます。`--check` を付けた場合はサーバーへ2つのリクエストを送信し、応答内容も検査します（`strata_cli/launch/check.py:36-43,111-143`）。
- JSON と `--write` の併用ではファイル書き込みは行われません。人向けの既定形式で `--write` を指定した場合は確認後に設定ファイルを書き込み、既存ファイルのバックアップや JSON 設定のマージを行う経路があります（`strata_cli/launch/cmd.py:930-948`; `strata_cli/launch/harness.py:275-298`）。
- JSON 出力には秘密情報のマスクが含まれます。人向け出力では `--show-key` により実際の key を表示する経路があります（`strata_cli/launch/cmd.py:870-875,900-910`）。

## 出力とエラー

- JSON モードの一覧・設定内容は標準出力へ出ます。人向けモードも説明内容を標準出力へ出します（`strata_cli/launch/cmd.py:847-855,872-879,897-920`）。
- 存在しないアプリ名は、形式指定にかかわらず `strata: ...` の案内を標準エラーへ出し、終了コード `2` を返します（`strata_cli/launch/cmd.py:857-863`）。したがって、この失敗経路は JSON エラーオブジェクトではありません。
- `--check` の失敗結果は JSON に記録され、終了コード `1` になります（`strata_cli/launch/cmd.py:884-896`）。

## 根拠

- `strata_cli/launch/cmd.py:148-165` — `connect` parser と `--output` の choices・既定値。
- `strata_cli/launch/cmd.py:842-948` — JSON / human の出力、key のマスク、`--check` と `--write` の制御フロー。
- `strata_cli/launch/harness.py:238-268,310-311` — アプリ名解決、出力データ生成、key マスク。
- `strata_cli/launch/harness.py:275-298` — 書き込み時のバックアップ・マージ・権限設定。
- `strata_cli/launch/check.py:1-7,36-43,111-155` — `--check` が送るリクエストと判定・失敗内容。
