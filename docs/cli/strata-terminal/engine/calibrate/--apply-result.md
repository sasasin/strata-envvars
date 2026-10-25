# `--apply-result`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine calibrate` |
| オプション | `--apply-result REPORT.json` |
| 別名 | なし |
| 値 | 校正レポートのファイルパスを1つ取る。省略不可（アクション群の必須選択に含まれる） |

## 役割

測定済みレポートの候補設定で短い生成確認を行い、成功した場合にだけ実行設定と setup の校正記録へ反映します。`--exclusive` の指定も必要です。レポートの確認だけなら `--review-result` を先に使います。

## 使い方

```sh
strata engine calibrate --profile four-gpu \
  --apply-result /absolute/path/to/calibration.json --exclusive
```

`--profile` は必須です。保存済みプロファイル名、または明示的な run-config JSON パスを指定できます。レポートパスは現在の作業ディレクトリからの相対パスも指定できます。

## 値と既定値

`REPORT.json` は argparse が文字列として受け取り、`Path` に変換して読み込みます。`--apply-result` 自体に既定値はなく、`--plan`、`--measure`、`--review-result`、`--apply-result`、`--review-rollback`、`--rollback-result` のうちちょうど1つを選ぶ必要があります。レポートパスの空文字列や形式は parser では検査せず、読み込み時にエラーになります。`--out` は `--measure` 専用です。

レポートは通常ファイルでサイズ2 MiB以下である必要があります。JSON、schema version、種別、suite、設定値、本文 SHA-256 が検証されます。設定値は許可された6種類のエンジン引数に限り、有限数値でなければなりません。`--pcie-frac`、`--spec-min-p`、`--adapt-decay` は0〜1、他の設定は1〜8192の整数です。

## 実行時の動作

処理はまず `--exclusive` を確認します。続いて対象プロファイルのロックと managed-runtime の排他 lease を取得し、設定ポート上のサーバーと管理対象の稼働中 Strata runtime がないことを確認します。レポートが現在も適用可能かを再評価し、対象 run-config、engine、校正ツール、hardware key、プロファイル revision、必須モデルファイルのサイズ・更新時刻などをレポートの identity と照合します。レポートは作成後30日を超えた場合、または現在より5分を超えて未来の場合も拒否されます。モデルファイル全体のハッシュ検証ではなくメタデータ照合です。

適用候補の設定で engine を起動し、`Say OK.` の生成を最大16 token 試します。1 token 以上出力できた後、設定やプロファイル identity と setup settings が smoke 中に変化していないことを再確認します。成功すると run-config の候補設定を置換し、setup settings の hardware key に設定・測定 tok/s・日付を保存します。保存先の run-config と同じ場所に `.strata-calibration-backups/` を作り、元の run-config、既存 setup settings（存在する場合）、および rollback 用 application record を保存します。候補設定が元と同じ場合も setup settings と記録は更新されます。

保存済みプロファイルを指定した場合、`engine.calibrate.apply` としてローカル operation journal に処理結果を記録します。明示的な run-config パスではこの journal を使いません。適用後の設定を実行中の server に即時反映する処理はなく、engine の再起動後に使われます。

## 適用条件と副作用

- `--exclusive` は他のプロセスが対象 GPU を使っていないことを保証する仕組みではなく、利用者の確認宣言です。lease は Strata の管理経路で起動した runtime との競合を抑え、設定ポートの server も検出します。直接起動した server、無関係な GPU プロセス、Windows 上の制御は網羅されません。対象デバイスを使う他プロセスを停止・確認してから実行してください。
- smoke test のため engine プロセスを起動し、モデル・tokenizer を読み込みます。利用環境に完全な Strata folder（`setup.py` と `tools/calibrate.py`）がなく、`STRATA_INSTALL_DIR` でも指定されていない場合は処理できません。
- backup/application record がすでに存在する同一レポートは再適用できず、再測定が必要です。POSIX では backup directory と記録ファイルの owner-only 条件も検査されます。
- report の checksum とローカル identity binding は publisher signature ではありません。

## 出力とエラー

成功時は終了コード0です。通常出力では rollback evidence の application record パスを表示し、`--output json` では `application` と（保存済みプロファイルの場合）`operation_id` を含む JSON を stdout に出します。適用中の標準出力は stderr に転送されます。

`--exclusive` 不足や `--out` の誤用は終了コード2、レポート・必要 component・setup settings の読み取り不備などは主に5、鮮度不一致、identity 変更、smoke 失敗、保存失敗などは主に6で失敗します。人向けエラーは `strata: ...` として stderr、JSON モードのエラーは `{schema_version, ok:false, error}` として stdout に出ます。候補 smoke が失敗した場合は設定を変更しません。設定または setup settings の書き込みが失敗した場合は両方を復元しようとし、復元にも失敗した場合は backup からの手動復旧先をエラーに示します。

## 根拠

- parser と相互排他アクション: `strata_cli/cli.py:174-189`
- `--exclusive`、journal 分岐、実行・出力: `strata_cli/cli.py:1048-1056`, `strata_cli/cli.py:1059-1095`
- saved profile と明示 config path の判定: `strata_control/profiles.py:382-388`
- 終了コード・人向け/JSON エラー整形: `strata_cli/cli.py:527-542`, `strata_cli/cli.py:2119-2193`
- 設定 lock、managed lease、server/runtime preflight: `strata_control/calibration.py:205-229`, `strata_control/calibration.py:526-545`
- report 読み込み・形式・checksum 検証、freshness と identity review: `strata_control/calibration.py:339-385`
- 対象 identity とモデルファイル照合の範囲: `strata_control/calibration.py:146-166`
- smoke 生成と engine 起動: `strata_control/calibration.py:388-409`
- settings 候補、backup/application record、適用と復元: `strata_control/calibration.py:425-453`, `strata_control/calibration.py:456-523`, `strata_control/calibration.py:537-626`
- journal への記録と compact result: `strata_control/journal.py:376-424`
- 利用例の補助資料: `docs/TERMINAL_QUICKSTART.md:81-89`
- 排他条件と適用・rollback の注意事項: `docs/TERMINAL.md:122-131`, `docs/TERMINAL.md:160-160`
- CLI 文書の索引: [`docs/cli/README.md`](../../../README.md)

## 調査範囲

同一 revision のソースと repository 内の CLI 利用者向け資料を確認しました。Release 配布物や他 OS/backend での実動作は調査していません。上記の OS 上の lease・GPU 外部プロセス制約はソース内の説明を含みますが、実機での動作確認は行っていません。
