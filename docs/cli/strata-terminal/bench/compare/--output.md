# `strata bench compare --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench compare` |
| オプション | `--output` |
| 別名 | なし（`--json` は別途定義された同等動作の指定） |
| 値 | `human`、`json`、`markdown` |
| 既定値 | `human` |

## 役割

2件の保存済み serving benchmark を比較し、その結果の表示形式を選びます。`strata bench compare` はベースラインと候補のパスを位置引数で受け取り、両方のレポートを読み込んでから比較します。`--output` は比較方法や測定条件を変えません（`strata_cli/cli.py:343-347, 1163-1174`）。

## 使い方

```sh
strata bench compare ./bench/baseline ./bench/candidate --output json
strata bench compare ./bench/baseline/results.json ./bench/candidate/results.json --output markdown
```

パスにはレポートを含むディレクトリ、またはレポート JSON ファイルを指定できます。ディレクトリの場合は `results.json` を読み込みます（`strata_cli/bench.py:891-900`）。

Markdown をファイルに保存する場合は、`--out` も指定します。

```sh
strata bench compare ./bench/baseline ./bench/candidate --output markdown --out ./comparison.md
```

## 値と既定値

- `human`（既定）: 比較結果を人向けのテキストとして標準出力に表示します。
- `json`: `schema_version: 1`、`ok: true`、`comparison` を含む JSON オブジェクトを標準出力に出します。
- `markdown`: 比較内容と比較上の制約を含む Markdown を標準出力に出します。
- 他の値は `argparse` の `choices` により受理されません。`--output` 自体を複数回指定した場合の特別な処理はなく、通常の argparse の同一引数処理に従います（`strata_cli/cli.py:343-347, 508-515`）。

この parser では `--json` も `bench compare` に登録されており、main 処理で `--output json` に置き換えられます。`--output` に JSONL はありません（`strata_cli/cli.py:508-515, 2232-2235`）。

## 実行時の動作

出力形式を適用する前に、ベースラインと候補それぞれをロードし、比較します。両レポートは成功済みで異なる run ID を持ち、suite・model ID・phase 数・各 phase の workload（要求 fingerprint と concurrency）が一致する必要があります。双方に source config digest がある場合は一致も必須です。報告された環境に差がある場合も比較は失敗します。一部の identity がない場合は警告として残り、ドライバー、engine binary、model artifact、monitor attachment はレポートから attestation されない旨など、適用範囲の限界も比較結果に含まれます（`strata_cli/bench.py:1006-1048`）。

その後、`human` は `format_comparison` の要約、`json` は比較辞書、`markdown` は比較表を出力します。Markdown には `Provisional comparison` と測定・qualification 上の注意が含まれます（`strata_cli/cli.py:1163-1174`; `strata_cli/bench.py:1084-1117, 1258-1298`）。

## 適用条件と副作用

- `--out NEW_FILE` は `--output markdown` のときだけ使用できます。これを付けて `human` または `json` を選ぶと、比較より先にエラーとなり終了コード `2` です（`strata_cli/cli.py:1132-1133`）。
- `--output markdown` のみなら標準出力へ出します。`--out` を指定すると Markdown をそのファイルへ新規作成し、作成後に解決済みパスを標準出力へ表示します。サイズ上限は 64 KiB で、既存ファイルまたはシンボリックリンクは置き換えず、エラー（終了コード `2`）になります。作成時は排他的な新規作成で mode `0600` を指定します（`strata_cli/cli.py:1165-1172`; `strata_cli/bench.py:1301-1308, 668-677`）。
- `--quiet` も当該 parser に登録されます。JSON 出力時は機械可読結果を維持しますが、`--output markdown --quiet` では成功時の標準出力が抑制されます。quiet 実行が失敗し、抑制対象の標準出力があれば stderr に出されます（`strata_cli/cli.py:508-515, 2236-2248`）。
- 比較処理は保存済みレポートの読み取りと、`--out` 指定時の Markdown 作成です。ここで benchmark を再実行したり、server/GPU を起動したりする経路はありません（`strata_cli/cli.py:1163-1174`）。

## 出力とエラー

正常終了は終了コード `0` です。`human` は `format_comparison` のテキスト、`json` は `{"schema_version":1,"ok":true,"comparison":...}`、`markdown` は Markdown 文書を標準出力へ出します（`strata_cli/cli.py:1163-1174, 535-542`）。

入力レポートは通常ファイルで 4 MiB 未満であること、JSON と report schema が対応していることを検証します。読めないファイルや不正・未対応 report は失敗します。比較条件不一致（異なる run、失敗 run、suite/model/workload/environment 不一致など）も `ProfileError` になります（`strata_cli/bench.py:891-949, 1006-1048`; `strata_control/profiles.py:30-31`）。これらは `ValueError` / `OSError` として CLI のエラー処理に入り、終了コードを伴うエラーになります。JSON モードでは `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}`、human/markdown モードでは `strata: ...` を stderr に出します（`strata_cli/cli.py:527-532, 2166-2183`）。

## 根拠

- `strata_cli/cli.py:343-347` — `bench compare` parser、値の選択肢と既定値、`--out`。
- `strata_cli/cli.py:508-515, 2232-2235` — `--json` / `--quiet` の登録と JSON への変換。
- `strata_cli/cli.py:1129-1174, 2166-2183, 2236-2248` — `--out` 条件、比較・出力分岐、エラーと quiet の処理。
- `strata_cli/bench.py:891-949, 1006-1048` — 保存レポートの読込・検証と比較条件。
- `strata_cli/bench.py:1084-1117, 1258-1308, 668-677` — human/Markdown の整形、新規 Markdown ファイル出力と上限。
- `strata_control/profiles.py:30-31` — 比較・読込で使われる `ProfileError` の基底型。

調査範囲は上記 revision の checkout 内の Terminal CLI 実装です。同一 revision の CLI `--help` は実行しておらず、parser と実装を根拠にしました。Release 配布物や他 platform の挙動は確認していません。
