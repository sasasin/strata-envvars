# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components verify` |
| オプション | `--output` |
| 別名 | `--json`（JSON 出力を選ぶ alias） |
| 値 | `human` または `json` |

## 役割

プロファイルが必要とするコンポーネントの検査結果を、人間向けテキストまたは機械処理向け JSON で標準出力に出します。検査対象のプロファイルは必須の `--profile` で指定します。

## 使い方

```sh
strata components verify --profile default --output json
```

`--output` を省略すると `human` になります。短い指定として `--json` も使えます。

## 値と既定値

- `human` と `json` のみ受理します。parser の `choices` にない値は拒否されます。
- 既定値は `human` です。
- オプションは値を一つ取ります。繰り返し指定時の parser 動作は通常の `argparse` で、最後に指定した値が残ります。
- `--json` は `--output json` の alias です。`--quiet` もこの parser に登録されていますが、JSON 出力時は quiet capture を通らず通常の JSON 出力になります。

## 実行時の動作

`human` では各コンポーネントの status・名前・パス等と issue を行単位で表示します。`json` では `schema_version: 1`、全体の `ok`、検査内容を含む `report` を一つの JSON オブジェクトとして出力します。`--output` はシリアライズ形式だけを選び、プロファイル解決やコンポーネント検査の条件は変更しません。

このコマンドは read-only のインベントリ検査として登録されています。`--live` を併用すると、ソースで実装された対象条件では `nvidia-smi` に最大5秒の読み取り専用問い合わせを行い、GPU 情報も report に含めます。この追加問い合わせは `--output` の値には依存しません。

## 適用条件と副作用

- `--profile` は必須です。保存済みプロファイル名、または JSON run-config のパスを渡します。`.json` 拡張子、絶対パス、または `/`・`\\` を含む値はパスとして解決され、それ以外は保存済みプロファイル名として解決されます。
- `--live` なしでは GPU の live probe は行われません。プロファイルを指定していない場合の共通 doctor 実装では検査 report に `PROFILE_NOT_SELECTED` が入り、`live` が有効なら終了結果も失敗になりますが、このサブコマンドは parser 上 `--profile` 必須です。
- 出力先ファイルへの書き込みは行いません。JSON 出力は stdout への表示です。検査対象ファイルの有無・状態確認や、`--live` の外部ツール問い合わせは `--output` の形式選択とは独立です。

## 出力とエラー

- 正常に検査を完了した場合、終了コードは `0`（report の `ok` が true）または `5`（error severity の issue がある）です。JSON 時も report を出力し、結果は `ok` で表されます。
- `--output json` または `--json` の処理中に捕捉されたエラーは、`schema_version: 1`、`ok: false`、数値の `error.code` と `error.message` を含む JSON を stdout に出します。human 時のエラー文は `strata: ...` の形で stderr に出ます。
- 選択肢以外の値や必須 `--profile` の欠落は処理本体に入る前に argparse が拒否します。`--output` の値が不正な場合に JSON エラーになるとは限らず、parser の usage/error 経路になります。

## 根拠

- `strata_cli/cli.py:114-119` — `components verify` parser、必須 profile、`--live`、`--output` の choices と default。
- `strata_cli/cli.py:508-515` — `components_verify` への共通 `--json` / `--quiet` 登録。
- `strata_cli/cli.py:1026-1048` — `_doctor` の human/JSON 出力、report 表示と終了コード。
- `strata_cli/cli.py:2129-2139` — `components verify` を含む `components` の `_doctor` への dispatch。
- `strata_cli/cli.py:527-542` — JSON エラー形式と共通成功出力。
- `strata_cli/cli.py:2223-2247` — argparse による引数検査、`--json` alias の適用、`--quiet` と JSON 出力の分岐。
- `strata_control/profiles.py:382-388` — プロファイル名と JSON path の解決規則。
- `strata_control/doctor.py:80-115,118-143` — `--live` 時の NVIDIA host probe と結果・issue。
- `strata_control/doctor.py:146-235` — report の生成、プロファイル不在時の扱い、コンポーネント検査と `ok` 判定。

調査範囲は上記 commit の checkout 内ソースです。同 revision の CLI `--help` と Release 配布物は照合していません。parser 定義と実処理の確認に基づく記述であり、他 OS/backend 上での live probe 実測は行っていません。
