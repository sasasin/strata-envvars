# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` のいずれか |

## 役割

`strata serve` の標準出力形式を選びます。`human` はサーバーの人間向け出力、`json` は `--plan` で計画を一度だけ出力する形式、`jsonl` はサーバーの起動・終了を追う JSON Lines 形式です。出力先ファイルを指定するオプションではなく、機械可読形式も標準出力へ出します（`strata_cli/cli.py:64-65, 838-867, 940-941`）。

## 使い方

```sh
# 通常の前景サーバー出力（既定）
strata serve --profile /path/to/run-config.json

# 起動せず、検証済みの起動計画を JSON で出力
strata serve --profile /path/to/run-config.json --plan --output json

# 前景サーバーの lifecycle を JSON Lines で出力
strata serve --profile /path/to/run-config.json --output jsonl
```

`--profile` は必須です。`json` は `--plan` と組み合わせ、`jsonl` は `--plan` を付けず前景実行に使います（`strata_cli/cli.py:46-47, 63-65, 915-953`）。

## 値と既定値

- 値は `human`、`json`、`jsonl` の3つに限定されます。`argparse` の `choices` による検査で、大文字小文字を変えた値や他の文字列は受理されません（`strata_cli/cli.py:64-65`）。
- 省略時は `human` です。値は1つ必須で、同じオプションを複数回指定した場合は `argparse` が最後に解析した値を保持します（同所）。
- 対応する環境変数や設定ファイル値はありません。選択値は serve コマンドの処理分岐に直接使われます（`strata_cli/cli.py:915-955`）。

## 実行時の動作

- **`human`**: `--plan` がなければサーバーを前景起動し、サーバーの標準出力をそのまま端末へ流します（`strata_cli/cli.py:900-912, 942-953`）。`--plan` と併用した場合は起動せず、計画を整形 JSON として標準出力へ出します（`strata_cli/cli.py:940-941, 535-542`）。
- **`json`**: `--plan` が必須です。計画を `schema_version: 1`、`ok: true`、`plan` を含む1行の JSON として出力し、サーバーは起動しません（`strata_cli/cli.py:915-918, 940-941, 535-542`）。`--plan` なしでは終了コード2となり、機械可読エラー JSON を出します（`strata_cli/cli.py:915-918, 829-835, 527-532`）。
- **`jsonl`**: `--plan` とは併用できません。前景サーバーの lifecycle を1イベント1行で標準出力へ flush します。CLI が出す `starting` に続き、サーバーから `ready`、停止時の `stopping` / `draining` / `stopped`、または失敗時の `failed` などが出ます（イベントのフィールドは `strata_cli/cli.py:838-867`、サーバー側の通知は `serve/server.py:8127-8137, 8645-8662, 8670-8710`）。`--plan` と併用すると、`failed` イベントを出して終了コード2になります（`strata_cli/cli.py:915-919, 829-835`）。

いずれの値も計画作成時には設定ファイルの読込・検証を行います。実際にサーバーを起動する場合、POSIX/Windows では runtime activity lease を取得してサーバーを実行し、終了時に lease を閉じます（`strata_cli/cli.py:931-955`）。`--quiet` は人間向け標準出力を抑えますが、`jsonl` のイベント出力は維持します。JSONL 経路ではイベント出力先が閉じた後もサービスを停止させず、以後のイベント記録を止めます（`strata_cli/cli.py:838-867, 900-912`）。

## 適用条件と副作用

- `json` は計画表示に限られ、稼働中サーバーの JSON ログ形式としては使えません。その用途は `jsonl` です（`strata_cli/cli.py:915-919`）。
- `jsonl` はサーバーの標準出力を標準エラーへ振り替え、イベントだけを標準出力に保ちます。`--quiet` 指定時は人間向け標準出力を `/dev/null` に振り替えます（`strata_cli/cli.py:868-873, 900-912`）。
- 起動経路では inference server がポートを bind し、停止時には所有するリクエストの drain などを行います。これらは `--output` 自体の効果ではなく、選択した出力形式で同じ serve 実行を観測するものです（`serve/server.py:8645-8662, 8670-8710`）。
- parser のヘルプは `--json` を「`--plan --output json` の alias」と説明しますが、実装は `--json` を指定すると `output=json` に変換するだけで、`plan` は有効にしません。そのため `--json` 単独は `--output json requires --plan` で拒否されます。説明と実装に不一致があり、計画 JSON には明示的に `--plan --output json` を指定してください（`strata_cli/cli.py:66, 915-918, 2232-2235`）。

## 出力とエラー

- 不正な値は parser が拒否し、`argparse` の usage とエラーを標準エラーへ出して終了コード2になります（parser 宣言 `strata_cli/cli.py:64-65`）。
- `--output json` と `--plan` の不整合は `schema_version`、`ok: false`、`error.code`、`error.message` を含む JSON を出して終了コード2になります。`jsonl` と `--plan` の不整合は `event: "failed"`、`exit_code: 2`、`error.message` を持つ JSONL イベントになります（`strata_cli/cli.py:829-835, 915-919`）。
- JSONL の通常イベントには `schema_version: 1` と `event`、時刻 `at`、各イベントに対応する項目が含まれます。stdout の Broken pipe はサービスを停止させず、イベント出力のみを閉じます（`strata_cli/cli.py:838-867`）。
- JSON/JSONL 実行時の serve 処理で捕捉される `ValueError`、`OSError`、`ClientError`、割り込みは機械可読エラーへ変換されます。JSONL では `failed` イベント、JSON ではエラー JSON です（`strata_cli/cli.py:2166-2193`）。

## 根拠

- `strata_cli/cli.py:46-67` — serve parser、`--output` の choices/default と `--json` の説明。
- `strata_cli/cli.py:829-955` — serve 固有の出力・エラー処理、計画モード、foreground 実行。
- `strata_cli/cli.py:527-542, 2166-2193, 2232-2243` — JSON success/error、例外処理、`--json` の変換。
- `serve/server.py:8127-8137, 8645-8710` — JSONL で利用する lifecycle 通知とサーバー側の状態遷移。

調査対象の checkout は `main` で `git status --short --branch` は `## main...origin/main`（変更表示なし）でした。既存の CLI help は実行せず、同一 revision の parser と実装を根拠にしています。
