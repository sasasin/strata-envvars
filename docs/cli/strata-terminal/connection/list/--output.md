# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。対象リポジトリの確認時点では `main` は `origin/main` と一致し、作業ツリーに未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata connection list` |
| オプション | `--output` |
| 別名 | なし（`--json` は同じ JSON 出力を選ぶ別オプション） |
| 値 | `human` または `json` |

## 役割

一覧の出力形式を選びます。既定の `human` は整形した JSON を出し、`json` は `schema_version` と `ok` を含むコンパクトな JSON を出します。したがって、`human` も通常の人間向けテーブルではなく JSON 形式です（`strata_cli/monitor_commands.py:91-94, 140-163`）。

## 使い方

```sh
strata connection list
strata connection list --output json
```

`--json` は `--output json` と同じ出力を選びます。

## 値と既定値

- 省略時は `human` です。
- `human` と `json` 以外は parser の choices により拒否されます。`jsonl` はこのコマンドでは受理されません（`strata_cli/monitor_commands.py:91-94`）。
- `--json` は `store_true` の別オプションで、`--output` の値自体を書き換えるのではなく、実行時に JSON 出力として扱われます（`strata_cli/monitor_commands.py:92-93, 167-169`）。

## 実行時の動作

一覧処理は `connections.list_connections()` を呼び出します。接続ディレクトリが存在しない場合は空一覧です。存在する場合は名前順の `*.json` のうち、ファイル名 stem が接続名規則に合うものを読みます。成功行には `id`、`url`、`prefix`、`credential_env`、`revision` が入ります（`strata_cli/monitor_commands.py:140-143`; `strata_cli/connections.py:149-164`）。

`--output human` は `schema_version` と `ok` を除いた `connections` 配列を、インデント付き JSON として stdout に出します。`--output json` は `{"schema_version":1,"ok":true,"connections":[...]}` をコンパクトな JSON として出します（`strata_cli/monitor_commands.py:142-163`）。`--quiet` を併用すると `human` の stdout は抑制されますが、`json` または `--json` では JSON 出力が維持されます（`strata_cli/monitor_commands.py:167-175`）。

## 適用条件と副作用

この一覧は接続情報を読むだけで、接続先サーバーへの通信や接続ファイルの変更は行いません。保存場所は `STRATA_CONNECTION_DIR` が設定されていればその絶対パス、Windows では `APPDATA` 配下（未設定時はユーザープロファイルの既定位置）、それ以外では `XDG_CONFIG_HOME` または `~/.config` 配下です。list はディレクトリ作成を要求しません（`strata_cli/connections.py:72-90, 149-164`）。

個別ファイルの読み込み・検証に失敗した場合、そのファイルは一覧から黙って除外されず、`id` と `error` を持つ行になります。100 件を超える有効な名前の JSON ファイルがあると一覧全体が失敗します（`strata_cli/connections.py:149-164`）。

## 出力とエラー

- 成功時の終了コードは `0` です。`human` と `json` の成功出力の形は上記のとおりです（`strata_cli/monitor_commands.py:142-164`）。
- `STRATA_CONNECTION_DIR` が相対パス、保存ディレクトリが不正または POSIX 上で所有者専用でない場合、接続記録が100件を超える場合は `ConnectionError` になります。既定の終了コードは `2`、ディレクトリ・件数の検査エラーは `5` です（`strata_cli/connections.py:47-50, 72-90, 149-155`）。
- 一覧ディレクトリを走査する際の `OSError` は終了コード `6` で処理されます。`json` または `--json` の場合は stdout に `ok: false` を含む JSON エラーを出し、それ以外は stderr に `strata: ...` を出します（`strata_cli/monitor_commands.py:124-129, 167-175, 239-240`）。
- 不正な `--output` 値は parser が拒否し、`argparse` の usage エラー（終了コード `2`）になります。parser の定義は `strata_cli/monitor_commands.py:91-94`、トップレベル CLI からの呼び出しは `strata_cli/cli.py:490-493, 2165, 2223-2231` です。

## 根拠

- Parser と `--output` / `--json` / `--quiet` の定義: `strata_cli/monitor_commands.py:75-94`。
- `connection list` の一覧取得と出力形式: `strata_cli/monitor_commands.py:132-164`。
- quiet・エラー処理: `strata_cli/monitor_commands.py:124-129, 167-175, 231-244`。
- 接続ディレクトリ選択・検査と列挙処理: `strata_cli/connections.py:47-50, 72-90, 149-164`。
- CLI への parser 登録と実行委譲: `strata_cli/cli.py:490-493, 2165, 2217-2231`。
