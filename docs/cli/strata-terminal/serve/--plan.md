# `strata serve --plan`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata serve` |
| オプション | `--plan` |
| 別名 | なし（`--json` は JSON 形式で plan を表示する別のフラグ） |
| 値 | 値を取らない真偽値。省略時は `false` |

## 役割

run config または保存済み profile と指定オプションを読み、解決後の設定、server に渡す引数、engine 実行ファイルと引数を表示して終了します。serve の起動可否に関わる検証も行いますが、推論 server を起動しません。parser は `action="store_true"` で定義されています（`terminal/strata_cli/cli.py:84`）。

## 使い方

```sh
strata serve --profile /path/to/run-config.json --plan
strata serve --profile /path/to/run-config.json --plan --output json
strata serve --profile /path/to/run-config.json --json
```

`--profile` と `--config` は同じ `config` 引数に入る別表記で、いずれかが必須です（`terminal/strata_cli/cli.py:69-71`）。`--output json` は `--plan` と組み合わせます。`--json` を指定すると `main` が `output` を `json` に切り替えます（`terminal/strata_cli/cli.py:87`, `2335-2338`）。

## 値と既定値

`--plan` 自体は値を取らず、既定値は `false` です。繰り返し指定しても同じ真の状態になります。値を後置する構文はありません（parser 定義: `terminal/strata_cli/cli.py:84`; 未認識引数の拒否: `terminal/strata_cli/cli.py:2325-2334`）。

## 実行時の動作

`strata serve` の処理は先に `--output` と主要引数を検証し、profile/run config を解決して実効値を組み立てます。各設定値の由来はコマンドライン、保存済み profile、run config、環境変数、既定値の順で選ばれ、結果と由来が plan に含まれます（`terminal/strata_cli/cli.py:783-818`, `821-865`）。

その後 `--plan` が真なら `_success({"plan": plan}, ...)` を返し、通常の server 起動処理へ進みません。plan は `effective`、`origin`、`server_argv`、`engine_exe`、redact 済み `engine_argv`、notes などを含みます（`terminal/strata_cli/cli.py:859-865`, `954-994`）。engine 引数は config の引数を元に組み立てられ、drafting や VRAM 適合などの処理を反映します（`terminal/serve/server.py:3665-3695`, `3711-3726`）。

出力は既定で human 形式（整形 JSON）です。`--output json` または `--json` は schema version と `ok: true` を含む一行 JSON にします（`terminal/strata_cli/cli.py:566-573`, `979-980`）。`--output json` は `--plan` なしでは拒否され、`--output jsonl` と `--plan` の併用も拒否されます。JSONL は foreground service のイベント出力用です（`terminal/strata_cli/cli.py:85-87`, `954-958`）。

## 適用条件と副作用

- `--plan` を通る前に、`--port` は `0..65535`、`--parallel` は `1..1024`、`--max-queue` は `0..4096`、`--queue-timeout` は有限秒数 `0.1..600`、`--shutdown-timeout` は `0..300` に検証されます。`queue_timeout` は `max_queue` が必要です（`terminal/strata_cli/cli.py:959-969`, `808-809`）。
- batch groups、parallel、offline などは profile override と run config 引数との衝突・適用条件も検証されます（`terminal/strata_cli/cli.py:804-818`）。API key が設定されている場合は形式検証されますが、plan 出力の `engine_argv` は秘密らしい引数値を伏せます（`terminal/strata_cli/cli.py:825-831`, `764-780`, `859-864`）。
- `--ready-file` を併用すると、plan 作成時に絶対パスであること、親ディレクトリが存在すること、対象が未作成であることを検査します。この段階ではファイルを作成しません（`terminal/strata_cli/cli.py:845-849`; `terminal/serve/ready.py:16-24`）。
- plan 分岐は server main の呼び出しと runtime activity lease の取得より前です。そのためこのオプション経由では inference server や engine を起動しません（`terminal/strata_cli/cli.py:979-994`）。ただし通常の CLI 初期化は先に実行され、Windows では private file の既定 owner 設定を試みます（`terminal/strata_cli/cli.py:2314-2324`; `terminal/strata_control/private_files.py:349-354`）。保存済み profile の読み込み経路は、必要時にアクセス権を修復する読み取り関数を呼びます（`terminal/strata_control/profiles.py:153-160`）。

## 出力とエラー

`--output json` と `--plan` の不整合、範囲外の数値、override の衝突、config/profile の読み込み・検証失敗はエラーになります。通常のエラーは stderr に `strata: ...` を出し、機械可読出力では `ok: false` と `error` を JSON で返します。明示された終了コードは `ProfileError` 等の `exit_code` を使い、その他の `ValueError` は既定 2、I/O error は 6 です（`terminal/strata_cli/cli.py:558-563`, `954-978`, `2222-2265`）。run config は JSON として読み、`args` 配列、`exe`、`tokenizer` などの形式を検査します（`terminal/strata_control/profiles.py:135-150`）。

## 根拠

- parser と `strata serve` の引数定義: `terminal/strata_cli/cli.py:65-88`
- 設定値の選択・相互作用: `terminal/strata_cli/cli.py:783-818`
- effective launch の組み立て: `terminal/strata_cli/cli.py:821-865`
- plan の検証、出力、server 起動との分岐: `terminal/strata_cli/cli.py:954-994`
- JSON 成功・失敗形式と例外経路: `terminal/strata_cli/cli.py:558-573`, `2222-2275`
- run config と ready-file の検証: `terminal/strata_control/profiles.py:135-150`, `terminal/serve/ready.py:16-24`
- engine 引数生成: `terminal/serve/server.py:3665-3726`
