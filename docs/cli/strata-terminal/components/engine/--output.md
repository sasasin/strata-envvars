# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engine` |
| オプション | `--output` |
| 別名 | なし |
| 値 | `human` または `json` |

## 役割

ローカルの engine component の状態を、人向け表示または JSON で出力します。engine package の選択、互換性確認、整合性確認の方法自体は変えません。

## 使い方

```sh
strata components engine --output json
```

component の場所を明示して確認する場合:

```sh
strata components engine --components-dir ./strata-components --output json
```

## 値と既定値

- `human` と `json` のみ受け付けます。省略時は `human` です。別の値を指定すると `argparse` が usage とエラーを標準エラーに出し、終了コード 2 で終了します。
- この parser に `--json` alias は定義されていません。`--output json` を指定してください。
- `--output` は `--backend`、`--components-dir`、`--full` と併用できます。出力形式を選ぶだけで、ほかの引数の解釈は変わりません。

## 実行時の動作

- `human` では component folder、検出した platform/backend、インストール済み package、問題のある package を表示します。利用可能なら選択された engine の実行ファイルと version も表示します。`json` では `schema_version: 1` と `ok` を含む status report 全体を JSON として標準出力に出します。report には component folder、platform、backend と検出元、installed 一覧、問題一覧、選択 engine、`usable`、notice、`acquires`、pin/previous 情報、更新通知が含まれます。
- engine が利用可能かの判定はどちらの形式でも実施されます。`--full` がなければ manifest の全ファイルについてサイズを調べ、entrypoint の SHA-256 を検証します。`--full` を付けると全ファイルの SHA-256 も検証します。
- `--backend` が省略された場合はマシンから backend を検出し、検出できなければ CPU backend を確認します。`--components-dir` が省略された場合は `STRATA_COMPONENTS_DIR`、次にユーザーごとの component folder が使われます。
- いずれの形式も status 確認のためにローカルファイルを読み、必要に応じて GPU/backend 情報を検出します。検出処理は既設ツール等への読み取り専用 probe を行います。ダウンロードやファイル変更は行いません。

## 適用条件と副作用

- このオプションは `strata components engine` の parser に属し、ほかのコマンドの `--output` とは別スコープです。
- `--output json` でも engine が見つからない、または利用できないときは JSON report を出力し、`ok` は `false`、`usable` は `false`、`engine` は `null` になります。人向け表示では状態一覧を標準出力に出し、理由を含む notice を標準エラーに出します。
- 整合性の判定で SHA-256 を計算するため、`--full` は既定の確認よりファイル読み取り量が増えます。出力先ファイルを作る機能ではなく、表示先は標準出力です。

## 出力とエラー

- 正常な状態 report は標準出力へ出ます。engine が usable でない場合は終了コード 5 です。JSON では `ok: false` の report、人向け表示では notice が加わります。
- `engine_component.status()` が `ComponentProblem` を送出した場合、human では `strata: <message>` を標準エラーへ、JSON では `{"schema_version":1,"ok":false,"error":{"code":2,"message":"..."}}` を標準出力へ出し、終了コード 2 を返します。
- option 値の不正は parser のエラーです。その他の `OSError` 等は共通例外処理へ進み、JSON 指定時は JSON error、未指定時は人向けエラーになります。

## 根拠

- `strata_cli/cli.py:132-138` — `components engine` の parser と `--output` の choices/default。`--json` / `--quiet` 共通登録の対象列挙 `strata_cli/cli.py:508-515` に `components_engine` は含まれません。
- `strata_cli/cli.py:2014-2041` — status 呼び出し、JSON/human 出力、非 usable 時の終了コードと notice。
- `strata_cli/cli.py:527-532,2119-2193,2217-2237` — 共通エラー形式、例外経路、parser 実行と `--json` の処理。
- `strata_control/engine_component.py:176-186` — `STRATA_COMPONENTS_DIR` とユーザー既定 folder。
- `strata_control/engine_component.py:402-427,439-453,737-758,859-880,969-988` — status が行う整合性確認、backend 検出、engine 選択と report 作成。
- `strata_control/engine_component.py:202-225` — report に含まれる更新通知がローカルの更新状態を読むこと。

調査は上記 commit の checkout に含まれる Terminal CLI と `strata_control/engine_component.py` に限定しました。別 OS の実機や個別 GPU での probe 結果、および配布済み Release の実行結果は確認していません。
