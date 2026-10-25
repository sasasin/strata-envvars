# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata doctor` |
| オプション | `--json` |
| 別名 | なし（`--output json` と同じ出力形式を選ぶ別指定） |
| 値 | 値を取らない真偽フラグ。既定値は無効 |

## 役割

診断結果を機械処理しやすい JSON で標準出力へ出します。`--json` は doctor の `--output` を `json` にする one-shot オプションです。`--output json` も同じ JSON 出力経路を選べます。

## 使い方

```sh
strata doctor --json
strata doctor --profile my-profile --json
strata doctor --profile ./run-config.json --json
```

`--profile` は保存済みプロファイル名、または run-config JSON のパスを受け取ります。パス形式の値は JSON ファイルとして扱われ、保存名へのフォールバックはありません（`strata_control/profiles.py:382-388`）。

## 値と既定値

`--json` は `argparse` の `store_true` フラグで、引数値を取りません。doctor parser の `--output` は `human` / `json` の選択肢を持ち、既定値は `human` です（`strata_cli/cli.py:109-113`）。one-shot コマンド群には共通処理で `--json` が追加され、既定値は無効です（`strata_cli/cli.py:508-515`）。

`--json` が有効なら、`--output` の値にかかわらず main 処理が `output` を `json` に設定します。したがって `--output human --json` も JSON になります。`--output` に指定できる値以外は parser が拒否します（`strata_cli/cli.py:109-113, 2232-2235`）。

## 実行時の動作

doctor の診断自体は `inspect_components()` に委譲されます。JSON モードでは標準出力に1行の JSON object を出します。外側の形式は `{"schema_version": 1, "ok": <診断結果>, "report": <診断レポート>}` で、UTF-8 文字をそのまま出力し、NaN 等の非標準数値は許可しません（`strata_cli/cli.py:1023-1031`）。

レポートには schema version、profile/source_config、component 一覧、issues、backend、選択デバイス、live GPU probe が含まれます（`strata_control/doctor.py:146-149`）。`--profile` を省略した場合も CLI/monitor の項目を含むレポートを返します。`--live` も省略なら live probe は実施されません（`strata_control/doctor.py:151-160, 230-235`）。

## 適用条件と副作用

このオプションは `strata doctor` の出力形式にだけ作用し、診断項目や検査範囲を変更しません。診断関数はファイル・実行可能性・設定内容などを読み取ります。`--live` を併用した場合、ホストの NVIDIA GPU 情報を照会する経路があり、`nvidia-smi` を最大5秒で実行します。これは `--json` 自体ではなく `--live` による動作です（`strata_control/doctor.py:44-53, 80-115, 230-232`）。

JSON モードでは通常の人間向け component/issue 行は出力されません（`strata_cli/cli.py:1029-1044`）。`--quiet` と併用しても JSON は抑止されません。main は JSON 出力を quiet capture の対象外にします（`strata_cli/cli.py:2236-2237`）。

## 出力とエラー

診断レポートの `ok` が偽でも report JSON を出し、終了コード `5` を返します。成功時は `0` です（`strata_cli/cli.py:1045`）。プロファイル解決や設定読み込みで捕捉対象の `ValueError` / `OSError` が起きた場合は、標準出力に `schema_version`、`ok: false`、`error` を含む JSON エラー object を出します。エラーコードは例外側の `exit_code`（指定がなければ `2`、run-config 読み込みエラーは `5`）に従います（`strata_cli/cli.py:527-532, 2166-2183`; `strata_control/profiles.py:135-147`）。未知の引数は `argparse` がエラーとして扱います（`strata_cli/cli.py:2223-2231`）。

## 根拠

- parser と `--output` の選択肢: `strata_cli/cli.py:109-113`
- one-shot `--json` の追加とフラグ設定: `strata_cli/cli.py:508-515`
- `--json` から `output=json` への正規化: `strata_cli/cli.py:2232-2237`
- doctor の診断呼び出し、JSON 成功出力、終了コード: `strata_cli/cli.py:1023-1045`
- JSON エラー形式と例外処理: `strata_cli/cli.py:527-532, 2166-2188`
- 診断レポート、profile 未指定/live probe の条件: `strata_control/doctor.py:146-160, 230-235`
- `--live` による外部 GPU 照会の制約: `strata_control/doctor.py:80-115`
- profile 名と JSON path の解決、run-config 読み込み: `strata_control/profiles.py:135-147, 382-388`
