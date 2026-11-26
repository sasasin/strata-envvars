# `--profile`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み serving profile 名、またはインストール済み run config の JSON パス |

## 役割

ベンチマーク対象を保存済み profile または run config から特定します。profile の有効な host と port から接続先を決め、標準 suite では設定内容も使って対象 server が起動済みかを確認します。`--url` と同時には指定できず、どちらか一方が必須です。`--suite` を省略すると `standard-v1` が選ばれます。parser は文字列を受け取り、ファイルか profile 名かの判定は後段の profile 解決で行います。根拠: `terminal/strata_cli/cli.py:321-328`、`terminal/strata_control/profiles.py:400-406`。

## 使い方

```sh
# 保存済み profile を使って標準ベンチマークを実行
strata bench run --profile local

# strata launch が保存した profile を指定する例（profile 名は launch-<preset>）
strata bench run --profile launch-my-preset --no-start

# run config JSON を直接指定して serving suite を実行
strata bench run --profile /path/to/run-config.json --suite serving-smoke --out ./bench-results/smoke-1
```

2 番目の例は `--no-start` により、対象 server が応答しなければ失敗します。launch の profile は `launch-<preset>` という名前で保存されます。根拠: `terminal/strata_cli/launch/runner.py:2323-2345`。

## 値と既定値

- `--profile` 自体に既定値はなく、`--profile` と `--url` の相互排他グループの一方を必ず指定します（`terminal/strata_cli/cli.py:322-324`）。`--profile` に parser レベルの型変換や値域検証はありません。
- 値が `.json` で終わる、絶対パスである、または `/`・`\` を含む場合は、展開・解決したパスとして扱います。それ以外は保存済み profile 名として読み込みます。パスらしい値が profile 名へフォールバックすることはありません（`terminal/strata_control/profiles.py:400-406`）。
- 保存済み profile 名は小文字英字で始まり、以降は `a-z`、数字、`_`、`-` のみ、最大 64 文字です。profile データは schema version 1、名前とファイル名の一致、絶対パスの `source_config`、対応する overrides が検証されます（`terminal/strata_control/profiles.py:25-27,48-55,120-132`）。
- run config は JSON object で `args` が文字列配列、`exe` と `tokenizer` が空でない文字列である必要があります。読めないファイルや不正な内容は profile error になります（`terminal/strata_control/profiles.py:135-150`）。
- `strata launch` preset の裸の名前ではなく、保存 profile 名 `launch-<preset>` を指定します。profile が見つからず、対応する `launch-<name>` が存在する場合は、その名前を使うよう案内するエラーになります（`terminal/strata_control/profiles.py:153-184`）。

## 実行時の動作

`strata bench run` は標準 suite と serving suite で profile を異なる目的に使います。

- `standard-v1`（既定）では profile/run config を読み、設定から有効 host・port を決めて HTTP endpoint を構成します。ワイルドカード host `0.0.0.0` と `::` は接続先として `127.0.0.1` に置き換えます。環境変数 `--credential-env` で指定された名前（既定 `STRATA_API_KEY`）の値を優先し、なければ設定中の API key を使います（`terminal/strata_cli/cli.py:1323-1341`）。
- 標準 suite で profile のアドレスに server が既に応答すれば、それを使い、停止しません。応答がなく `--no-start` が指定されていなければ、一時作業ディレクトリを作成し、`strata serve --profile <値> --quiet` を子プロセスとして起動してベンチマーク後に停止します。`--no-start` 指定時に応答がない場合は失敗します（`terminal/strata_cli/cli.py:1352-1378`、`terminal/strata_cli/bench_standard.py:674-685`）。
- serving suite では profile から同様に接続先を作り、保存 profile の revision・run config のパスと SHA-256 などを結果の照合情報に渡します。保存 profile のときはベンチマーク lease も取得します。run config パス指定時は保存 profile がないため、その profile lease と保存 profile 同一性の照合はありません（`terminal/strata_cli/cli.py:1263-1289`）。
- suite の既定値は `standard-v1` です。`--url` でも対象を指定できますが、`--profile` とは同時に使えません（`terminal/strata_cli/cli.py:322-328`）。

## 適用条件と副作用

- `--profile` は、標準 suite では server 設定の読み込みに加え、server が未起動なら `--no-start` の有無に応じて起動・停止にも関与します。既に応答する server は停止しません（`terminal/strata_cli/cli.py:1362-1378`）。
- serving suite は `--profile` を接続情報と実行結果の profile identity に使い、profile が保存済みなら lease を取得します。ベンチマーク処理が server を起動する経路は標準 suite の処理に限られます（`terminal/strata_cli/cli.py:1283-1289,1352-1378`）。
- 起動した標準 suite の子プロセス出力は一時ディレクトリの `engine.log` に集められ、完了時に一時ディレクトリは削除されます。停止できなかった場合は警告を stderr に出し、結果ディレクトリに `ENGINE-NOT-STOPPED.txt` を書こうとします（`terminal/strata_cli/cli.py:1365-1369,1376-1389`）。
- run config に `api_key` がある場合、その設定値は接続用に読み込まれます。キーの取り扱い全般や認証サーバー側の動作は、このオプションの parser/使用箇所だけからは網羅できません。

## 出力とエラー

- `--profile` と `--url` のどちらも指定しない、または両方指定すると argparse が usage error として拒否します（`terminal/strata_cli/cli.py:322-324,2325-2334`）。
- 未保存 profile、profile の形式不正、run config の読み込み・検証失敗は `ProfileError` になります。通常の人向け出力では `strata: <message>` を stderr に出し、error の exit code を返します。profile 不在（保存 profile）や読めない run config は既定で code 5、名前・schema・overrides 等の validation error は既定で code 2 です（`terminal/strata_control/profiles.py:30-35,153-173`、`terminal/strata_cli/cli.py:558-563,2248-2255`）。
- 標準 suite で server が見つからない場合、`--no-start` 指定時は code 5 で失敗します。ベンチマークは新規レポートディレクトリへ結果を書き、指定 `--out` が既存なら拒否します（`terminal/strata_cli/cli.py:1362-1365`、`terminal/strata_cli/bench_standard.py:834-853`）。
- 標準 suite で起動した server の停止に失敗した場合は stderr に停止失敗を示し、結果を failed として code 6 を返します（`terminal/strata_cli/cli.py:1382-1398`）。

## 根拠

- `terminal/strata_cli/cli.py:319-328` — `bench run` parser、`--profile`/`--url` の相互排他と必須指定、suite の既定値。
- `terminal/strata_control/profiles.py:25-27,48-55,120-150,153-184,400-406` — profile 名とデータの検証、run config 読み込み、profile 名/JSON パスの判定、launch profile の案内。
- `terminal/strata_cli/cli.py:576-579,821-849,1263-1289,1307-1378` — profile 解決後の設定・endpoint 構築と各 suite での使用。
- `terminal/strata_cli/bench_standard.py:674-685,834-853` — 標準 suite が起動する子 server と対象 server の前提確認。
- `terminal/strata_cli/launch/runner.py:2323-2345` — launch が `launch-<preset>` 名で serving profile を保存・更新。
