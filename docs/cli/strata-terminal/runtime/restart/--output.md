# `strata runtime restart --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（調査日: 2026-10-25）。

## 概要

`--output` は `strata runtime restart` の結果を人間向け表示または JSON で出力する。再起動処理そのものには値を渡さず、コマンドが受け取った結果の表示形式を選ぶ。

```sh
strata runtime restart --profile PROFILE --plan --output json
```

`PROFILE` は対象の保存済みプロファイル名に置き換える。上の例は `--plan` を付けて候補を確認する呼び出しであり、runtime を drain して再起動する実行例ではない。

## 値と既定値

- `human`: 既定値。状態、instance ID、API URL、launch 検証状態、readiness、エラーを人間向けの1行で表示する。
- `json`: `schema_version: 1` と runtime 操作結果を含む JSON オブジェクトを stdout に出す。

parser は `choices=("human", "json")`、`default="human"` として宣言する。別名 `--json` は one-shot コマンドに共通して後から追加され、指定時に `a.output = "json"` に置き換えられる。`--output` と `--json` を両方指定した場合は、argparse が後に処理した `--json` によって `json` になる。`--output` の値が許可外なら argparse の引数エラーとなり、処理には進まない。

## 実行時の動作と相互作用

`_runtime()` は `--output json` かどうかを `machine` として保持し、`management.runtime_action()` の引数に `output` は渡さない。restart の plan/実行結果を受け取った後、`human` なら状態などの1行、`json` なら `{"schema_version": 1, ...result}` を出力する。したがって `--output` は再起動可否、待ち時間、drain、起動、rollback には影響しない。

`--plan` と併用した場合も restart は汎用 runtime 結果の表示経路を通る。plan が成功すると、JSON では返された plan の項目（profile、owner/instance ID、候補 revision、source config と digest、argv、変更有無など）を含む結果が出力され、human では `PROFILE: ready` のような短い状態表示になる。`start` / `stop` / `verify` の成功 plan のように `_success()` で plan 全体を出す特例は restart には適用されない。

`--quiet` は one-shot コマンドとして restart にも追加される。human 出力の場合は成功時の stdout を抑制し、失敗時には捕捉した出力を stderr に出す。JSON 出力は quiet 時も通常どおり出力する。`--json` は `--output json` と同じ扱いになる。

## 出力と失敗経路

- JSON: runtime 操作が返す `ok`, `state`, `error`, `exit_code` などを `schema_version: 1` とともに stdout に出す。結果の `ok` が偽なら、返却 `exit_code` を使い、なければ `6` で終了する。
- human: `PROFILE: STATE` と、存在する場合は instance ID、API URL、launch verification、readiness label、エラーを stdout に表示する。失敗時の restart では engine log の場所と末尾3行を stderr に追加する。
- runtime 管理で `ValueError` / `ProfileError`、`OSError`、`ClientError` などが例外として上がった場合、JSON 選択時は `schema_version`, `ok: false`, `error.code`, `error.message` の JSON を stdout に出す。human 選択時は `strata: ...` を stderr に出す。
- argparse の未知引数や選択肢違反は runtime handler 前に拒否され、parser の usage/error が stderr に出て終了コード `2` となる。

このオプションは出力の形式だけを変える。restart 自体は owned かつ ready な runtime を対象とし、候補確認、実行前提条件、source 変更の許可、drain 後の起動や失敗時 rollback を行う。詳細な再起動の適用条件・副作用は `--output` の説明範囲外であり、management/runtime の処理に記載されている。

## 根拠

確認した Strata ソース（上記の同一 commit）:

- `strata_cli/cli.py:238-254` — `runtime restart` parser と `--output` の値・既定値。
- `strata_cli/cli.py:508-515` — one-shot parser 群へ `--json` と `--quiet` を追加。
- `strata_cli/cli.py:1331-1373` — runtime 結果の JSON/human 出力、失敗時の engine log hint、終了コード。
- `strata_cli/cli.py:527-542` — 例外時エラー形式と `_success()` の JSON 表示。
- `strata_cli/cli.py:2119-2193` — runtime dispatch、ValueError/OSError/ClientError/KeyboardInterrupt の出力と終了コード。
- `strata_cli/cli.py:2223-2247` — argparse の未知引数処理、`--json` の `--output json` への変換、quiet 時の処理。
- `strata_control/management.py:292-336` — restart の plan/実行分岐。表示形式が restart 呼び出しへ渡らないこと、検査・journal・runtime 呼び出し。
- `strata_control/runtime.py:702-740` — restart 実行 API と timeout/source digest validation、plan API。
- `strata_control/runtime.py:1043-1130` — 再起動前提の確認、停止・新起動、失敗時 rollback と返却結果。
- `strata_control/runtime.py:1132-1164` — plan 結果に含まれる情報と、plan が drain/start をしないこと。

同一 revision の CLI `--help` は補助確認に使っていない。ビルド済み CLI、Release 配布物、異なる OS/backend での実行出力は調査していない。
