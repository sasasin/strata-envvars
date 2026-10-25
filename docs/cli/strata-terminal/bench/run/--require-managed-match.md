# `--require-managed-match`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata bench run` |
| オプション | `--require-managed-match` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定時は真、未指定時は偽。 |

## 役割

serving suite のベンチマーク対象が、指定した保存済み profile と一致するローカル管理 runtime であることを、負荷をかける前と終了時に確認する。合格したレポートでは `profile_running_match` が `managed_launch_checked` になる。この確認は開始時・終了時のチェックポイントであり、実行中の継続的な検証ではない（`strata_cli/cli.py:305-306`、`strata_cli/bench.py:173-203, 761-765, 852-877`）。

## 使い方

新しい出力先を使い、保存済み profile に対して serving suite を実行する例:

```sh
strata bench run --profile local --require-managed-match --suite serving-smoke --out ./bench-managed-check
```

この例は `local` という保存済み profile と、まだ存在しない `./bench-managed-check` を前提とする。serving suite では `--out` が必須で、出力先がすでに存在する場合は拒否される（`strata_cli/cli.py:291-311, 1186-1203`、`strata_cli/bench.py:755-756`）。

## 値と既定値

引数値を取らず、`argparse` の `store_true` により既定値は `False`。指定すると `bench.run` に `require_managed_match=True` が渡される（`strata_cli/cli.py:305-306, 1219-1225`）。

指定時には `--profile` が必要で、さらにその参照が保存済み profile 名として解決される必要がある。`--url` だけを指定した場合、および保存済み profile ではなく run config を直接参照した場合は、それぞれ `--require-managed-match needs a saved --profile` または `--require-managed-match needs a saved profile name` で終了コード 2 となる（`strata_cli/cli.py:294-296, 1197-1203`）。

## 実行時の動作

CLI は profile から設定ファイル、revision、model 名、GPU 情報を読み、設定ファイルの SHA-256 を含む profile identity を作る。接続 URL は profile の有効 host/port から組み立てる。`0.0.0.0` と `::` は接続先として `127.0.0.1` に置き換えられる（`strata_cli/cli.py:1199-1217`）。

ベンチマークは telemetry snapshot を取得し、モデルがロード済みであることを確認した後、suite の workload を始める直前に照合する。`_managed_match` は `runtime.status(profile)` と `runtime.plan_restart(profile)` を参照し、owner が `ready` で launch attestation・API identity・generation readiness を満たすこと、profile/source に変更がないこと、snapshot と owner の instance ID が一致すること、現在および候補 profile revision が保存済み revision と一致すること、owner の API URL が接続先と一致することを確認する（`strata_cli/bench.py:173-203, 757-765`）。

workload 終了後にも telemetry snapshot と管理状態を照合する。開始時と終了時の照合が通り、各 phase と instance の成功条件も満たす場合に限り `successful: true`、`profile_running_match: "managed_launch_checked"` となる。profile-running check の before/after 結果と制約説明も `results.json` に記録する（`strata_cli/bench.py:843-880`）。

## 適用条件と副作用

- `--suite` の既定値 `standard-v1` ではこのオプションを使用できない。標準 suite は `--require-managed-match` を固定 workload に適用できないオプションとして扱い、エラーと終了コード 2 を返す。`--suite serving-smoke` などの serving suite を明示する（`strata_cli/cli.py:297-300, 1186-1188, 1237-1248`）。
- 保存済み profile によるローカル接続が前提であり、任意の URL や未管理の foreground/remote server をこの照合で検証するものではない。照合関数はローカルの `runtime` status と restart plan を呼び出す（`strata_cli/cli.py:1197-1217`、`strata_cli/bench.py:173-203`）。
- 事前照合に失敗すると workload の前に `ProfileError` で拒否され、該当の実行では benchmark 出力ディレクトリ作成より前に止まる。出力先の既存確認、最初の telemetry 検証、managed preflight の順に処理され、その後でディレクトリを作成する（`strata_cli/bench.py:755-765, 792`）。
- 実行中に profile/source、owner、instance または endpoint が変わるなど終了時の照合が失敗すると、実行済み workload の `results.json` は保存されるが `successful` は偽となる。通常の CLI は失敗レポートの場所を表示し、終了コード 6 を返す（`strata_cli/bench.py:843-888`、`strata_cli/cli.py:1226-1234`）。
- この照合は開始時と終了時だけで、実行中の変更を継続監視しない。また driver、model artifact hash、monitor の接続状態を証明しない（`strata_cli/bench.py:869-880`）。

## 出力とエラー

フラグ自体は出力先を指定しない。serving benchmark の出力ディレクトリに `progress.json` と `results.json` が作られ、後者に照合前後の結果が入る。成功・失敗レポートの通常表示では標準出力に要約と Evidence のパスを出し、機械出力 (`--output json`) では JSON の `ok`、パス、要約を出す（`strata_cli/bench.py:792-803, 857-888`、`strata_cli/cli.py:1221-1234`）。

フラグの適用条件違反や標準 suite での指定は終了コード 2。事前照合の不一致は `managed benchmark preflight failed: <reason>` となり、既定では stderr に `strata: ` を付けて表示して終了コード 5。事後照合を含む benchmark の失敗はレポートを保存して終了コード 6（`strata_cli/bench.py:761-765, 852-888`、`strata_cli/cli.py:527-532, 2166-2173, 1226-1234`）。

## 根拠

- parser、scope、suite 既定値: `strata_cli/cli.py:291-311`
- serving suite の引数検証、profile 必須条件、実行引数の受け渡し、終了コード: `strata_cli/cli.py:1183-1234`
- 標準 suite での拒否: `strata_cli/cli.py:1237-1248`
- 管理対象・profile・instance・endpoint 照合: `strata_cli/bench.py:173-203`
- preflight、出力作成、postflight、結果レポートと制約: `strata_cli/bench.py:744-765, 792-803, 843-888`
- 共通エラーの表示先と形式: `strata_cli/cli.py:527-532, 2166-2188`
