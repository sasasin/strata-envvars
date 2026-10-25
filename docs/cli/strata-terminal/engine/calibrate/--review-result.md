# `--review-result`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine calibrate` |
| オプション | `--review-result REPORT.json` |
| 別名 | なし |
| 値 | calibration report のパス（文字列、位置引数名 `REPORT.json`） |

## 役割

計測済み calibration report を現在の profile と照合し、候補設定がまだ適用可能かを表示します。この action 自体は候補を config に書き込まず、engine の smoke test も行いません。適用には別 action の `--apply-result` が必要です（parser: `strata_cli/cli.py:178-186`、review 処理: `strata_cli/cli.py:1076-1085`、適用処理: `strata_cli/cli.py:1086-1095`）。

## 使い方

```sh
strata engine calibrate --profile my-profile --review-result ./calibration-report.json
```

`--profile` は必須です。`--plan`、`--measure`、`--apply-result`、`--review-rollback`、`--rollback-result` を含む action 群から、ちょうど一つを選ぶ必要があります。`--review-result` はこの相互排他 group の一つです（`strata_cli/cli.py:176-186`）。

## 値と既定値

値は argparse の文字列で受け取り、明示的な `type`、`choices`、path 存在確認は parser では設定されていません。値の省略はできず、パスとして `Path(...)` に渡されます（`strata_cli/cli.py:181`、`strata_cli/cli.py:1077`）。相互排他 group の `required=True` により、この action か別の calibration action が必須です。report の既定値はありません。

report 読込時は通常ファイルであること、サイズが 2 MiB 以下であること、UTF-8 JSON であることを確認します。schema version `1`、kind `strata.engine.calibration`、suite `legacy-decode-v1`、必須 identity/measurement 形式、有限の `created_at`、32 桁小文字 hex の report ID、settings の許可リスト・数値形式・範囲、body SHA-256 が検証されます（`strata_control/calibration.py:33-38`、`strata_control/calibration.py:169-189`、`strata_control/calibration.py:339-360`）。settings の数値範囲は `--pcie-frac`、`--spec-min-p`、`--adapt-decay` が 0..1、その他の許可設定が 1..8192 の整数です。

## 実行時の動作

処理は profile と run config を解決し、report を読み込んで freshness を評価します。report の `source_config` が現在の config パスと異なる、計測時点ですでに `applicable` でない、作成時刻が現在から 30 日を超えて古い、または現在より 5 分超先である場合は理由を記録します。さらに、source config の SHA-256、engine binary と calibration suite の SHA-256、hardware key、model/backend/GPU、profile ID/revision、必須ファイルの metadata を含む identity を比較します。identity を取得できない場合も `identity_unavailable:<終了コード>` を理由にします（`strata_control/calibration.py:146-166`、`strata_control/calibration.py:363-385`）。

返却結果には `applicable`、理由一覧、測定 settings、measurements、現在の `before_args`、report settings を反映した `after_args` が含まれます。before/after の引数列は表示前に、引数名に key/token/secret/password/credential を含む値を伏せます（`strata_control/calibration.py:381-385`、`strata_cli/cli.py:726-742`）。

report の identity 検査には full Strata folder の `tools.calibrate` が必要です。import できず、`STRATA_INSTALL_DIR` に `setup.py` と `tools/calibrate.py` を含む folder も指定されていない場合は処理できず、エラーになります（`strata_control/calibration.py:41-64`）。この処理は計測スイープや engine 起動を呼び出しません。

## 適用条件と副作用

`--review-result` 単独の処理では report と profile/config、component/engine identity を読み取って判定・表示します。calibration report、run config、profile を更新せず、GPU 独占を要求する `--exclusive` も不要です。`--exclusive` は parser 上受理されますが、review と併用すると「`--exclusive` は `--measure`、`--apply-result`、`--rollback-result` のみ」として終了コード 2 になります（`strata_cli/cli.py:187-189`、`strata_cli/cli.py:1062-1064`）。

この action は診断上の候補表示で、成功しても適用可能性を後続処理まで保証するものではありません。実際の適用処理は別 action です。

## 出力とエラー

- 既定の `--output human` では `calibration.review()` の返却 dict を整形 JSON として stdout に出します。`applicable` が真なら終了コード 0、偽なら 6 です（`strata_cli/cli.py:1080-1085`）。
- `--output json` または one-shot parser が追加する alias `--json` では、stdout に `{"schema_version":1,"ok":<applicable>,"review":...}` を出します（`strata_cli/cli.py:189`、`strata_cli/cli.py:508-515`、`strata_cli/cli.py:1080-1082`）。
- 壊れた/不正な report、サイズ超過、report が通常ファイルでない、読込不能、full Strata folder 不在などは `ProfileError` 等になり、共通エラー経路で終了コード 5 または 6 とエラー出力を返します。machine mode では JSON error、human mode では stderr に `strata: ...` を出します（report 検証: `strata_control/calibration.py:339-360`、folder 要件: `strata_control/calibration.py:41-64`、出力: `strata_cli/cli.py:527-542`、例外処理: `strata_cli/cli.py:2166-2183`）。
- action の指定不足/複数指定、値の不足、または review と不適合な `--exclusive` は argparse の usage error または明示的なエラーになり、終了コード 2 です（`strata_cli/cli.py:178-189`、`strata_cli/cli.py:1062-1064`、`strata_cli/cli.py:2223-2231`）。
- `--quiet` は one-shot parser 群に追加されます。human mode で適用不可の結果（終了コード 6）になった場合、quiet 処理が捕捉した結果 JSON を stderr に出します。`--output json` では quiet による stdout 抑止経路に入りません（`strata_cli/cli.py:508-515`、`strata_cli/cli.py:2236-2248`）。

## 根拠

- parser と option scope: `strata_cli/cli.py:174-189`
- `--review-result` の dispatch、出力、終了コード: `strata_cli/cli.py:1059-1085`
- report schema/サイズ/本文ハッシュ検査: `strata_control/calibration.py:339-360`
- freshness と identity の判定、返却項目: `strata_control/calibration.py:146-166`, `strata_control/calibration.py:363-385`
- settings validation: `strata_control/calibration.py:169-189`
- argv の redaction: `strata_cli/cli.py:726-742`
- full Strata folder 要件: `strata_control/calibration.py:41-64`
- 共通エラー出力と終了コード処理: `strata_cli/cli.py:527-542`, `strata_cli/cli.py:2166-2183`

## 調査範囲

Strata checkout の commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5` の parser と実装を確認しました。リポジトリの確認時点では `main...origin/main` で未コミット変更はありませんでした。CLI `--help` や Release archive は別途照合していません。`tools.calibrate` や engine の実測動作、各 platform/backend 上の hardware identity の具体的内容は実行しておらず、この文書では実行時の計測値や性能効果を主張しません。
