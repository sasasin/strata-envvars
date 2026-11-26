# `--check`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect <harness>` |
| オプション | `--check` |
| 別名 | なし |
| 値 | 取らないフラグ（`store_true`、既定値 `false`） |

## 役割

指定した harness の設定で Strata サーバーに接続できるかを実際の API リクエストで確認する。1つの短い prompt と1つの tool call を送り、HTTP 応答だけでなく、回答に `pong` が含まれることと、`get_weather` tool が `paris` を引数に含めて呼び出されることを確認する。選択したアプリそのものは起動せず、tool 実装も実行しない。`--write` と併用した場合は check が先で、どちらかが失敗すると設定ファイルを書かずに終了する。（`terminal/strata_cli/launch/cmd.py:175,1087-1107,1147-1155`、`terminal/strata_cli/launch/check.py:1-7,111-143`）

## 使い方

```sh
# 既定の接続情報で OpenCode 相当の prompt と tool call を確認する
strata connect opencode --check

# 接続先を指定して確認する（URL はサーバーの root を指定）
strata connect codex --url http://127.0.0.1:8080 --check
```

## 値と既定値

`--check` 自体は値を取らず、繰り返し指定による追加動作もない。省略時はチェックを行わない。対象アプリ名は位置引数 `<harness>` で指定する。接続情報は `--url`、`--key`、`--key-env`、`--model`、`--context`、`--preset` から解決され、明示 URL / key / model / context が優先される。指定がなければ、名前付き preset または実行中 launch 情報を参照し、最終的に URL は `http://127.0.0.1:<既定ポート>`、モデル名は `strata`、context は 32768 となる。key は `--key`、`--key-env` の環境変数、launch 情報の順で採用し、いずれもなければ空文字列である。（`terminal/strata_cli/launch/cmd.py:168-175,1074-1079`）

URL の末尾に `/v1` があれば正規化時に取り除かれる。`--context` は `_context` で Strata の context parser に渡され、不正値は argparse の型エラーとなる。`--check` 固有の追加 validation はない。（`terminal/strata_cli/launch/harness.py:333-340`、`terminal/strata_cli/launch/cmd.py:46-50,173-175`）

## 実行時の動作

まず harness と接続先を解決し、check は最大 240 秒の timeout で2つの POST リクエストを順に送る。`codex` は Responses API、`claude-code` は Messages API、その他は Chat Completions 形式を使う。API key が空でなければ `Authorization: Bearer ...` と `x-api-key` の両方を付ける。最初の prompt は応答テキストに `pong` が含まれるかを調べ、次の tool call は関数名 `get_weather` と引数中の `paris` を確認する。HTTP status 成功だけでは PASS にならない。（`terminal/strata_cli/launch/check.py:20-25,36-68,111-143`）

通常出力では各結果を `PASS` / `FAIL` として表示する。`--output json` では `checks`、`checked_server`、および総合判定 `ok` を JSON に含める。check 単独の成功は終了コード 0、片方でも失敗すれば 1。（`terminal/strata_cli/launch/cmd.py:1088-1107,1147-1155`）

## 適用条件と副作用

指定した harness の wire 形式と server root に対して実リクエストを送信するため、サーバー上で推論を2回発生させ、処理時間やサーバー資源を消費する。確認用 tool call はモデルが tool 呼び出しを返すかを見るだけで、外部 tool の実行確認ではない。チェック対象は `strata connect` が構成する API 経路であり、アプリ本体の起動や各アプリの設定読込までは検証しない。（`terminal/strata_cli/launch/check.py:1-7,111-143`）

`--check --write` を併用すると、両方 PASS のときだけ書き込み段階へ進む。check 失敗時は終了コード 1 で、human 出力では書き込み処理へ到達せず、JSON 出力では `write.written` を空として返す。書き込み時の確認やファイル副作用は `--write` 側の動作である。（`terminal/strata_cli/launch/cmd.py:1087-1107,1147-1157`）

## 出力とエラー

接続拒否・HTTP エラー・応答形式の不正など各リクエストで例外が起きても、その check は失敗結果に変換され、もう一方の check も試行される。401/403 は key 拒否、404 は endpoint 不一致、その他の HTTP status は HTTP エラー、URL error は到達不能として説明される。応答があっても prompt に `pong` がない、または期待した tool call / `paris` 引数がない場合は FAIL。human 出力では結果の詳細を表示してコード 1、JSON では `ok: false` と `error.code: 1` を出す。（`terminal/strata_cli/launch/check.py:121-155`、`terminal/strata_cli/launch/cmd.py:1093-1107,1151-1155`）

## 根拠

- `terminal/strata_cli/launch/cmd.py:168-183` — connect parser、`--check` が引数なし `store_true` であること、隣接する接続情報・出力オプション。
- `terminal/strata_cli/launch/cmd.py:1074-1080` — preset / 実行中 launch と明示値から接続情報を解決し harness 設定を生成する経路。
- `terminal/strata_cli/launch/cmd.py:1087-1119,1147-1167` — JSON / human の check 実行、失敗時の終了と `--write` より先に判定する順序。
- `terminal/strata_cli/launch/check.py:20-25,36-68,111-155` — wire format、送信内容、成功条件、timeout、エラー詳細。
- `terminal/strata_cli/launch/harness.py:318-340` — harness 名の解決と URL root の正規化。
