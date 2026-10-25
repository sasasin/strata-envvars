# `strata components update` の `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--json` |
| 別名 | なし（`--output json` と同じ出力モード） |
| 値 | 値を取らない真偽フラグ。既定値は `false` |

## 役割

更新結果を機械可読な JSON で標準出力に出します。`--json` は `--output json` の簡易表記です。更新内容や対象コンポーネントを変えるフラグではありません。

## 使い方

```sh
strata components update --json --check
```

`--check` は署名付き feed を読み、変更予定を報告します。更新パッケージそのものは取得しません。ただし feed の取得を行います。

## 値と既定値

`argparse` の `store_true` フラグで、値は不要です。省略時は `false` で、人向け出力になります。複数回指定しても真偽値が真になるだけです。パーサーは `components update` の `--output` に `human`、`json`、`jsonl` を許可し、既定値を `human` にしています（`strata_cli/update_cmd.py:30-59`）。

`--json` は `strata_cli/cli.py` が update parser 群を含む one-shot parser に追加し、help には「`--output json` の alias」として登録します（`strata_cli/cli.py:508-515`）。引数解析後、`main()` が `--json` を検出すると `a.output = "json"` に設定します（`strata_cli/cli.py:2217-2236`）。そのため `--json --output human` と併用した場合も、実行時の出力モードは `json` です。

`--json` に値を付ける構文はありません。`--output` に未定義の値を渡すと argparse の引数エラーになります。`--json` と `--output jsonl` を同時に指定すると、one-shot 専用の `--json` と JSON Lines の組み合わせとして拒否され、終了コード 2 のエラーになります（`strata_cli/cli.py:2232-2235,829-835`）。JSON Lines が必要な場合は `--output jsonl` だけを指定します。

## 実行時の動作

通常の人向け進捗・結果表示の代わりに、更新処理の完了時に JSON オブジェクトを標準出力へ出します。成功時は `schema_version: 1`、`ok`、feed 情報、コンポーネントごとの `results`、`exit_code` が含まれます。コンポーネント更新が失敗した場合も、処理結果を `results` に含め、`ok` は終了コードが 0 かどうかで決まります（`strata_cli/update_cmd.py:163-171,203-224`）。致命的な更新・feed・署名エラーは `schema_version: 1`、`ok: false`、`error.code`、`error.message` の JSON オブジェクトになります（同 `:167-172,225-234`）。

`--check` では同じ JSON 出力モードで feed と engine、Control、app の判定レポートを出力します。`check()` は feed 以外のパッケージをダウンロードせず、確認結果を state に記録します（`strata_cli/update_cmd.py:203-209`、`strata_control/updater.py:624-640`）。

`--json` が抑制するのは human 向けの進捗表示です。更新の実行時には `--output json` を機械出力モードとして認識し、進捗 event を表示しません（`strata_cli/update_cmd.py:62-84,163-172`）。一方、feed 読み込み、署名検証、コンポーネント更新などの処理は `--json` の有無で切り替わらず、通常の `components update` と同じです（同 `:197-224`、`strata_control/updater.py:1274-1297`）。

## 適用条件と副作用

このオプションは `strata components update` 用 parser に適用されます。共通の one-shot parser 登録により、同じ `--json` は `strata update` と `strata components rollback` にも追加されていますが、それぞれのコマンド文書の範囲です（`strata_cli/update_cmd.py:42-59`、`strata_cli/cli.py:508-515`）。

`--json` 自体はファイルやネットワークを操作しません。ただし併用する `components update` の通常処理は、署名付き feed を参照して engine と Control を更新し、失敗の種類に応じて終了コード 5、6、7 などを返すことがあります。出力形式の指定だけで更新の副作用がなくなるわけではありません（`strata_cli/update_cmd.py:1-11,197-224`）。稼働中 engine に対する待機・拒否の条件も `--json` によって変更されません。機械出力モードでは対話確認をせず、`--wait` がなければ updater 側の busy エラー経路に進みます（同 `:237-252`）。

## 出力とエラー

- 通常の成功は JSON を1オブジェクト出力し、更新結果に応じた終了コードを返します（`strata_cli/update_cmd.py:203-224`）。
- 捕捉された `UpdateError`、feed エラー、署名エラー、取得禁止、割り込みは、JSON モードでは `error.code` と `error.message` を持つ JSON エラーとして出力されます（同 `:167-172,225-234`）。
- 子処理単位の失敗は、全体エラーへの変換ではなく各 component の失敗結果として報告される場合があります。`run_update()` は失敗した component を記録し、成功済み component の変更を取り消さず、最も重い終了コードを返します（`strata_control/updater.py:1274-1297`）。
- `--json` と `--output jsonl` の併用は終了コード 2 で拒否されます。`--output jsonl` 単独では進捗 event と最終結果が JSON Lines で出力されます（`strata_cli/cli.py:2232-2235`、`strata_cli/update_cmd.py:62-84,203-224`）。

## 根拠

- `strata_cli/cli.py:508-515` — one-shot parser 群への `--json` 追加と help 上の alias 説明。
- `strata_cli/cli.py:2217-2236` — 引数解析後の `--json` から `--output json` への正規化。
- `strata_cli/update_cmd.py:30-59` — update parser の `--output` choices/default と、対象 parser 群。
- `strata_cli/update_cmd.py:62-84,163-234` — JSON/JSONL 進捗、成功出力、エラー出力、終了経路。
- `strata_cli/update_cmd.py:237-252` — JSON モードでの稼働中 engine に対する対話抑止。
- `strata_control/updater.py:624-640,1274-1297` — `--check` の処理と通常の更新処理。
- 関連するコマンド・オプションの一覧: [`docs/cli/README.md`](../../README.md) の `strata-terminal` 節。
