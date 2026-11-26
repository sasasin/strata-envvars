# `strata connect --url`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connect` |
| オプション | `--url` |
| 別名 | なし |
| 値 | `URL` 文字列。parser で型・scheme・host・範囲の検証は行わない |

## 役割

接続設定を表示または生成するアプリに渡す Strata サーバーのアドレスを指定する。生成設定の server root と `--check` の接続先を明示的に選べる。省略時は起動中の launch（`--preset` 指定時はその名前に対応する起動情報または preset）からアドレスを使い、情報がなければ `http://127.0.0.1:8080` を使う（`terminal/strata_cli/launch/cmd.py:169,703-724,1074-1079`）。

## 使い方

```sh
# 指定したサーバー向けの OpenCode 設定を表示する
strata connect opencode --url http://127.0.0.1:8080

# 指定先に prompt と tool call を送り、設定相当の疎通を確認する
strata connect opencode --url https://strata.example --check
```

## 値と既定値

- `--url` は値を1つ取る。必須指定ではなく、別名はない。parser は通常の文字列として受け取り、URL形式の validation や空文字の拒否は定義していない（`terminal/strata_cli/launch/cmd.py:163-175`）。
- 明示値があれば `launch_info()` の値より優先する。省略時は `--preset` があればその起動情報または保存 preset のアドレスを参照し、preset 名がなければ起動中 launch の先頭のアドレスを参照する。どちらも得られない場合の fallback は `http://127.0.0.1:<DEFAULT_PORT>` で、connect parser の help は既定ポートを `8080` と示す（`terminal/strata_cli/launch/cmd.py:703-724,1074-1079,169`）。
- `harness.target()` は前後の空白と末尾 `/` を除き、末尾が大文字小文字を問わず `/v1` ならそれも取り除く。`/v1` を含む URL を渡しても、生成設定には server root が使われる（`terminal/strata_cli/launch/harness.py:333-340`）。
- `--url ""` は Python の `or` により未指定と同じ fallback になる（`terminal/strata_cli/launch/cmd.py:1075`）。

## 実行時の動作

選択したアプリ用の `Target` に正規化済み server root を渡し、アプリ設定・環境表示をレンダリングする。`--url` だけではファイルを書き換えない。`--write` を付けるとレンダリングされた設定ファイルを書き、既存ファイルがあれば確認後にバックアップする。`--dry-run` は書き込みをプレビューする（`terminal/strata_cli/launch/cmd.py:1074-1080,1123-1127,1019-1050,1156-1167`）。

`--check` と併用すると、正規化済み server root に対してアプリが使う形式で prompt と tool call をそれぞれ送信する。URL は `/v1` を含まない root として扱われ、チェック用 endpoint に `/v1/...` が追加される（`terminal/strata_cli/launch/harness.py:31-38,333-340`; `terminal/strata_cli/launch/check.py:50-55,111-143`）。`--preset NAME` と併用した場合、`--url` は preset 由来の URL を上書きするが、key・model・context はそれぞれ明示指定がなければ起動情報/preset 側から解決される（`terminal/strata_cli/launch/cmd.py:1074-1079`）。

## 適用条件と副作用

アプリ名を省略した `strata connect` は対応アプリ一覧を表示して終了するため、そこで `--url` は利用されない（`terminal/strata_cli/launch/cmd.py:1055-1066`）。アプリ名を指定した場合、URL形式の検査や HTTPS 強制はこのオプションの parser・正規化処理にはない。値が不正または到達不能な場合の具体的な扱いは、後続の URL 利用方法に依存する。

`--check` は実サーバーへ最大2種類の HTTP POST を行う。到達不能・HTTP error 等はチェック結果に反映され、片方でも失敗すれば終了コード `1` となる。`--check --write` ではチェック失敗時にファイルを書かず終了する（`terminal/strata_cli/launch/check.py:36-43,111-154`; `terminal/strata_cli/launch/cmd.py:1087-1107,1147-1155`）。通常の表示では接続情報を出力し、`--write` は設定ファイルへの書き込みを伴うため、remote URL 指定時は接続先と生成内容を確認して使う。

## 出力とエラー

`--check` は human 出力では prompt/tool call の PASS/FAIL を表示し、両方が成功しなければ `1` を返す。JSON 出力でも `checks`、`checked_server`、`ok` を返し、失敗時は `error` を付けて `1` を返す（`terminal/strata_cli/launch/cmd.py:1087-1107,1147-1155`）。チェック処理は到達不能、HTTP 401/403、404、その他 HTTP error を区別して説明する（`terminal/strata_cli/launch/check.py:146-154`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:163-175` — `connect` parser と `--url` 宣言。URL の型変換・validation がないこと。
- `terminal/strata_cli/launch/cmd.py:703-724,1074-1079` — running launch/preset の情報取得、明示値の優先、既定アドレスと key/model/context の解決。
- `terminal/strata_cli/launch/harness.py:333-345` — server root の正規化と、値をアプリ設定へレンダリングする入口。
- `terminal/strata_cli/launch/cmd.py:1019-1050,1087-1109,1120-1167` — check/write の順序、表示、書き込みとエラー経路。
- `terminal/strata_cli/launch/check.py:36-55,111-154` — HTTP check request と失敗理由。
