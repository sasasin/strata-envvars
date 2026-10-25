# `--out`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine calibrate` |
| オプション | `--out REPORT.json` |
| 別名 | なし |
| 値 | レポートを書き出すファイルパス。省略時の既定値なし（`--measure` では必須） |

## 役割

`--measure` が実行するエンジンのデコード測定結果を JSON レポートとして保存するパスを指定します。測定だけでは run config は変更されず、レポートを確認した後の適用は別操作です。

## 使い方

```sh
strata engine calibrate --profile my-profile --measure --exclusive --out ./calibration-report.json
```

`my-profile` は使用する保存済みプロファイル名に置き換えます。出力先ディレクトリは事前に存在し、`calibration-report.json` はまだ存在しない必要があります。相対パスは CLI を起動した作業ディレクトリから解決されます。

## 値と既定値

- 値は argparse の文字列引数です。拡張子や JSON ファイル名の形式を parser が検査することはありません。
- 既定値はありません。`--measure` と `--exclusive` と `--out REPORT.json` が揃わない場合は測定を開始せず、終了コード 2 のエラーになります。
- `--out` は `--measure` 以外の action（`--plan`、`--review-result`、`--apply-result`、`--review-rollback`、`--rollback-result`）と併用できません。action 自体は相互排他で必須です。
- `Path(a.out)` が測定関数へ渡されます。CLI 自身は `~` をホームディレクトリに展開しません。シェルが展開する書き方にするか、必要なら絶対パスを指定してください。

## 実行時の動作

測定開始前に、出力先が既存ファイルまたはシンボリックリンクなら拒否し、親ディレクトリが存在するか確認します。測定後は設定・エンジン・ハードウェア等の識別情報、選ばれた設定、測定値を含むレポートを JSON 化し、SHA-256 を付けて保存します。ファイルは排他的な新規作成（`O_EXCL`）で作成され、POSIX では mode `0600` が要求されるため、既存ファイルを上書きしません。書き込みに失敗した場合、作成途中のレポートを削除します。

この処理は `tools/calibrate.py` のデコード sweep を実行し、候補によってエンジンを再起動して測定します。`--exclusive` は利用者が測定中の排他アクセスを確認したことを示す必須指定です。実装はプロファイルのポートで稼働中のサーバーがないこと、管理対象 runtime が停止していることも確認します。測定はエンジン実行や GPU 使用を伴い得ますが、run config の適用・更新は行いません。

`--output human|json` はレポートの保存先とは別に標準出力の形式を選びます（既定 `human`）。成功時は human 形式でレビューを促すメッセージ、json 形式では保存先とレポートを含む JSON を出力します。one-shot コマンド共通の `--json` は `--output json` の alias です。

## 適用条件と副作用

- `--profile` は必須です。Terminal CLI の軽量配布物に `setup.py` と `tools/calibrate.py` が含まれない場合、フル Strata フォルダーを import 可能にするか、両ファイルを含む `STRATA_INSTALL_DIR` を指定する必要があります。見つからない場合は終了コード 5 で拒否されます。
- 必要な engine/model component が揃っていない場合、出力先の事前確認後に測定を始めず失敗します。出力先の親ディレクトリがない場合も、測定前に終了コード 5 で拒否されます。
- 指定先がすでにある場合（シンボリックリンクを含む）は終了コード 2 です。レポートの最大サイズは 2 MiB で、超過時は終了コード 6 です。
- 測定成功時はレポートファイルが新規作成されます。キャンセル、runner の失敗、識別情報の変化、無効な測定結果などでは report を保存しない経路があります。`--out` は保存先を選ぶだけで、適用や既存 config の書き換えを有効にはしません。

## 出力とエラー

通常のエラーは `stderr` に `strata: ...` と出力され、終了コードが返ります。`--output json`（または `--json`）では `stdout` に `{"schema_version":1,"ok":false,"error":...}` 形式を出力します。CLI の ValueError 系捕捉では `ProfileError.exit_code` が使われ、未指定時のコードは 2 です。代表的な拒否条件は `--out` と `--measure` の不整合（2）、既存パス（2）、出力ディレクトリ不在（5）、測定失敗または report の不正（6）、キャンセル（130）です。

## 根拠

- parser、必須 action 群、`--out` の metavar と help: `strata_cli/cli.py:174-189`。
- one-shot `--json` alias: `strata_cli/cli.py:508-515`。
- action 条件、レポート保存呼び出し、成功表示: `strata_cli/cli.py:1048-1075`。
- 既存パス・親ディレクトリの検査、測定実行、config 不変の明記、report 生成: `strata_control/calibration.py:270-336`。
- 出力先の新規排他的作成、権限、失敗時の削除、2 MiB 上限: `strata_control/calibration.py:232-253`。
- フル Strata フォルダーの要件と `STRATA_INSTALL_DIR`: `strata_control/calibration.py:41-79`。
- 排他確認、稼働中サーバー・管理 runtime の拒否: `strata_control/calibration.py:192-229`。
- CLI の終了コード・エラー出力形式: `strata_cli/cli.py:527-542`, `strata_cli/cli.py:2119-2183`。
- sweep 内の複数候補測定・エンジン再起動: `tools/calibrate.py:27-32`, `tools/calibrate.py:365-455`。

調査対象 checkout は commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、作業状態は `main...origin/main`（未コミット変更なし）でした。CLI の実行や測定は行わず、parser とソースコードを確認しました。
