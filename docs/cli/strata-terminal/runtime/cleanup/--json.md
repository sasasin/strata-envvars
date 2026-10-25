# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime cleanup` |
| オプション | `--json` |
| 別名 | `--output json` |
| 値 | 値を取らないフラグ。JSON 出力を選択する |

## 役割

cleanup の処理結果を機械処理しやすい JSON で標準出力へ出します。`--json` は cleanup 対象や終了方法を変えません。

## 使い方

```sh
strata runtime cleanup --json
strata runtime cleanup --profile my-profile --json
```

`--output json` も同じ出力モードです。`--json` は one-shot コマンド向けの共通 alias として `runtime cleanup` に登録されています（`strata_cli/cli.py:508-515`）。

## 値と既定値

`--json` は `argparse` の `store_true` で、値を取りません。未指定時は false で、通常は human-readable な要約を出します。複数回指定しても true のままです（`strata_cli/cli.py:513`）。

このコマンドでは `--output` の選択肢は `human` または `json`、既定値は `human` です（`strata_cli/cli.py:233-237`）。`--json` を指定すると、引数中の順序にかかわらず `--output` は `json` に設定されるため、たとえば `--output human --json` も JSON 出力になります（`strata_cli/cli.py:2232-2236`）。

## 実行時の動作

`_runtime` は `a.output == "json"` を機械出力モードとして cleanup 処理を呼び、結果辞書に `schema_version: 1` を加えて JSON 化し、標準出力に1行出します（`strata_cli/cli.py:1331-1338`）。成功・失敗時の基本形は cleanup の結果辞書で、`ok`、`state`、`ended`、`gone`、`stuck`、`unverifiable`、`exit_code` などを含みます。JSON 化は `ensure_ascii=False`、`allow_nan=False` です（`strata_control/runtime.py:682-684`; `strata_cli/cli.py:1336-1338`）。

処理本体は `runtime.cleanup(a.profile)` です。`--profile` を省略すると記録された全 profile の leftover を調べ、指定すると名前が一致する記録に対象を絞ります。生きている親プロセスが記録どおり存在する子プロセスは leftover 扱いされず、記録 PID の開始時刻 token とコマンドラインが一致しないプロセスも終了対象にしません。cleanup は PID だけでプロセスを特定して終了させる処理ではありません（`strata_control/runtime.py:670-675`; `strata_control/procs.py:253-264,269-291`）。

確認できた leftover は記録時刻の新しい順に処理され、終了直前にも PID・開始 token・コマンドラインを再確認します。POSIX では SIGTERM 後8秒待機して残存すれば SIGKILL、Windows では確認後 `taskkill /F` を実行します。さらに最大10秒終了を確認し、結果を `ended` / `gone` / `stuck` に分類します。コマンドラインを読み取れず身元を確認できないプロセスは `unverifiable` に記録して残します（`strata_control/procs.py:294-328,331-342`）。

## 適用条件と副作用

- `--profile NAME` は任意です。指定値は runtime の profile 名規則で検証され、不適切な名前はエラーになります（`strata_cli/cli.py:236`; `strata_control/runtime.py:670-675`; `strata_control/runtime.py:95-98`）。
- profile を指定した場合、該当する runtime state があり、owner lease が有効でなければ、cleanup は stale runtime state の回収も試みます。回収では子プロセスの終了・所有記録を確認したうえで、ready file、POSIX control socket、rollback snapshot、marker などの stale artifact を削除します。確認不能または live runtime と判定された場合は回収を拒否します（`strata_control/runtime.py:676-680,297-320,321-372`）。
- leftover の終了はプロセスへのシグナル送信または Windows の強制終了を伴います。`--json` 自体はこの副作用を抑止・追加しません（`strata_control/procs.py:294-328`; `strata_cli/cli.py:1334-1344`）。
- profile 名が有効でも、保存済み profile の存在を `--json` が別途検証するわけではありません。profile 名の検査と、見つかった runtime state / process record の処理が実行されます（`strata_control/runtime.py:670-680`）。

## 出力とエラー

通常完了時は JSON オブジェクト1行が stdout に出力されます。検証済み leftover が終了できない、または身元を確認できないものがある場合、結果は `ok: false` / `state: "failed"`、終了コードは `6` です。正常時は `ok: true` / `state: "cleaned"`、終了コード `0` です（`strata_control/runtime.py:682-684`; `strata_cli/cli.py:1336-1344`）。

profile 名などの実行時例外は CLI の共通エラーハンドラーを通ります。機械出力モードでは `{schema_version, ok: false, error: {code, message}}` を JSON で出し、`ProfileError` が持つ終了コードを返します。profile 名不正の例はコード `2`、回収時に安全性を確認できない場合はコード `6` です（`strata_cli/cli.py:527-532,2166-2173`; `strata_control/profiles.py:30-35`; `strata_control/runtime.py:307-320`）。無効な `--output` 値や未知引数など parser 段階のエラーは argparse の usage/error 経路です。

## 根拠

- parser と `--output` の既定値: `strata_cli/cli.py:233-237`
- one-shot parser 群への `--json` 登録: `strata_cli/cli.py:508-515`
- alias の解決と dispatch: `strata_cli/cli.py:2232-2236,1331-1344`
- cleanup 対象・戻り値・profile ごとの stale state 回収: `strata_control/runtime.py:670-684`
- プロセス record の抽出・照合・終了処理: `strata_control/procs.py:253-291,294-342`
- stale state 回収の検証と artifact の整理: `strata_control/runtime.py:297-372`
- 機械出力のエラー形式と `ProfileError`: `strata_cli/cli.py:527-532,2166-2173`; `strata_control/profiles.py:30-35`

調査範囲は上記 commit の checkout に含まれる Terminal CLI と runtime/process 管理実装です。同一 revision の CLI `--help` は補助資料として実行していません。Release 配布物ごとの差、OS ごとの実機動作は確認していません。
