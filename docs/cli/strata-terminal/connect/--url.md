# `--url`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。対象 checkout の `git status --short --branch` は `## main...origin/main` で、表示上は未コミット変更なし。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--url` |
| 別名 | なし |
| 値 | `URL`。parser 上は文字列で、型変換・形式検証なし |

## 役割

アプリ向け接続設定の生成、表示、または `--check` の接続先となる Strata サーバーアドレスを指定する。`strata connect` は実行中の `strata launch` の設定をアプリ用に示すコマンドであり、`--url` を指定すると接続先だけを明示的に差し替えられる（`strata_cli/launch/cmd.py:148-155, 842-870`）。

## 使い方

```sh
strata connect opencode --url http://127.0.0.1:8080
```

## 値と既定値

- `URL` は必須の値引数だが、URL の scheme、host、port などを検証する処理は parser にない（`strata_cli/launch/cmd.py:154`）。
- 値を指定しない場合、`--preset` があればその名前に対応する起動中 launch または保存 preset の情報を選び、指定がなければ実行中 launch の情報を選ぶ。そこから得た URL がなければ `http://127.0.0.1:<既定ポート>` を使う。既定ポートは `S.DEFAULT_PORT` である（`strata_cli/launch/cmd.py:567-592, 605-627, 864-865`）。
- `--url` の明示値はこの選択結果より優先する。空文字列を渡すと `a.url` が偽となり、通常の既定値選択へ進む（`strata_cli/launch/cmd.py:864-865`）。
- アドレスを `harness.target()` に渡す際、前後の空白と末尾の `/` を除き、末尾が大文字小文字を問わず `/v1` ならそれも取り除く。したがって `http://host:8080/v1/` は `http://host:8080` として扱われる（`strata_cli/launch/harness.py:253-260`）。この正規化は URL 全体の妥当性検査ではない。

## 実行時の動作

正規化後のアドレスはアプリの設定ファイルや環境変数を組み立てる `Target` に入り、各アプリ用設定に埋め込まれる。OpenAI 互換設定では `/v1` を付けた base URL、Claude Code 用環境変数では `/v1` を付けない server root が使われる（`strata_cli/launch/harness.py:27-39, 95-100, 167`）。

`--preset` と併用した場合、`--url` はアドレスを上書きする一方、key・model・context は個別の `--key` / `--model` / `--context` がなければ起動情報または preset から選ばれる（`strata_cli/launch/cmd.py:605-627, 864-870`）。`--key-env` も含む key 選択の詳細は別オプション文書の対象。

`--check` を併用すると、正規化後の URL に対し、対象アプリの形式で prompt と tool call を送る。これは接続確認のためネットワーク要求を行う（`strata_cli/launch/cmd.py:880-896, 921-928`; `strata_cli/launch/check.py:36-66, 111-114`）。`--write` を併用した場合は URL を含む設定ファイルを出力し、既存ファイルは先にバックアップされる（`strata_cli/launch/cmd.py:930-947`; `strata_cli/launch/harness.py:275-284`）。

## 適用条件と副作用

- 通常の表示・JSON 出力だけなら、`--url` を使ったこと自体でサーバーへの接続は行わない。サーバーへの prompt と tool call は `--check` 時に行う（`strata_cli/launch/cmd.py:870-880, 882-896, 921-928`）。
- `--url` は `--check` の接続先と生成設定のアドレスを指定する。`--write` はファイル書き込みを伴い、既存ファイルを置換する際はバックアップを作る。確認を省くには別オプション `--yes` が必要（`strata_cli/launch/cmd.py:930-947`）。
- parser は無効な URL 形式を拒否しないため、誤った値は生成設定へ出力されるか、`--check` の通信失敗として判明する。URL の網羅的な受理形式や scheme 別の挙動はこの実装から確認できない（`strata_cli/launch/cmd.py:154, 864-870`; `strata_cli/launch/harness.py:253-260`）。

## 出力とエラー

- 無効な harness 名はエラーを標準エラーに出し、終了コード `2` で終了する。これは URL の validation ではない（`strata_cli/launch/cmd.py:857-863`）。
- `--check` で二つの確認が両方成功すれば終了コード `0`、失敗があれば詳細を出して終了コード `1`。JSON 出力では失敗時にエラー説明と `ok: false` を含む（`strata_cli/launch/cmd.py:880-896, 921-928`）。
- URL の形式不正に対する専用メッセージや専用終了コードは確認できなかった。通信時の具体的なエラー文は失敗原因・相手サーバーに依存するため、ここでは固定文言を記載しない。

## 根拠

- parser と `connect` の説明: `strata_cli/launch/cmd.py:148-165`
- URL 選択、引数の優先順位、出力、check、write 経路: `strata_cli/launch/cmd.py:605-627, 842-947`
- URL の正規化と `/v1` の扱い: `strata_cli/launch/harness.py:27-39, 253-260`
- check が送る要求先と通信処理: `strata_cli/launch/check.py:36-66, 111-114`

調査範囲は上記 commit の checkout 内にある Terminal CLI の Python 実装。別 revision のバイナリや Release 配布物の動作は確認していない。
