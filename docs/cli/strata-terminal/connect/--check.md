# `--check`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象リポジトリの状態は `main...origin/main` で、未コミット変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect <harness>` |
| オプション | `--check` |
| 別名 | なし |
| 値 | 値を取らないフラグ（`store_true`）。未指定時は `false` |

## 役割

指定したアプリ（harness）の設定に合わせ、対象 Strata サーバーへテキスト生成と tool call のリクエストを各1回送り、両方の応答を確認します。アプリ自体は起動しません。確認対象は HTTP 成功だけでなく、生成文に `pong` が含まれること、および `get_weather` の tool call 引数に `paris` が含まれることです（`strata_cli/launch/check.py:1-7,111-143`）。

## 使い方

```sh
strata connect opencode --check
```

接続先や認証情報を明示する例:

```sh
strata connect opencode --url http://127.0.0.1:8080 --key-env STRATA_API_KEY --check
```

`--check` は `strata connect` のオプションです。harness 名が必要で、名前を省略するとアプリ一覧表示の経路に入りチェックは実行されません（`strata_cli/launch/cmd.py:148-164,842-856`）。

## 値と既定値

値は不要で、指定すると真になります。省略時はチェックをしません。`--check` 自体に数値・文字列の validation はありません（`strata_cli/launch/cmd.py:160`）。

チェックに使う接続先・モデル・キーは `--url`、`--model`、`--key` / `--key-env`、`--preset` と実行中の launch 情報から決まります。優先順はそれぞれ明示引数、選択した launch/preset 情報、既定値です。既定 URL は `http://127.0.0.1:8080`、model は `strata`、context は 32768 です。設定表示・生成用の空キーは `strata-local` に置き換えられますが、チェックの HTTP request には元のキー値が渡され、空なら認証ヘッダーは付加されません（`strata_cli/launch/cmd.py:153-160,864-870,883-884`; `strata_cli/launch/harness.py:22-43,253-260`; `strata_cli/launch/check.py:36-43`）。`--url` が `/v1` で終わる場合は server root として扱う際に末尾の `/v1` を除きます（`strata_cli/launch/harness.py:253-260`）。

## 実行時の動作

チェックは `strata_cli/launch/check.py` の `run_checks` を呼び、選んだ harness の API 形式で2回の POST を順番に行います。`codex` は Responses API、`claude-code` は Messages API、それ以外は Chat Completions API を使います（`strata_cli/launch/check.py:20-26,46-68,111-120,128-132`）。

1. `Reply with exactly one word: pong` を送り、応答テキストに大文字小文字を区別せず `pong` が含まれるか確認します。
2. Paris の天気を `get_weather` tool で尋ね、tool 名が `get_weather` で引数内に `paris` が含まれる call があるか確認します。Strata は tool の実行結果を送信しません（`strata_cli/launch/check.py:23-25,121-143`）。

各 POST の timeout は 240 秒です。指定キーが空でなければ `Authorization: Bearer ...` と `x-api-key` の両ヘッダーに設定されます（`strata_cli/launch/check.py:36-43,111-120`）。ローカル loopback 宛ては proxy を使わず、それ以外の URL は標準 `urllib` に渡されます（`strata_control/loopback.py:1-5,13-28`）。

## 適用条件と副作用

`--check` は推論サーバーへのネットワークリクエストを発生させます。両リクエストは逐次実行され、モデル推論を伴います。サーバーの状態を確認するだけの無通信オプションではありません。テキスト生成が遅い場合、各リクエストは timeout まで待つことがあります（`strata_cli/launch/check.py:111-143`）。

人向け出力では、設定内容を表示してからチェック結果を `PASS` / `FAIL` として表示します。`--write` も指定した場合はチェック成功後にファイル書き込みへ進みます。したがって、設定ファイル変更も避けたいときは `--write` を付けないでください。チェック失敗時は終了コード 1 で書き込みに進みません（`strata_cli/launch/cmd.py:897-948`）。JSON 出力ではチェック結果を含む JSON を出して終了し、`--write` の処理には進みません（`strata_cli/launch/cmd.py:164,872-896`）。

## 出力とエラー

人向け出力は各 check 名、`PASS` / `FAIL`、詳細、経過秒数を表示します。すべて成功なら終了コード 0、どちらかが失敗すれば 1 です。JSON 出力には `checks`、`checked_server`、全成功を示す `ok` が含まれ、失敗時は `error` も設定されます（`strata_cli/launch/cmd.py:880-896,921-929`）。

HTTP 401/403 はキー拒否、404 は URL または endpoint 種別の問題、その他の HTTP エラーは status code を示す詳細に変換されます。URL 接続エラーはサーバーに到達できない旨になり、その他の例外は例外型名を含む失敗になります。prompt 側で例外が起きても tool call 側は別に試行され、2件の結果を返します（`strata_cli/launch/check.py:117-143,146-155`）。

## 根拠

- parser とフラグ宣言: `strata_cli/launch/cmd.py:148-165`
- 接続先解決、通常/JSON の実行経路、終了コード、`--write` との相互作用: `strata_cli/launch/cmd.py:842-948`
- API 形式、リクエスト内容、判定、timeout、失敗詳細: `strata_cli/launch/check.py:20-26,36-68,111-155`
- harness の server root・placeholder・既定 context: `strata_cli/launch/harness.py:22-43,253-260`
- loopback の proxy 取り扱い: `strata_control/loopback.py:1-28`

調査は checkout のソースコードに限定しました。同一 revision の `--help` や Release 配布物は追加確認していません。
