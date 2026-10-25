# `--output`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine calibrate` |
| オプション | `--output` |
| 別名 | `--json`（JSON 出力を選ぶフラグ） |
| 値 | `human` または `json` |

## 役割

コマンド結果の出力形式を選びます。`human` は人向け表示、`json` は機械処理向け JSON です。`--json` は値を取らず、`--output json` の別表記です。測定レポートの保存先を指定するものではありません（保存先は `--measure` と組み合わせる `--out REPORT.json` です）。parser は `--output` に `human` / `json` 以外を受け付けず、既定値は `human` です。`strata_cli/cli.py:176-189, 508-515, 2232-2235`。

## 使い方

```sh
strata engine calibrate --profile local --plan --output json
strata engine calibrate --profile local --plan --json
```

`--profile` は必須で、`--plan`、`--measure`、`--review-result`、`--apply-result`、`--review-rollback`、`--rollback-result` のうち一つを選ぶ必要があります。これらは相互排他かつ必須の action 群です。`strata_cli/cli.py:176-189`。

## 値と既定値

- `--output human`: 既定値です。計画は要点をテキストで表示し、測定・適用・ロールバックの成功時には短い完了メッセージを表示します。`strata_cli/cli.py:1073-1075, 1093-1095, 1111-1113, 1114-1126`。
- `--output json` / `--json`: JSON を stdout に出します。`--json` は各 one-shot parser に追加され、`main()` が `a.output = "json"` に変換します。`strata_cli/cli.py:508-515, 2232-2235`。
- 値の大文字小文字、別表記、空値の補正処理はありません。選択肢外の値は argparse の引数エラーとなります。宣言箇所は `strata_cli/cli.py:189`。

## 実行時の動作

この option は表示方法を選び、校正処理自体の値や適用条件を変更しません。選択結果は全 action に共通して `machine = (a.output == "json")` として参照されます。`strata_cli/cli.py:1059-1064`。

- `--plan`: JSON は `schema_version`, `ok`, `plan` を含みます。`human` はモデル名、run config、所要時間の目安、プレビューが engine を起動・設定を変更しないことを表示します。必要 component が不足する場合は追加案内を表示します。`strata_cli/cli.py:1114-1126`。
- `--measure`: JSON は `schema_version`, `ok`, `report`, `path`（saved profile の場合は `operation_id` も）を含みます。`human` はレポートを確認するよう促す完了文を表示します。実測中に出るメッセージは stdout から stderr に振り替えられます。`--out` が実際のレポート出力先です。`strata_cli/cli.py:1065-1075`。
- `--apply-result` / `--rollback-result`: JSON はそれぞれ `application` / `rollback` を含む成功結果です。`human` は適用時に rollback evidence の場所を、復元時にモデル再起動が必要なことを表示します。`strata_cli/cli.py:1086-1113`。
- `--review-result` / `--review-rollback`: JSON 指定では `schema_version`, `ok`, `review` または `rollback_review` を含みます。`human` 指定でも、この2 action は要約文ではなく整形 JSON を stdout に出します。`applicable` が偽なら終了コード 6、真なら 0 です。`strata_cli/cli.py:1076-1085, 1096-1103`。

## 適用条件と副作用

値の許容範囲は `human` / `json` のみで、未指定時は `human` です。コマンドで選んだ action に応じた出力だけを変えます。`--quiet` が指定されると、JSON 出力は通常どおり実行されます。human 出力は quiet capture の対象になり、失敗時に捕捉した出力を stderr に出す場合があります。`strata_cli/cli.py:2236-2247`。

この option 自体はファイルを作成・変更しません。測定時は `--out` の report path に JSON レポートが新規作成され、既存ファイルまたは symlink があるパスは拒否されます。親ディレクトリも事前に存在する必要があります。`strata_control/calibration.py:289-296, 322-336`。

Terminal archive では `setup.py` と `tools/calibrate.py` が同梱されない場合があり、その場合、測定・レビュー等の校正処理には完全な Strata folder が必要です。`STRATA_INSTALL_DIR` が指定される場合はそのフォルダの `setup.py` と `tools/calibrate.py` を探します。この制約は出力形式によって変わりません。`strata_control/calibration.py:41-64, 67-79`。

## 出力とエラー

- JSON モードの成功出力は stdout です。通常の共通成功 helper は `schema_version: 1` と `ok: true` を付加します。review と plan は個別に JSON を構成し、`ok` に適用可能性・component preflight の結果を反映します。`strata_cli/cli.py:535-542, 1081-1085, 1098-1103, 1114-1118`。
- JSON モードの意味的エラーは通常 stdout に `schema_version`, `ok: false`, `error` を含む JSON を出し、human モードでは `strata: ...` を stderr に出します。`strata_cli/cli.py:527-532, 2165-2183`。
- `--measure` には `--exclusive` と `--out` が必要です。`--out` は measure 以外では使えず、`--exclusive` は measure / apply / rollback 以外では使えません。apply / rollback にも `--exclusive` が必要です。これらの違反は終了コード 2 です。`strata_cli/cli.py:1062-1067, 1086-1088, 1104-1106`。
- report path が既存または親ディレクトリがない場合の拒否、engine 測定失敗時の設定未変更扱い、cancel 時の終了コード 130 など、校正処理固有の失敗はこの option の選択では緩和されません。`strata_control/calibration.py:293-315`。
- 値の欠落・不正値や相互排他 action の不足は argparse が拒否します。parser のエラー表示はこの command の handler より前に行われます（`parse_known_args` と未知引数処理）。`strata_cli/cli.py:176-189, 2223-2235`。

## 根拠

- parser と適用 scope、`--json` alias の登録: `strata_cli/cli.py:174-189, 508-515`。
- alias を `output=json` にする処理、quiet 時の扱い: `strata_cli/cli.py:2232-2247`。
- action ごとの出力と終了コード: `strata_cli/cli.py:1048-1126`。
- 成功・失敗の共通出力: `strata_cli/cli.py:527-542, 2165-2188`。
- measure の保存先、既存ファイル拒否、report 書き込み: `strata_control/calibration.py:289-336`。
- Terminal archive で校正 tool を解決する条件: `strata_control/calibration.py:41-79`。
