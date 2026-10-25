# `strata bench run --quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

成功時の人間向け標準出力を抑制します。ベンチマークの実行、結果の保存、サーバーとの通信、必要に応じたエンジン起動を省略するオプションではありません。

## 使い方

```sh
strata bench run --profile my-profile --quiet
```

`--profile` の代わりに `--url` を指定することもできます。`--suite` の既定値は `standard-v1` で、serving suite では通常 `--out NEW_DIRECTORY` が必要です。実行は通常どおりベンチマークを行い、結果を保存します（`strata_cli/cli.py:291-311,1186-1190`）。

## 値と既定値

`--quiet` は `store_true` のフラグで、値は不要です。one-shot コマンド用の parser 群に共通追加され、`bench_run` もその対象です。省略時は `argparse.SUPPRESS` により `quiet` 属性が作られず、実行時の `getattr(a, "quiet", False)` で無効として扱われます。`--quiet=true` のような値指定は受け付けません。独自の値 validation はありません（`strata_cli/cli.py:508-515,2236-2243`）。

## 実行時の動作

`--quiet` が有効で `--output` が `json` / `jsonl` でない場合、CLI は `_run()` が標準出力へ書く内容を最大64 KiBの捕捉領域へ一時的に送ります。コマンドが終了コード0なら捕捉内容を表示せず、非0なら捕捉内容を標準エラーへ戻します。64 KiBを超えた場合は末尾64 KiBを保持し、失敗時には先行出力を省略した旨も標準エラーへ出します（`strata_cli/cli.py:2196-2214,2236-2248`）。

`--output json` または alias の `--json` を指定すると、quiet の捕捉処理を通らず JSON を標準出力に出します。`--json` は parser 後処理で `output=json` に変換されます（`strata_cli/cli.py:513-515,2232-2237`）。

## 適用条件と副作用

- 索引上のスコープは `strata bench run` です。同じ `--quiet` が他のコマンドにも登録されていますが、別コマンドでの意味はこの文書の対象外です（`docs/cli/README.md:610-638`; `strata_cli/cli.py:508-515`）。
- `standard-v1` と serving suite のどちらにも parser 上は適用されます。quiet は suite 選択や workload、validation、結果内容を変えません。標準 suite では新規結果ディレクトリとレポートを作成し、serving suite では `--out` の新規ディレクトリに進捗・結果を保存します（`strata_cli/cli.py:297-334,1183-1195,1279-1282`; `strata_cli/bench.py:744-756,792-802,881-887`; `strata_cli/bench_standard.py:766-780,835-840`）。
- suite が `standard-v1` の場合、profile のサーバーが応答しなければ `--no-start` が指定されていない限りエンジンを起動し、終了処理で停止します。既に応答している profile サーバーは停止しません。serving suite は選択した URL への要求を実行します。これらのプロセス・ネットワーク上の作用は quiet でも発生します（`strata_cli/cli.py:1288-1305,1306-1311`; `strata_cli/bench.py:813-887`）。
- ベンチマーク処理中の出力は明示的に標準エラーへ送られるため、進捗・ログは `--quiet` でも表示される場合があります。quiet が抑えるのは標準出力です（`strata_cli/cli.py:1221-1234,1289-1305`）。

## 出力とエラー

- 既定の `--output human` では、成功時の標準出力サマリーと結果パス表示を抑制します。ベンチマークの失敗は serving suite で終了コード `6`、standard suite でも不完全な結果や開始したエンジンの停止失敗などで `6` になり得ます。quiet は失敗を成功に変えません（`strata_cli/cli.py:1226-1234,1312-1328`）。
- 人間向けのエラーは標準エラーに出ます。quiet 捕捉中に標準出力へ既に出力された内容がある場合、それも失敗時に標準エラーへ戻されます。捕捉領域を超過した場合は `strata: earlier human output omitted in quiet mode` が先に出ます（`strata_cli/cli.py:527-532,2166-2193,2241-2248`）。
- `--output json` / `--json` では JSON 出力を標準出力に維持します。benchmark が完了して不成功なら結果 JSON の `ok` が false となり、終了コード `6` です（`strata_cli/cli.py:1226-1234,1321-1328,2232-2237`）。
- argparse による未知引数など、`_run()` より前に発生する解析エラーは quiet 捕捉の対象外です（`strata_cli/cli.py:2223-2231,2236-2243`）。

## 根拠

- 索引のコマンド階層と予定リンク: `docs/cli/README.md:610-638`。
- `bench run` parser、suite 既定値、出力形式: `strata_cli/cli.py:291-334`。
- one-shot parser 群への `--quiet` / `--json` 登録: `strata_cli/cli.py:508-515`。
- serving suite の検証、処理、標準出力/標準エラー: `strata_cli/cli.py:1183-1234`; `strata_cli/bench.py:744-887`。
- standard suite の quiet 対象外ログ、結果表示、終了処理: `strata_cli/cli.py:1237-1328`; `strata_cli/bench_standard.py:766-840`。
- 共通 quiet 捕捉、失敗時の再出力、JSON 出力の例外: `strata_cli/cli.py:2196-2248`。

調査時の Strata checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されませんでした。確認したのは記載した commit のソースと索引です。同一 revision の CLI help、Release 配布物、別 platform の実行結果との照合は行っていません。
