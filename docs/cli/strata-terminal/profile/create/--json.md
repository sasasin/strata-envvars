# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile create` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らない boolean flag。省略時は `False` |

## 役割

作成処理の結果を JSON 形式で標準出力へ出します。`strata profile create` では `--output json` の別表記です。プロファイルを作成するかどうかや、作成内容は変えません。

## 使い方

```sh
strata profile create workstation --from-config /path/to/strata-model.json --json
```

`workstation` は新しいプロファイル名、`--from-config` の値は有効な run config のパスです。ソース checkout から起動する場合の入口は `python strata.py profile create ...` です。

## 値と既定値

値は不要です。指定すると `json=True` となり、CLI の共通処理が `output` を `json` に設定します。未指定時の `json` は `False` で、既定の出力形式は `human` です。`--output` は `human` または `json` のみを受理し、既定値は `human` です。したがって `--json` は `--output json` と同じ形式を選びます。両方指定した場合も JSON 出力になります。

この option は `profile create` の parser に追加されるため、他のコマンドに対する有効性はこの文書の対象外です。名前と `--from-config` は別途必須です。

## 実行時の動作

`--json` が有効な場合、作成成功時は次の形式の JSON オブジェクトを標準出力に1行で出します（`profile` と `revision` の値は実行結果です）。

```json
{"schema_version": 1, "ok": true, "profile": {"schema_version": 1, "id": "workstation", "source_config": "/path/to/strata-model.json", "overrides": {}}, "revision": "0123456789abcdef"}
```

作成処理自体は `profiles.create(name, from_config)` が行います。プロファイル名を検証し、run config を読み込んで形式を確認した後、プロファイルファイルを新規作成します。JSON 出力はその保存結果を機械処理しやすい形式で返すもので、設定の意味や作成時の副作用を変更しません。

成功時の JSON 化は `--output json` と共通で、`--json` 指定時には `output=json` になるため、`--quiet` も同時に指定しても JSON 結果は抑制されません。

## 適用条件と副作用

`--json` 自体は出力形式だけを選択し、ファイル・ネットワーク・プロセスへの独自の副作用はありません。ただしコマンド本体は新しいプロファイルを保存します。保存先は `STRATA_PROFILE_DIR` があればそのディレクトリ、Windows では `%APPDATA%/Strata/profiles`（未設定時はユーザーの `AppData/Roaming/Strata/profiles`）、それ以外では `$XDG_CONFIG_HOME/strata/profiles`（未設定時は `~/.config/strata/profiles`）です。保存先のファイルが既にある場合は上書きせず失敗します。

プロファイル名は小文字アルファベットで始まり、続きは `a-z`、`0-9`、`_`、`-` のみ、全体で1〜64文字です。`--from-config` は存在するパスに解決でき、JSON の object に `args`（文字列配列）、`exe` と `tokenizer`（空でない文字列）が必要です。

## 出力とエラー

実行時の `ValueError` / `ProfileError` などは、JSON モードでは標準出力に `schema_version: 1`、`ok: false`、`error: {code, message}` を含む JSON を出します。標準の `ProfileError` code は `2` です。読み込み不能・run config 不在など一部のエラーは code `5` を持ちます。作成済みプロファイルとの名前重複は `ProfileError` となり、既存ファイルを置換しません。

必須引数の欠落や不正な option など parser 段階のエラーは、dispatch 前に argparse の usage/error 経路へ進みます。これは `--json` による実行時エラー JSON とは異なり、`ap.error(...)` による終了 code `2` です。

## 根拠

- `strata_cli/cli.py:69-74` — `profile create` parser と `--output` の選択肢・既定値。
- `strata_cli/cli.py:508-515` — `profile_create` を含む one-shot parser 群に `--json` を追加。
- `strata_cli/cli.py:958-963` — `create` の dispatch、作成結果の成功 JSON / human 出力。
- `strata_cli/cli.py:527-542` — 成功・失敗時の JSON envelope と stdout/stderr。
- `strata_cli/cli.py:2166-2173`, `2223-2237` — 実行時エラー処理、`--json` から `output=json` への変換、quiet 分岐。
- `strata_control/profiles.py:25-35`, `48-55` — profile 名の validation と profile ファイル path。
- `strata_control/profiles.py:38-45` — 保存先ディレクトリの環境変数・OS 別既定値。
- `strata_control/profiles.py:135-147` — run config の読み込みと必須構造。
- `strata_control/profiles.py:236-249` — source path 解決、run config 検証、新規ファイルのみの作成。

索引: [`docs/cli/README.md`](../../../README.md)。このコマンドの概要・関連 option 文書は索引の [`profile create`](README.md) 節を参照してください。
