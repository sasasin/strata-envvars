# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata models list` |
| オプション | `--output` |
| 別名 | なし。`--json` は別のフラグで、同じく JSON 出力を選ぶ |
| 値 | `human` または `json`。省略時 `human` |

## 役割

結果を人向けの行表示、または機械処理向けの JSON で出力します。`--served` の有無で一覧対象は変わりますが、出力形式の選択は共通です。ローカル一覧では既定でインストール済みモデル設定候補を調べ、`--served` を付けると指定または選択されたサーバーの現在インスタンスを照会します（`strata_cli/cli.py:564-596`）。

## 使い方

```sh
strata models list --output json
strata models list --served --output json
```

## 値と既定値

- parser は `choices=("human", "json")` を指定し、既定値を `human` にしています。これ以外の値は `argparse` が受理せず、usage とエラーを表示して終了コード 2 になります（`strata_cli/cli.py:143-152`）。
- `--json` は one-shot parser 群へ共通追加される独立フラグです。`strata models list --json` は `main()` で `output` を `json` に設定します。したがって `--output human --json` を併記した場合も JSON になります（`strata_cli/cli.py:508-515, 2232-2235`）。`--output` 自体に短縮 alias はありません。
- 重複指定時の特別な validation や優先順位処理はありません。`argparse` の通常の同一引数処理に従います。

## 実行時の動作

- `human` のローカル一覧は各候補につき `ID  component_status  name` を表示します。候補がない場合は探索した場所と案内を1行表示します。`json` は一覧データを `schema_version: 1` と `ok: true` を含む JSON オブジェクトとして stdout に出します（`strata_cli/cli.py:588-596`、成功出力の共通処理は `strata_cli/cli.py:537-542`）。
- ローカルの列挙対象は setup が書き込む `strata-<id>.json` の run config です。`--install-dir` がなければ Strata の discovery 順で見つけた各インストール先を読み取り、同一 ID は先に見つかった場所を採用します。1インストール先あたり設定数の上限は128件です（`strata_control/models.py:62-81, 88-103, 185-210`）。一覧結果はモデル実行や設定変更を行いません。設定と必要コンポーネントを検査し、互換性は `unverified` として扱います（`strata_control/models.py:158-182`）。
- `--served` 使用時は `--install-dir` は使えず、併用するとエラーになります。`--url`、`--connection`、`--credential-env`、`--timeout` は `--served` が必要で、`--served` なしで指定するとエラー終了コード2です（`strata_cli/cli.py:565-587`）。JSON 出力では `scope: "served_current_instance"` と `models` 等を含み、現在のサーバーインスタンスのモデルID・ロード状態を出力します。これはインストール済みモデル全体の一覧ではありません（`strata_cli/cli.py:568-585`）。
- `--output json` は `--quiet` と併用しても JSON をそのまま stdout に出します。`--quiet` の人向け stdout 抑制処理は human 出力でのみ適用されます（`strata_cli/cli.py:2232-2248`）。

## 適用条件と副作用

ローカル一覧では設定ファイルと参照コンポーネントの読み取り・検査が行われます。設定ファイルが symlink、非 regular file、1 MiB 超、JSON 不正、必須フィールド不正などの場合、その候補を `component_status: "invalid"` として一覧に含める経路があります。設定が検査中に変化した場合もその候補の検査エラーとして記録されます（`strata_control/models.py:106-129, 173-205`）。候補数が上限超過など、ディレクトリ単位で列挙できない場合は install directory 自体を invalid 行として記録します（`strata_control/models.py:96-103, 189-195`）。

`--served` では HTTP の読み取り専用 telemetry endpoint を要求し、認証環境変数が設定されていれば Bearer credential として送信します。timeout は未指定時3秒、明示値は `0 < 値 <= 30` 秒で、`--timeout` parser 自体は `float` 変換のみを行い、範囲検査は接続設定の解決時に行います（`strata_cli/connections.py:273-303`、`strata_cli/client.py:84-110`）。リクエストは `/v1/telemetry` を優先し、404の場合に `/metrics`、さらに必要なら `/v1/status` を参照します（`strata_cli/client.py:134-145`）。

## 出力とエラー

- `--output json` の成功出力は1つの JSON オブジェクトを stdout に出します。`--served` の要求失敗など、共通処理で捕捉するエラーは `schema_version: 1`, `ok: false`, `error` を含む JSON を出力します。human モードの通常エラーは `strata: ...` を stderr に出します（`strata_cli/cli.py:537-542, 2184-2193`）。
- `--served --install-dir ...`、または `--served` なしで接続関連フラグを指定した場合は終了コード2です。前者は `--output json` の場合 JSON エラーになります（`strata_cli/cli.py:565-587`）。
- 接続先への HTTP 401/403 は終了コード4、telemetry schema 非互換等はコード5として `ClientError` 経由で失敗します。HTTP redirect、HTTP その他の非成功、timeout、不正な JSON、2 MiB 超応答も拒否されます（`strata_cli/client.py:101-144`）。
- 明示した `--install-dir` が既存の絶対ディレクトリでない場合は `ProfileError` で失敗します。ローカル設定の個別不備は原則として一覧内の `invalid` 行にし、コマンド全体の即時失敗と区別されています（`strata_control/models.py:62-72, 185-210`）。

## 根拠

- parser と同じコマンド階層の option 定義: `strata_cli/cli.py:141-152`
- `--json` / `--quiet` の共通追加と `--json` の実効化: `strata_cli/cli.py:508-515, 2232-2248`
- `--output` に応じた一覧・エラー出力: `strata_cli/cli.py:564-596`
- ローカル discovery、重複処理、上限、個別設定の validation: `strata_control/models.py:62-103, 106-129, 173-210`
- served 接続設定の既定値・timeout 範囲: `strata_cli/connections.py:273-303`
- telemetry HTTP、応答 validation、fallback: `strata_cli/client.py:84-145`

調査範囲は上記 checkout の Terminal CLI ソースです。異なる配布バイナリや Release artifact の挙動は照合していません。
