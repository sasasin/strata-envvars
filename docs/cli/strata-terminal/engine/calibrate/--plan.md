# `strata engine calibrate --plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine calibrate` |
| オプション | `--plan` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は `False`。ただし、同じ必須の排他グループから別の操作を一つ指定する必要がある |

## 役割

校正の事前確認を行い、対象モデルの実行設定、必要コンポーネントの状態、校正可能な設定項目などを表示します。エンジンを起動せず、校正計測や実行設定の変更もしません。

## 使い方

保存済み profile 名、または run config JSON のパスを `--profile` に指定します。

```sh
strata engine calibrate --profile my-model --plan
strata engine calibrate --profile /path/to/run-config.json --plan --json
```

`--profile` は必須です。`--plan` は `--measure`、`--review-result`、`--apply-result`、`--review-rollback`、`--rollback-result` と必須の相互排他グループを構成するため、ちょうど一つの操作を指定します。`--json` はこの one-shot コマンドで `--output json` の別名です。

## 値と既定値

`--plan` 自体は `argparse` の `store_true` で値を受け取りません。既定値は偽であり、通常は前述の別操作を選びます。`--profile` は文字列で、`.json` パス、絶対パス、またはスラッシュを含む値を run config パスとして扱い、それ以外を保存済み profile 名として解決します。

## 実行時の動作

CLI は `--plan` を選ぶと `calibration.preview(profile)` を呼び出します。preview は profile/run config を解決して読み込み、run config の内容が読み取り中に変わっていないことを照合し、`doctor.inspect` で必要コンポーネントを調べます。結果には config のパスと SHA-256、profile revision、モデル名、backend、選択 GPU、`tools/calibrate.py` の利用可否、計測予定時間（15〜30分）、排他的なエンジンアクセスの要否、計測対象設定、コンポーネント事前確認が含まれます。ハードウェア識別は計測前には未確認と明示されます。

人間向け出力は校正計画、run config の場所、目安時間、変更・起動を行わなかったことを表示します。必須コンポーネントがない場合は `strata doctor --profile` を案内します。JSON 出力は `schema_version`、`ok`、`plan` を含みます。`ok` は必須コンポーネント事前確認の結果です。

## 適用条件と副作用

この操作自体は読み取り専用です。エンジン起動、計測、run config 書き込みは行いません。コンポーネント確認では run config と関連ファイルを読み、パスの存在・種別・サイズ・実行可否などを調べ、GPU driver probe の実行ファイル有無を確認します。この経路では live GPU probe は有効化されていないため、GPU や driver の実動作・互換性は検証しません。

Terminal archive に `setup.py` と `tools/calibrate.py` がなければ、`tool_available` は偽になります。preview はその不足だけでコマンドを拒否しませんが、結果から完全な計測準備ができているとは判断できません。`STRATA_INSTALL_DIR` は、これらのファイルを含むフル Strata フォルダーがある場合に校正ツール探索へ使われます。

共通 CLI 起動処理は Windows ではファイル生成時の所有者・ACL を現在のユーザーにする token 既定値を設定しようとします（他 OS では何もしません）。これは `--plan` の校正 preview とは別の起動時処理です。

## 出力とエラー

- 必須コンポーネント確認が成功すれば終了コード `0`、失敗すれば `5` です。JSON では失敗時も計画を出力し、`ok: false` とします。
- profile/run config の解決・読み込みや run config の不正、読み込み中の変更などはエラーになります。通常出力では `stderr` に `strata: ...`、JSON 指定時はエラーオブジェクトが出力されます。run config の読み込み失敗は `5`、preview 中に内容が変わった場合は `6` です。
- `--out` を `--plan` と併用すると、計測以外での `--out` 使用として終了コード `2` になります。`--exclusive` も plan では許可されず、同じく終了コード `2` です。
- 操作選択がない、または複数ある場合は `argparse` が拒否し、usage とエラーを表示します。

## 根拠

- 索引上の配置とコマンド階層: `docs/cli/README.md:357-373`（strata-envvars 側）。対象パスの `--plan` リンクと parser 上のオプションは一致します。
- parser、必須排他グループ、`--out` / `--exclusive` の scope、共有 `--json` / `--quiet`: `strata_cli/cli.py:174-189`, `strata_cli/cli.py:508-515`。
- `--plan` の選択から preview、出力、終了コード、および `--out` / `--exclusive` の検査: `strata_cli/cli.py:1059-1064`, `strata_cli/cli.py:1114-1126`。
- `--profile` の path/name 解釈: `strata_control/profiles.py:382-388`。
- preview の読み取り・変更検出と返却情報: `strata_control/calibration.py:90-111`。
- 必須コンポーネント検査、live probe を行わない既定動作と report の `ok`: `strata_control/doctor.py:146-149`, `strata_control/doctor.py:162-179`, `strata_control/doctor.py:218-235`。
- 校正ツールの探索条件と不足時の説明: `strata_control/calibration.py:41-64`, `strata_control/calibration.py:67-79`。
- 共通エラー処理・終了コード・出力先: `strata_cli/cli.py:527-532`, `strata_cli/cli.py:2166-2188`。
- Windows の起動時 token 既定値設定: `strata_cli/cli.py:2217-2222`, `strata_control/private_files.py:349-385`。

調査範囲は上記 commit の parser と Python 実装です。OS ごとの実機状態、外部 GPU driver の互換性、各ホスト上のコンポーネント状態は実行せず確認していません。
