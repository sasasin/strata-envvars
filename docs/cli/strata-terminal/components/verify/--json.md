# `strata components verify --json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components verify` |
| オプション | `--json` |
| 別名 | なし（`--output json` が同等の指定） |
| 値 | 値を取らない真偽フラグ |

## 役割

検査処理を変えず、結果をスクリプトで扱える JSON 形式で stdout に出力します。`components verify` は指定した run config または保存済み profile を解決し、構成ファイルが参照するエンジン・tokenizer などのコンポーネントを検査します（`strata_cli/cli.py:1023-1031`、`strata_control/doctor.py:146-166`）。

## 使い方

```sh
strata components verify --profile /path/to/strata-model.json --json
```

保存済み profile 名も `--profile` に指定できます。GPU デバイスの live probe は別オプションです。

```sh
strata components verify --profile my-profile --live --json
```

`--profile` は必須で、`--live` は任意です（`strata_cli/cli.py:116-119`）。

## 値と既定値

- `--json` は `argparse` の `store_true` action で、値を取りません。省略時は偽で、`--output` の既定値 `human` により人間向け出力になります。繰り返し指定しても真のままです（`strata_cli/cli.py:116-119,508-514`）。
- `--json` を付けると、`main()` が `a.output` を `json` に設定します。これは `--output json` と同じ出力モードです。`--json --output human` のように併記した場合も、後段の正規化により JSON が選ばれます（`strata_cli/cli.py:119,2232-2235`）。
- `--json` の後ろに値を渡す形式はありません。余分な引数や未定義オプションは argparse のエラーとなり、usage とエラーを stderr に出して終了コード 2 になります（`strata_cli/cli.py:2223-2235`）。

## 実行時の動作

parser は `components_verify` を `--json` を共通登録する one-shot parser 群に含めます。`main()` はこのコマンドの `--json` を `a.output = "json"` に変換し、`components` の通常ルートから `_doctor()` を呼びます（`strata_cli/cli.py:508-515,2232-2237,2138-2139`）。

JSON 成功時の stdout は1行の JSON object で、外側に `schema_version: 1`、`ok`、`report` を含みます。`report` には検査対象の profile/config、components、issues、backend などが入ります。JSON 化によって検査項目は増えず、`--live` を指定した場合だけ live GPU probe が実行され、その結果が report に含まれます（`strata_cli/cli.py:1023-1031`、`strata_control/doctor.py:146-160,223-235`）。

## 適用条件と副作用

- このオプションは `strata components verify` の parser に属します。他のコマンドへの適用可否は各コマンドの parser によります。索引上の配置は [`docs/cli/README.md`](../../../README.md) の `strata components verify` 節です。
- `--json` 自体は出力形式を選ぶだけです。通常の検査は構成ファイルや参照先を読み取り、レポート生成のために構成を書き換える処理は確認できません（`strata_control/doctor.py:162-183,223-235`）。ただし Windows で `PermissionError` が起きると、共通の回復処理が一度 Strata のユーザーデータ領域のアクセス権を修復してから再実行する場合があります（`strata_cli/cli.py:2085-2104,2166-2178`、`strata_control/private_files.py:506-565`）。`--live` を付ける場合は、ホスト GPU の probe も加わります（`strata_control/doctor.py:230-232`）。
- CLI 共通の起動処理として、引数解析より前に `private_files.adopt_user_defaults()` を呼びます。これは Windows でプロセス token の既定 owner/DACL を現在ユーザー向けに設定し、管理者実行時にそのプロセスが後から作るファイルの既定アクセスを調整する処理です。`--json` 固有の作用ではありません（`strata_cli/cli.py:2217-2223`、`strata_control/private_files.py:349-385`）。
- 共通の `--quiet` も登録されていますが、JSON モードでは `main()` が通常ルートを直接実行するため、人間向け出力の抑制動作を追加しません（`strata_cli/cli.py:513-515,2232-2243`）。

## 出力とエラー

- 検査レポートの `ok` は、重大度 `error` の issue がない場合に真です。必要なコンポーネントの欠落・無効状態は error issue になり得ます（`strata_control/doctor.py:223-235`）。レポートの `ok` が偽なら `_doctor()` は終了コード 5 を返します。これはレポート自体を JSON で出力した後の検査結果です（`strata_cli/cli.py:1029-1031,1045`）。
- profile 解決や設定読み込みなどが例外になった場合、JSON モードでは `{"schema_version":1,"ok":false,"error":{"code":...,"message":"..."}}` 形式を stdout に出します。通常の `ValueError` / `OSError` などは実際の終了コード（既定値 2 / 6 など）を返します（`strata_cli/cli.py:527-532,2166-2188`）。
- parser の引数エラーは JSON envelope ではなく argparse の usage/error 出力で、終了コード 2 です（`strata_cli/cli.py:2223-2235`）。

## 根拠

- parser と `--json` / `--quiet` の登録: `strata_cli/cli.py:116-119,508-515`
- フラグの JSON 出力への正規化、コマンド dispatch、共通起動処理: `strata_cli/cli.py:2138-2139,2217-2237`
- 検査結果の JSON envelope と通常結果の終了コード: `strata_cli/cli.py:1023-1045`
- JSON error envelope: `strata_cli/cli.py:527-532`
- 検査レポートの構造、error 判定、live probe の適用条件: `strata_control/doctor.py:146-160,162-183,223-235`
- Windows のアクセス権回復経路: `strata_cli/cli.py:2085-2104,2166-2178`、`strata_control/private_files.py:506-565`
- `--profile` の path/name 解決: `strata_control/profiles.py:382-388`
- Windows の process default owner/DACL 調整: `strata_control/private_files.py:349-385`

## 調査範囲

同一 revision のソース parser と処理経路を確認しました。CLI の `--help` は実行していません。ここに記載した挙動は上記 commit の checkout に基づきます。
