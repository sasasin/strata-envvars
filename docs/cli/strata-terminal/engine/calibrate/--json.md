# `--json`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine calibrate` |
| オプション | `--json` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は通常表示。 |

## 役割

校正の plan、測定、結果の review/apply、rollback の結果を機械処理しやすい JSON 形式で標準出力に出します。校正コマンドの `--output json` の別表記です。`--json` 自体は校正や設定変更を開始せず、表示形式を切り替えます。

## 使い方

```sh
strata engine calibrate --profile local --plan --json
```

`--profile` と、必須の操作選択肢（`--plan`、`--measure`、`--review-result`、`--apply-result`、`--review-rollback`、`--rollback-result` のいずれか）を指定します。たとえば測定を実行する場合は別途 `--measure --exclusive --out REPORT.json` が必要です。

## 値と既定値

- `--json` は `store_true` で、既定値は偽です。calibrate parser 群へ共通 one-shot オプションとして追加されます（`strata_cli/cli.py:508-515`）。
- 校正コマンドの `--output` は `human` / `json` の選択式で、既定値は `human` です。`main()` は `--json` が指定されると `a.output` を `json` に設定します（`strata_cli/cli.py:187-189, 2232-2236`）。したがって同時指定時も `--json` が `--output human` を上書きします。
- `--json` は校正の操作選択肢ではありません。`--profile` と相互排他グループ内の操作指定は別途必須で、操作を複数指定した場合も parser が拒否します（`strata_cli/cli.py:176-189`）。

## 実行時の動作

処理は `strata engine` の `_calibration()` に入り、`a.output == "json"` を機械出力モードとして扱います（`strata_cli/cli.py:2119-2144, 1059-1064`）。JSON は操作に応じて次の形で標準出力に出ます。

- `--plan`: `schema_version`, `ok`, `plan` を含む JSON（`strata_cli/cli.py:1114-1126`）。この plan は校正対象や component preflight を確認し、エンジン起動・設定書き込みはしません（`strata_control/calibration.py:95-111`）。
- `--measure`: `schema_version`, `ok`, 測定 `report`、出力 `path` を含む JSON。保存 profile の場合は `operation_id` も付きます（`strata_cli/cli.py:1065-1075`）。測定中の進捗メッセージは stderr に送られます（同 `1068-1072`）。
- `--review-result` / `--review-rollback`: `schema_version`, `ok`, それぞれ `review` / `rollback_review` を含む JSON。適用可能かどうかを `ok` と終了コードで示します（`strata_cli/cli.py:1076-1085, 1096-1103`）。
- `--apply-result` / `--rollback-result`: `schema_version`, `ok` と、それぞれ `application` / `rollback` の結果を含む JSON。保存 profile の場合は `operation_id` も付きます（`strata_cli/cli.py:1086-1095, 1104-1113`）。

成功・エラー JSON はいずれも1行で、成功は `{"schema_version":1,"ok":true,...}`、共通エラーは `{"schema_version":1,"ok":false,"error":{"code":...,"message":...}}` です（`strata_cli/cli.py:527-542`）。review が不適用なら `ok:false` と終了コード `6` になります。JSON は UTF-8 文字をそのまま出し、NaN/Infinity を許さない設定です（同 `537`、および review/plan の個別出力 `1081, 1099, 1117`）。

## 適用条件と副作用

`--json` が有効なのはこの one-shot コマンドでは通常表示が JSON になることだけです。各アクション固有の副作用・条件は引き続き適用されます。たとえば測定には `--exclusive` と `--out` が必須で、既存の出力パスは拒否され、既存ファイルを上書きしません（`strata_cli/cli.py:1065-1075`; `strata_control/calibration.py:289-296, 333`）。適用・rollback にも `--exclusive` が必要です（`strata_cli/cli.py:1086-1092, 1104-1110`）。

測定・適用・rollback は、対象 profile のポートで server が稼働中、または管理 runtime が活動中なら拒否されます（`strata_control/calibration.py:192-229`）。測定は全 Strata フォルダーの `setup.py` と `tools/calibrate.py` を必要とし、Terminal archive 単体にはそれらがない場合 `STRATA_INSTALL_DIR` でそのフォルダーを示す必要があります（同 `41-64`）。`--json` はこれらの条件を緩和しません。

## 出力とエラー

- 無効な値、未知の引数、必須の `--profile` / 操作指定の不足、相互排他違反は `argparse` により usage とエラーになります。`--json` に値を続けて指定する形式はありません（parser 定義: `strata_cli/cli.py:176-189, 508-515`）。
- `--measure` に `--exclusive` または `--out` がない場合、`--out` を測定以外で使った場合、または `--exclusive` を plan/review で使った場合はコード `2` のエラーです（`strata_cli/cli.py:1062-1068`）。`--apply-result` / `--rollback-result` に `--exclusive` がない場合もコード `2` です（同 `1086-1088, 1104-1106`）。
- 既存の測定レポート出力先はコード `2`、出力先ディレクトリ不足や必要 component 不足はコード `5`、稼働中 server/runtime や測定・review の鮮度不一致などはコード `6` で失敗し得ます（`strata_control/calibration.py:151-152, 205-229, 289-296, 308-315, 363-385`）。これらの通常の CLI 例外は JSON モードで共通エラーオブジェクトになります（`strata_cli/cli.py:2166-2188`）。
- 調査では同 revision の `--help` を実行していません。値・既定値はソース parser 定義を根拠にしています。Release artifact ごとの収録内容・実行可否はこの調査では検証していません。

## 根拠

- parser と操作のスコープ: `strata_cli/cli.py:174-189, 508-515`
- `--json` から `output=json` への変換: `strata_cli/cli.py:2217-2236`
- JSON 出力と操作別の分岐: `strata_cli/cli.py:527-542, 1059-1126`
- 測定の出力先検査・レポート生成: `strata_control/calibration.py:270-336`
- 排他条件と runtime lease: `strata_control/calibration.py:192-229`
- Terminal archive と full folder の条件: `strata_control/calibration.py:41-79`
