# `strata doctor --output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata doctor` |
| オプション | `--output` |
| 別名 | なし（`--json` は別 parser action の alias） |
| 値 | `human` または `json` |

## 役割

doctor の診断レポートを人間向けの行表示か JSON に切り替えます。出力先ファイルを指定するオプションではありません。省略時は `human` です。

## 使い方

```sh
strata doctor --output json
strata doctor --profile four-gpu --live --output json
```

## 値と既定値

- `human`: 既定値。コンポーネントごとの状態とパス・理由・バージョン、問題の severity/code/message、live GPU probe の状態とカード情報を標準出力に表示します。
- `json`: schema version 1 の単一 JSON オブジェクトを標準出力に出します。形は `{"schema_version":1,"ok":<bool>,"report":<doctor report>}` です。
- それ以外の値は `argparse` の choices 検証で拒否され、通常の usage/error が標準エラーに出て終了コード 2 になります。値の省略時は `human` です。parser は通常の `store` action なので同じ `--output` を複数指定すると最後の値が使われます。

## 実行時の動作

`--output` は `_doctor` が `a.output == "json"` かを判定するために使い、`inspect_components(...)` が作った同じレポートを出力形式だけ変えて表示します。JSON は `ensure_ascii=False`、`allow_nan=False` で標準出力へ1行出力します。human 形式では `report["components"]` と `report["issues"]` を順に表示し、live probe があれば追加で表示します。どちらも出力ファイルを作成しません。

`--json` は doctor を含む one-shot parser 群に後から追加される `store_true` オプションで、指定すると `a.output` を `json` に置き換えます。したがって `--output json` と出力形式は同じです。`--quiet` も同じ parser 群に追加されます。quiet の人間向け doctor 出力は一旦捕捉され、正常終了時には表示されません。診断が終了コード 5 になると捕捉した出力を標準エラーへ出します。JSON 出力は quiet でも抑止されません。

レポートの内容は `--output` によって変わりません。`--profile` があれば保存済み profile 名または run config JSON path を解決して、その構成で必要なコンポーネントを検査します。省略時は profile 固有の検査をせず、CLI と任意 monitor dependency を報告します。`--live` の probe は別の指定で、profile が必要です。既定の doctor は外部ツールを実行せず、`--live` の場合のみ NVIDIA の `nvidia-smi` を呼び出す経路があります。

## 適用条件と副作用

`--output` 自体は表示形式の選択だけで、ファイル書き込み、修復、ダウンロード、engine 起動を行いません。doctor の通常の検査も読み取り専用です。ただし `--live` を併用した場合は、診断側がホスト上の `nvidia-smi` を最大5秒の timeout で一度呼び出します。これは `--output` による副作用ではありません。

## 出力とエラー

- レポートの `ok` が false の場合でも、doctor は通常の human または JSON レポートを出力して終了コード 5 を返します。JSON のトップレベル `ok` は `report["ok"]` と同じ値です。
- JSON mode 中に `_run` が捕捉する `ValueError`、`OSError`、`ClientError`、`KeyboardInterrupt` 等が起きた場合、一般エラー形式 `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}` を標準出力へ出します。profile/run config の読込失敗はこの経路で終了コード 5 になり得ます。
- 無効な `--output` 値や未知引数は doctor の実行前に parser が拒否し、終了コード 2 です。この parser-level エラーは `--output json` による JSON error envelope にはなりません。

## 根拠

- `strata_cli/cli.py:109-113` — doctor parser と `--profile`、`--components`、`--live`、`--output` の定義。`--output` の choices と既定値。
- `strata_cli/cli.py:508-515` — doctor を含む one-shot parser 群へ `--json` と `--quiet` を追加。
- `strata_cli/cli.py:1023-1045` — profile 解決、inspect 呼び出し、JSON/human 出力、診断結果に応じた終了コード。
- `strata_cli/cli.py:527-542` — 共通 JSON error envelope と `_success` の出力先。
- `strata_cli/cli.py:2138-2139` — doctor を `_doctor` へ dispatch。
- `strata_cli/cli.py:2166-2193` — 実行中の例外を出力形式に応じて処理。
- `strata_cli/cli.py:2223-2248` — argparse 実行、`--json` を `output=json` にする処理、quiet 時の stdout 捕捉。
- `strata_control/profiles.py:135-147` — run config の読込と必須キー検証。`strata_control/profiles.py:382-388` — profile 名または JSON path の解決。
- `strata_control/doctor.py:80-115` — live 時の `nvidia-smi` 呼び出し、timeout、出力サイズ・カード情報の検証。
- `strata_control/doctor.py:146-160` — report の基本構造と profile 未指定時の動作。
- `strata_control/doctor.py:162-235` — config に基づく検査、live probe、issues と `ok` の決定。
- `docs/TERMINAL.md:158-172` — doctor の読み取り専用性、live probe の制約、JSON に含まれる任意 monitor の状態に関する利用者向け説明。

調査範囲は上記 commit の checkout に含まれる parser と実装、および同 checkout の Terminal 文書です。各 OS/backend 上の実機での出力差は実行して確認していません。
