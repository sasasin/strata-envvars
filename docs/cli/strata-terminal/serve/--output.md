# `--output`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human`、`json`、`jsonl` |

## 役割

計画表示または前景サーバーの出力形式を選ぶ。`human` は通常の人向け表示、`json` は `--plan` の計画を単一 JSON オブジェクトで出力し、`jsonl` はサーバーの起動・準備完了・停止などの lifecycle event を stdout に1行ずつ出力する。`strata serve` は既存の run config（または保存済み profile）を読み、計画時は有効な設定と起動引数を組み立て、通常時はその設定で推論サーバーを前景起動する。

## 使い方

```sh
# 設定を検証し、計画を人向け形式で表示する
strata serve --profile ./run.json --plan --output human

# 計画を機械処理できる JSON で表示する
strata serve --profile ./run.json --plan --output json

# 前景サーバーの lifecycle event を JSON Lines で受け取る
strata serve --profile ./run.json --output jsonl
```

`--profile` は `--config` の別名で、parser 上必須である。`--output` 自体には短縮別名はない。

## 値と既定値

- 省略時は `human`。
- parser が受け付ける値は `human`、`json`、`jsonl` の3つだけ。別の値は argparse の選択肢エラーとなり、usage とエラーを表示して終了コード 2 で終了する。
- 同じオプションを複数回指定した場合の独自処理はない。argparse の通常の `store` 動作で最後の値が残る。
- `human` と `json` は `--plan` と併用できる。`json` を `--plan` なしで使うと実行前に拒否される。`jsonl` は通常の前景起動用で、`--plan` と同時には使えない。

## 実行時の動作

- `--plan --output json` は起動計画を組み立て、`{"schema_version":1,"ok":true,"plan":...}` の JSON を stdout に出して終了する。計画には有効設定とその出所、サーバー引数、エンジン実行ファイル・引数（引数は redaction 処理後）、注意事項などが含まれる。`human` の計画出力は `_success` に人向け文字列を渡さないため、同じ計画 payload を整形 JSON として stdout に出す。
- 前景起動時に `jsonl` を選ぶと、CLI が `starting` を出した後、サーバーから受け取った `ready`、停止時の `stopping` / `draining` / `stopped` などを schema version 付き JSON Lines として stdout に出す。起動または実行に失敗した場合は `failed` event を出す。イベントの `at` は時刻で、各 event に含めるフィールドは event ごとに限定される。
- JSONL 中のサーバー人向け出力は stderr に振り向ける。`--quiet` も指定した場合はその人向け出力を `/dev/null` に送る一方、JSONL event は stdout に出す。JSONL の受信側が stdout を閉じても、イベント出力を止めてサーバー自体は継続する。
- `--output` は出力先ファイルを指定せず、serve の起動・停止条件を変えない。foreground を選ぶとサーバーは停止されるまで実行を続ける。

### 関連オプションとの相互作用

- `--output json` には `--plan` が必須。欠けている場合は JSON 形式のエラーオブジェクトを stdout に出し、終了コード 2 となる。
- `--output jsonl --plan` は拒否され、`failed` event を stdout に出して終了コード 2 となる。
- `--json` の parser help は「`--plan --output json` の alias」と説明している。しかし実装では、`--json` が指定されると `output` を `json` にするだけで `plan` は有効にしない。そのため `strata serve --profile ./run.json --json` は `--output json requires --plan` エラーになる。計画 JSON を得るには明示的に `--plan` を付ける必要がある。
- `--output jsonl` では、値・設定などを検査している段階で `ValueError`、`OSError`、`ClientError` 等が起きた場合も、serve のエラー経路は `failed` JSONL record に整形する。通常の `human` は `strata: ...` を stderr に出し、`json` は schema version、`ok: false`、エラーコードとメッセージを持つ JSON を stdout に出す。

## 適用条件と副作用

`json` / `jsonl` の選択は出力形式だけに作用する。`jsonl` はサーバーを前景で稼働させ、起動時から停止時までイベントを出力する。出力先ファイルの作成や設定の保存はこのオプションでは行わない。stdout の Broken pipe は JSONL の記録を止めるが、推論サービスは終了させない。

## 出力とエラー

- 計画 JSON 成功時は `_success` が JSON 1件と終了コード 0 を出す。
- `human` モードの `_serve_error` は `strata: <message>` を stderr に出す。`json` は `_error` のエラー JSON を stdout に出し、検査エラーは既定で終了コード 2。
- `jsonl` の事前エラーは `{"schema_version":1,"event":"failed",...}` の1行を stdout に出す。サーバー実行中の例外は終了コード 6、割り込みは 130 として扱い、failed event を出す。停止時には server の返した終了コードが反映され、drain deadline 超過は 8。
- 有効でない値は serve の実行関数に入る前に parser が拒否するため、出力形式ごとの JSON エラーにはならず、argparse の usage error となる。

## 根拠

- `terminal/strata_cli/cli.py:67-88` — serve parser、`--output` の choices と既定値、`--json` の help。
- `terminal/strata_cli/cli.py:558-573` — 成功・失敗時の human / JSON 出力と終了コード。
- `terminal/strata_cli/cli.py:821-864` — 計画の構築、エンジン引数の redaction、plan の内容。
- `terminal/strata_cli/cli.py:868-874, 877-936` — JSONL failed record、lifecycle event の stdout 出力、Broken pipe と例外処理。
- `terminal/strata_cli/cli.py:939-994` — human / JSONL の前景実行、JSON と JSONL の `--plan` 制約、serve の validation error。
- `terminal/strata_cli/cli.py:2194-2198, 2248-2275, 2325-2343` — serve の dispatch、例外整形、`--json` が `output` のみを書き換える処理。
- `terminal/serve/server.py:9145-9155, 9763-9822` — ready、停止・drain・stopped event とサーバー終了コード。
