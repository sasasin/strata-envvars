# `--output`

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime cleanup` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |
| 既定値 | `human` |
| 調査対象 | Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25） |

## 役割

cleanup の結果を人向けの短い要約か JSON に切り替えます。`--output` はファイル名・出力先を受け取らず、cleanup の対象や終了処理を変えません。cleanup 自体は Strata が開始した leftover server / engine を調べて終了させる操作です。

## 使い方

```sh
strata runtime cleanup --profile dev --output json
```

`--profile` を省略して実行すると、記録された全 profile の leftover が対象になります。profile を指定した実行では、その profile の leftover に絞られます。

## 値と既定値

- 値は `human` または `json` のいずれか1つです。値を省略した場合、候補外の値を指定した場合は argparse が拒否します（`strata_cli/cli.py:233-237`）。
- 省略時は `human` です。同じ `--output` を複数回指定したときは argparse の通常の `store` 動作で最後に指定した値が残ります。
- 短縮別名・`--json` alias は cleanup parser に定義されていません（`strata_cli/cli.py:233-237`）。

## 実行時の動作

`strata runtime cleanup` の dispatcher は `--output json` のとき `runtime.cleanup(a.profile)` が返した結果に `schema_version: 1` を加え、JSON 1行を標準出力へ出します。`human`（既定）では終了した件数を表示し、該当すれば終了できなかった件数と識別できず残した件数も表示します（`strata_cli/cli.py:1331-1344`）。

cleanup の効果は `--output` と独立です。対象は owner が失われた Strata 管理下の leftover で、記録された PID の開始時刻とコマンドラインが記録値に一致し、記録上の親プロセスが同一プロセスとして稼働していない場合に限って終了対象になります。稼働中の owner に属する child や別プロセスは終了対象にしません。識別不能なプロセスは残して報告します（`strata_control/procs.py:269-291`; parser の安全条件: `strata_cli/cli.py:233-235`）。

終了対象には POSIX では再確認後 SIGTERM を送り、猶予後も同じプロセスなら SIGKILL を試みます。Windows では再確認後 `taskkill /F` を使います。終了できない process は `stuck` として結果に残ります（`strata_control/procs.py:294-328`）。

`--profile` を指定した場合、通常の leftover 処理に加えて、runtime state が残り owner lease が非アクティブなら stale state の回収を試みます。回収は子プロセスの終了と記録の検証を確認してから行い、ready file、条件に応じて socket や snapshot、marker、state file を削除します。稼働中 owner がある場合は回収しません（`strata_control/runtime.py:670-684,285-294,297-378`）。

## 適用条件と副作用

- `--output` 自体は表示形式だけに作用し、ファイル作成・上書きやプロセス操作はしません。プロセス終了・runtime state 回収は `runtime.cleanup()` の副作用です。
- `--profile` の省略は `None` のまま `runtime.cleanup()` に渡り全 profile の記録を走査します。指定時は profile 名を検証してから処理し、その profile に限定します（`strata_cli/cli.py:236-237`; `strata_control/runtime.py:670-680`; `strata_control/runtime.py:95-98`）。
- cleanup が全 leftover を終了でき、識別不能な process もなければ `ok: true`、`state: "cleaned"`、`exit_code: 0` になります。`stuck` または `unverifiable` があれば `ok: false`、`state: "failed"`、`exit_code: 6` です。結果には `ended`, `gone`, `stuck`, `unverifiable` の配列が含まれます。profile 指定時は stale state 回収を試みた結果を示す `recovered` も付加されます（`strata_control/runtime.py:675-684`; `strata_control/procs.py:331-342`）。

## 出力とエラー

- `human` は `ended N leftover process(es)` と表示します。`stuck` があれば `; N would not end`、`unverifiable` があれば `; N could not be identified here and were left alone` を加えます。`gone` の件数はこの短い表示には含まれません（`strata_cli/cli.py:1339-1344`）。
- `json` は `schema_version` と cleanup の戻り値を含む JSON object を標準出力へ出します。`ok` が false の場合もこの結果 object を出した後、戻り値の `exit_code`（cleanup が `stuck` / `unverifiable` を返す場合は `6`）で終了します（`strata_cli/cli.py:1336-1344`; `strata_control/runtime.py:682-684`）。
- 指定値の不正・欠落は argparse の usage/error と終了コード `2` です（`strata_cli/cli.py:233-237,2223-2231`）。不正な profile 名など cleanup の前に `ValueError` が発生すると、`human` は `strata: <理由>` を標準エラーへ、`json` は `{"schema_version":1,"ok":false,"error":{"code":2,"message":"..."}}` を標準出力へ出します（`strata_control/runtime.py:673-674`; `strata_control/runtime.py:95-98`; `strata_cli/cli.py:527-532,2166-2173`）。

## 根拠

- `strata_cli/cli.py:197-202,233-237` — `runtime cleanup` の parser 階層、`--profile` と `--output` の定義、および help の対象範囲。
- `strata_cli/cli.py:1331-1344` — `--output` による出力分岐、cleanup 呼び出し、終了コード。
- `strata_control/runtime.py:670-684` — cleanup の処理、profile 指定時の stale state 回収、結果構造。
- `strata_control/procs.py:269-291,294-342` — leftover の識別、終了・未終了結果。
- `strata_control/runtime.py:95-98,285-378` — profile 名の形式と owner lease / stale state 回収条件。
- `strata_cli/cli.py:527-532,2166-2183,2223-2231` — CLI 共通エラー形式と parser error 経路。

## 調査範囲

指定 commit の Python Terminal CLI parser と `strata_control` の cleanup 実装を確認しました。安全な同一 revision の CLI help は実行していません。OS ごとの signal / `taskkill` 動作そのもの、プロセス権限差、個々の環境での実際の cleanup 結果はこのソース調査では実行確認していません。
