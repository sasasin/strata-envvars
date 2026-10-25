# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile validate` |
| オプション | `--json` |
| 別名 | なし（`--output json` でも同じ出力形式を指定可能） |
| 値 | 値を取らないフラグ。既定では無効 |

## 役割

検証結果を機械処理向けの JSON で出力します。`profile validate` は保存済みプロファイルと参照先の run config から起動 plan を組み立てて検査しますが、推論サーバーや engine は起動しません。

## 使い方

```sh
strata profile validate default --json
```

`default` は検査する保存済みプロファイル名です。`--output json` も同じ出力を選びます。

## 値と既定値

`--json` は `store_true` のフラグで、値を付けません。指定しない場合の `--output` は `human`、指定すると `json` になります。共通の one-shot parser 登録で `profile validate` に追加され、起動時に `--json` が有効なら `main` が `output` を `json` に設定します。従って `--json` と `--output human` を併記しても JSON が選ばれます。`--output` は `human` / `json` のみを受理し、不正な値や `--json=true` のような値付き指定は parser エラーです。

## 実行時の動作

JSON モードの成功時は stdout に1行の JSON を出し、`schema_version: 1`、`ok: true`、プロファイル名、revision、検証した `plan` を含めて終了コード `0` を返します。通常の人間向けモードでは成功時に `Profile <name> is valid at revision <revision>` を表示します。

検証はプロファイルを読み込み、run config の構造、profile override の範囲、override と run config 引数の競合などを確認し、実効値と server / engine 引数を含む plan を構築します。API key の形式も起動 plan の作成時に検査します。このオプション自体は出力形式を変えるだけで、検証範囲や設定値を変えません。

## 適用条件と副作用

この `--json` は `strata profile validate` のスコープです。同じ文字列が他コマンドにあっても、各コマンド固有の適用範囲・動作に従います。`--quiet` も指定できます。JSON モードでは構造化出力が維持されます。

検証経路は server / engine の起動、ネットワーク接続、profile 保存を行いません。一方、プロファイル読込時に Windows でアクセス拒否が起き、アクセス修復に成功した場合、Strata が対象ファイルのアクセス権を修復して再読込します。起動時の `adopt_user_defaults()` は Windows で後続の作成ファイルに使うプロセス既定 owner / ACL を設定します。

## 出力とエラー

JSON モードの失敗時は stdout に `schema_version: 1`、`ok: false`、`error.code`、`error.message` を含む JSON を出し、エラー種別に応じた非ゼロ終了コードを返します。たとえば保存済みプロファイルが見つからない場合はコード `5`、不正な profile / run config や override、競合では検査箇所に応じた `2` または `5` です。JSON 出力では個別エラーの内容が `message` に入り、`code` は終了コードです。JSON モードでない場合、共通エラー処理は `strata: ...` を stderr に表示します。

## 根拠

- `strata_cli/cli.py:81-83` — validate parser と `--output` の選択肢・既定値。
- `strata_cli/cli.py:508-515` — one-shot parser 群への `--json` / `--quiet` 登録。
- `strata_cli/cli.py:2232-2236` — `--json` から `output=json` への切替、および JSON 時の quiet 処理。
- `strata_cli/cli.py:958-960, 1015-1020` — profile の読込、validate 時の plan 作成、成功結果。
- `strata_cli/cli.py:782-826` — launch plan の検証と構築。API key 検査は `788-792`。
- `strata_cli/cli.py:527-542` — 成功 / 失敗時の JSON schema と出力先。
- `strata_cli/cli.py:2166-2188` — ValueError / OSError 等の JSON エラー変換と終了コード。
- `strata_control/profiles.py:98-147, 150-166` — override、profile、run config の検証と読み込み。
- `strata_control/profiles.py:476-484` — 読込時に Windows のアクセス修復後、再試行する処理。
- `strata_control/private_files.py:349-389` — Windows での process default owner / ACL 設定。
- `serve/server.py:3077-3129` — plan 構築で呼ばれる engine 引数の組み立て。

この文書は上記 commit のソースを根拠にしています。同一 revision の CLI `--help` は実行していません。
