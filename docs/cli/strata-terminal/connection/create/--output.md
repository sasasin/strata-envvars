# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection create` |
| オプション | `--output` |
| 別名 | `--json`（JSON 出力を選ぶフラグ） |
| 値 | `human` または `json` |

## 役割

接続情報を保存する `strata connection create` の成功結果とエラーを、人向けまたは JSON 形式で出力します。出力先ファイルを指定するオプションではありません。

## 使い方

```sh
strata connection create lab --url https://example.invalid --output json
```

`name` と `--url` は必須です。`--prefix` と `--credential-env` は必要に応じて追加します。`--output` は create に限らず connection の create/show/list/set parser に個別登録されていますが、この文書では create の結果形式を扱います。（根拠: `strata_cli/monitor_commands.py:75-94`）

## 値と既定値

- `human` と `json` のみを受け付けます。省略時は `human` です。
- `--json` は値を取らない alias で、JSON 形式を選びます。`--output human --json` のように両方を指定した場合も `--json` により JSON 形式になります。
- その他の値は `argparse` の choices 検証で拒否され、コマンド処理へ進みません。根拠: `strata_cli/monitor_commands.py:91-94`。

## 実行時の動作

create の処理が返す接続レコードと revision を共通 payload にまとめ、`--output json`（または `--json`）なら `schema_version` と `ok` を含む JSON を1行で出力します。`human` ではそれら2キーを除いた内容を、インデント付き JSON として表示します。したがって human も機械可読な JSON 風の整形出力ですが、JSON モードの成功 payload とはキー構成が異なります。根拠: `strata_cli/monitor_commands.py:140-164`, `167-169`。

このオプションは接続の保存形式や保存先を変えません。作成時には名前、URL、prefix、credential 環境変数名を検証して接続ファイルを新規作成します。実際の credential 値は記録しません。根拠: `strata_cli/connections.py:221-242`。

`--quiet` は human 出力の抑制と組み合わせられます。`--output human --quiet` では local command の標準出力を捨てますが、JSON モードでは quiet による抑制は適用されません。根拠: `strata_cli/monitor_commands.py:167-175`。

## 適用条件と副作用

`--output` の形式選択は成功結果と処理エラーの表示に適用されます。接続の保存先は別の設定で決まり、`STRATA_CONNECTION_DIR` があれば絶対パスであることを要求し、なければ Windows では `%APPDATA%/Strata/connections`（APPDATA がなければホーム以下）、それ以外では `$XDG_CONFIG_HOME/strata/connections`（未設定時は `~/.config/strata/connections`）を使います。作成時はディレクトリを作り、接続名の JSON ファイルを排他的に新規作成します。根拠: `strata_cli/connections.py:72-95`, `221-242`。

URL は `http` または `https` のサーバー root で、埋め込み認証情報・path・query・fragment を含められません。HTTPS でない URL は localhost、127.0.0.1、::1 のみに許可されます。prefix は空または `/` なら空に正規化され、それ以外は traversal を含まない単純なパス segment に限られます。根拠: `strata_cli/client.py:45-76`, `strata_cli/connections.py:59-69`。

接続ディレクトリは作成時に private directory helper で作成され、POSIX では既存ディレクトリの所有者・権限も検査します。接続ファイルは `O_EXCL` で作成し、mode `0600` を指定します。既存名のファイルは上書きせずエラーになります。根拠: `strata_cli/connections.py:72-90`, `221-242`。

## 出力とエラー

- 成功時は終了コード `0` です。JSON モードでは `{"schema_version":1,"ok":true,"connection":...,"revision":...}` を標準出力へ出します。human モードでは `connection` と `revision` のみを整形して出します。根拠: `strata_cli/monitor_commands.py:147-164`。
- `--output json` または `--json` の処理エラーは `ok: false`、エラーコード、メッセージを含む JSON を標準出力へ出します。human モードでは `strata: ...` を標準エラーへ出します。根拠: `strata_cli/monitor_commands.py:124-129`, `231-240`。
- 名前の形式、URL、prefix、credential 環境変数名が不正な場合や、同名の接続が既にある場合は `ConnectionError` となり、既定終了コード `2` で失敗します。接続名は小文字英字で始まり、小文字英数字・`_`・`-` を続ける最大64文字です。根拠: `strata_cli/connections.py:41-69`, `221-234`。
- 保存時の OS file error は `_file_words` によるメッセージで終了コード `6` として返されます。具体的な文言は platform と `strata_control` の有無に依存します。根拠: `strata_cli/monitor_commands.py:116-121`, `239-240`。

## 根拠

- 索引上のコマンド階層とリンク: `docs/cli/README.md:1039-1049`（文書リポジトリ）
- parser、alias、既定値: `strata_cli/monitor_commands.py:75-94`
- 結果生成、quiet、エラー変換: `strata_cli/monitor_commands.py:124-175`, `231-248`
- 接続作成・保存副作用: `strata_cli/connections.py:72-95`, `221-242`
- URL と prefix の検証: `strata_cli/client.py:45-76`, `strata_cli/connections.py:59-69`

調査時点の checkout は `main` が `origin/main` と一致し、`git status --short --branch` に未コミット変更はありませんでした。Release artifact や platform ごとの実行結果は確認していません。この文書は同一 checkout の parser と使用箇所に基づきます。
