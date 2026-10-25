# `strata ops init --json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査時の checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops init` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 取らないフラグ。既定値は `false` |

## 役割

`--json` は `--output json` の別表記です。`strata ops init` の成功結果を機械処理しやすい JSON オブジェクトで標準出力へ出します。recipe の初期化内容は変えず、表示形式だけを切り替えます。

## 使い方

```sh
strata ops init --profile local --json
```

`--profile` は必須です。`--json` は値を伴わず指定します。同じ効果を `--output json` で指定できます。

## 値と既定値

`argparse` の `store_true` フラグであり、値を受け付けません。省略時は `false` となり、人間向け出力が選ばれます。明示時は CLI の共通処理が `output` を `json` に設定します。`--json true` のような書き方は引数 parser で余分な引数として拒否されます。

## 実行時の動作

`--json` は各 one-shot `ops` parser に共通登録され、`main()` が monitor 系以外のコマンドについて `--json` を `output=json` に正規化します。`_ops()` は `a.output == "json"` を機械出力の判定に使います。成功時には次の形式で出力し、終了コード `0` を返します（`created` はこの実行で作成された recipe ID の配列です）。

```json
{"schema_version":1,"ok":true,"profile":"local","created":["restart","calibrate","check"]}
```

初期化は保存済み profile を読み込み、標準 recipe `restart`（`runtime.restart`）、`calibrate`（`engine.calibrate.measure`）、`check`（`components.verify`）を作成します。既存の同名 recipe が正しい kind なら上書きせず、足りないものだけ作成します。すべて既に存在する場合も成功し、`created` は空配列です。

## 適用条件と副作用

`--profile NAME` が指す保存済み profile が必要です。recipe は profile 設定ディレクトリの `.ops/NAME/` 以下に保存されます。既定の profile ディレクトリは Unix 系では `$XDG_CONFIG_HOME/strata/profiles`（未設定時は `~/.config/strata/profiles`）、Windows では `%APPDATA%/Strata/profiles`（未設定時はユーザーの `AppData/Roaming`）です。`STRATA_PROFILE_DIR` を設定するとこの保存先を置き換えます。

不足するディレクトリを作り、recipe ファイルを新規作成します。ファイル作成は排他で行い、mode `0600` を指定します。recipe ディレクトリと POSIX 上の owner-only 制約も検証されます。Windows の ACL を含む全 platform の実行結果はこの調査では確認していません。初期化自体は recipe の記録にとどまり、recipe が表す操作の実行は行いません。

## 出力とエラー

成功 JSON は標準出力に1行で出ます。失敗時、JSON モードでは `{"schema_version":1,"ok":false,"error":{"code":N,"message":"..."}}` 形式のエラー JSON を標準出力に出し、同じ `N` を終了コードとして返します。profile 不在・不正や既存 recipe の kind 不一致などの `ProfileError` は通常終了コード `2`、recipe 保存領域・ファイルの安全性に関する一部エラーはコード `5` です。ファイル操作の `OSError` は整形したエラー JSON とコード `6` になります。JSON は出力形式なので、失敗条件や終了コードは変更しません。

## 根拠

- `strata_cli/cli.py:255-267` — `ops init` parser、必須の `--profile`、既定 `human` の `--output`。
- `strata_cli/cli.py:508-515` — `ops` を含む one-shot parser への `--json` 登録（`store_true`）。
- `strata_cli/cli.py:1391-1398` — `init` 分岐と、`output=json` による成功 payload の選択。
- `strata_cli/cli.py:527-542` — JSON 成功・失敗 envelope と終了コード。
- `strata_cli/cli.py:2217-2237` — parser 実行、`--json` から `output=json` への正規化。
- `strata_cli/cli.py:2166-2183` — `ValueError` / `OSError` の失敗出力と終了コード処理。
- `strata_control/recipes.py:153-177` — profile 読み込み、標準 recipe、kind 事前確認、既存を保持した不足分の初期化。
- `strata_control/recipes.py:38-64,130-150` — profile 設定、owner-only directory 検証、排他新規作成、mode `0600`。
- `strata_control/profiles.py:38-45,150-166` — profile 保存ディレクトリと保存済み profile の読み込み・validation。
