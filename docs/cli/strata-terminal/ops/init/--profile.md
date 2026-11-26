# `--profile`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata ops init` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済み serving profile の名前（必須） |

## 役割

初期化する operation recipe の保存先となる serving profile を指定する。指定した profile に、標準 recipe `restart`、`calibrate`、`check` を作成する。profile の JSON パスではなく、保存済み profile の ID を渡す。

## 使い方

```sh
# saved serving profile "local" に標準 recipes を初期化
strata ops init --profile local
```

## 値と既定値

値は必須で、parser 上の既定値はない。値の文字列形式は parser では制約されず、その後の profile 読み込みで検証される。profile ID は小文字 `a-z` で始まり、続く文字は小文字英字・数字・`_`・`-`、全体で1〜64文字でなければならない。空文字、パス、拡張子付きの JSON ファイル名は profile ID として無効。

指定した profile が保存されていない場合も失敗する。つまりこのオプションは profile の作成やパス指定を行わず、事前に `strata profile create` 等で作成された profile を参照する。

## 実行時の動作

`strata ops init` は `--profile` の値を recipe 初期化関数にそのまま渡す。profile を読み込んだ後、`restart`（`runtime.restart`）、`calibrate`（`engine.calibrate.measure`）、`check`（`components.verify`）の順に既定 recipe を確認する。まだ存在しないものだけを作成し、同じ名前・同じ kind の recipe がすでにあれば再利用するため、再実行は冪等。既存 recipe の内容は上書きしない。既存の同名 recipe の kind が期待値と異なる場合はエラーになる。

recipe は profile ディレクトリ下の `.ops/<profile>/<name>.json` に保存される。recipe ディレクトリとファイルは owner-only として作成され、POSIX では既存のディレクトリやファイルが symlink または不適切な権限の場合に拒否される。profile ディレクトリのルートは `STRATA_PROFILE_DIR` が設定されていればその値、なければ OS ごとの既定設定ディレクトリとなる。

## 適用条件と副作用

- `--profile` は `ops` の全サブコマンドで共通に登録されるが、この文書の対象 `init` では必須の保存済み profile ID として働く。
- profile 本体を更新せず、recipe 用のディレクトリと、欠けている標準 recipe ファイルを新規作成する。recipe ファイル作成時は排他作成を使い、同時作成で既に存在する場合は読み直す。
- `--output json`（または共通 alias の `--json`）を併用すると、成功結果に profile 名と今回新規作成した recipe 名の配列が含まれる。省略時は作成名の一覧、または `Recipes already initialized` を表示する。

## 出力とエラー

成功時は終了コード `0`。人間向け出力は `Created: <名前一覧>`、変更がなければ `Recipes already initialized`。JSON 出力は `ok: true`、`profile`、`created` を含む。

profile 名が不正、profile が未保存、または既存 recipe が不正・期待する kind と異なる場合はエラーになる。通常の `ValueError` 系は `strata: <message>` を stderr に出し、例外に指定された終了コードを返す（profile の形式エラーは `2`、未保存 profile や recipe の安全性・読込エラーは主に `5`）。JSON モードでは `{ "ok": false, "error": ... }` を stdout に出す。ファイル操作の `OSError` は整形したエラーを返し、CLI の一般的な file operation error code は `6`。

## 根拠

- `terminal/strata_cli/cli.py:283-295` — `ops init` の parser 階層。`--profile` は必須で値型・既定値・choices は指定されていない。
- `terminal/strata_cli/cli.py:539-546` — `ops` の各サブコマンドに `--json` と `--quiet` を追加。
- `terminal/strata_cli/cli.py:1461-1468` — `init` が profile を初期化関数に渡し、成功メッセージと JSON payload を構成。
- `terminal/strata_control/recipes.py:32-59` — recipe profile ID の形式、保存先、ディレクトリ symlink・権限の確認と作成。
- `terminal/strata_control/recipes.py:153-177` — profile 読込後の標準 recipe 名・kind、既存項目の検査、欠落項目の作成、および返却値。
- `terminal/strata_control/recipes.py:130-150` — recipe の排他新規作成、0600 指定、書込失敗時の部分ファイル削除。
- `terminal/strata_control/private_files.py:1-5` — private directory/file の POSIX mode と Windows ACL の設計。
- `terminal/strata_control/profiles.py:25,38-50,153-174` — profile ID の検証、profile 保存ディレクトリ、未保存 profile と破損時のエラー。
- `terminal/strata_cli/cli.py:558-573,2248-2265` — 成功・失敗の出力先と終了コードの処理。
- `terminal/strata_cli/cli.py:2335-2339` — `--json` を `--output json` として扱う処理。
