# `--condition`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--condition` |
| 別名 | なし |
| 値 | serving suite の実行条件を表す小文字ラベル。最大40文字 |

## 役割

serving suite のレポートに、実行者が指定した条件ラベルを記録します。例として `baseline` や `monitor-default` を使えます。ラベルは利用者入力であり、監視ツールが接続されていたことや、その設定が有効だったことを検証しません（`strata_cli/cli.py:304`、`strata_cli/bench.py:857-874`）。

## 使い方

```sh
strata bench run --url http://127.0.0.1:8080 --suite serving-smoke \
  --condition baseline --out ./bench-baseline
```

`--condition` は `strata bench run` 専用で、索引上も `bench/run` のオプションです。上記は serving suite の例です。`--out` にはまだ存在しない出力ディレクトリを指定します（`strata_cli/cli.py:291-311`、`strata_cli/bench.py:755-756`）。

## 値と既定値

- 値は必須の文字列です。省略時は `None`（条件ラベルなし）です。値の型変換や `choices` は parser では指定されていません（`strata_cli/cli.py:304`）。
- serving suite では `^[a-z][a-z0-9_-]{0,39}$` に一致する値を受理します。先頭は小文字英字、その後は小文字英字・数字・`_`・`-` を使え、全体で1〜40文字です。大文字、空文字、空白、その他の記号は拒否されます（`strata_cli/bench.py:753-754`）。値を省略してオプションだけを書くと、値付き引数として parser が拒否します（`strata_cli/cli.py:304`）。
- 重複指定時の特別な集約処理はありません。argparse の通常の値付き引数として最後に解析された値が `a.condition` に入り、その値が実行処理へ渡されます（parser: `strata_cli/cli.py:304`、転送: `strata_cli/cli.py:1222-1225`）。

## 実行時の動作

`strata bench run` の既定 suite は `standard-v1` です。この標準 suite では `--condition` は適用されず、指定すると workload 固定のための拒否対象となります。CLI は他の serving 専用オプションとともに指定を検出して、エラー「do not apply to the standard suite」を返します（`strata_cli/cli.py:297-300,1237-1248`）。したがって、このオプションを使うときは `--suite serving-smoke` や他の serving suite を明示してください。

serving suite では値を `bench.run(..., condition=a.condition)` にそのまま渡し、測定リクエストや条件設定の変更には使いません。成功・失敗・キャンセルの結果 JSON に `condition` として保存され、summary と人向け表示でも参照されます。Markdown レポートでは「Operator condition」として表示し、比較レポートも baseline/candidate のラベルを表示できます（`strata_cli/cli.py:1222-1234`、`strata_cli/bench.py:857-874,952-975,1120-1128,1182-1201,1267-1270`）。

## 適用条件と副作用

- serving suite の実行にのみ適用されます。`--suite` の省略時は標準 suite なので指定できません（`strata_cli/cli.py:297-304,1237-1248`）。
- 条件ラベル自体は記録用です。監視の接続状態、設定、実行条件とサーバー状態との一致を検証しません（`strata_cli/bench.py:869-874,1247-1250`）。
- このオプションによる追加のファイルやネットワークアクセスはありませんが、serving suite 自体はサーバーに benchmark 要求を送り、指定した新規出力ディレクトリに進捗・結果を保存します。ラベルはその suite の通常レポートに含まれます（`strata_cli/bench.py:755-802,815-884`）。

## 出力とエラー

- 標準 suite に指定すると、CLI は stderr に `strata: --condition do not apply to the standard suite: the protocol fixes the workload (use --suite serving-smoke for a serving benchmark)` を出し、終了コード2を返します。JSON 出力モードでは `_error` が `ok: false` とエラー情報を JSON で出力します（`strata_cli/cli.py:527-532,1241-1248`）。
- serving suite で値が形式に合わない場合は `benchmark condition must be a lowercase name up to 40 characters` で拒否され、`ValueError` 経由で終了コード2になります（検証: `strata_cli/bench.py:753-754`、共通エラー処理: `strata_cli/cli.py:2166-2173`）。検証は `bench.run` の出力先確認やディレクトリ作成より前に行われるため、このエラーだけでは benchmark 出力ディレクトリは作成されません（`strata_cli/bench.py:753-756,792`）。
- workload が失敗しても条件ラベルは報告に残ります。レポートの `successful` が偽なら人向け実行結果は failed と表示され、CLI は終了コード6を返します（`strata_cli/bench.py:848-874,1124-1126`、`strata_cli/cli.py:1226-1234`）。

## 根拠

- `strata_cli/cli.py:291-315` — `bench run` parser、suite の既定値、`--condition` の宣言。
- `strata_cli/cli.py:1237-1248` — 標準 suite における指定拒否。
- `strata_cli/cli.py:1183-1234` — serving suite への値の引き渡し、表示と終了コード。
- `strata_cli/bench.py:744-756,792-802,857-884` — 値の validation、出力ディレクトリと進捗・結果ファイル、結果への記録。
- `strata_cli/bench.py:952-975,1120-1128,1182-1201,1247-1250` — summary・人向け表示・Markdown レポートと条件ラベルの検証上の限界。
- `docs/TERMINAL.md:145-154` — serving-suite の利用例、標準 suite との適用範囲、ラベルが監視接続を検証しない旨。

コマンド階層と文書配置は [CLI 索引](../../../README.md) を参照してください。調査は上記 commit のソースと利用者向け文書に限定し、CLI help の実行、build、テスト、ベンチマーク実行は行っていません。
