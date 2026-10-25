# `strata profile validate`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象リポジトリの状態は `main...origin/main` で、未コミット変更はありません。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata profile validate` |
| 位置引数 | `name` — 保存済みプロフィール名 |
| 出力オプション | `--output human\|json`（既定値: `human`）、`--json`（`--output json` の alias）、`--quiet` |

## 役割

保存済みプロフィールを読み込み、プロフィールの形式、参照先 run config、およびそのプロフィールから組み立てる有効な起動計画を検証します。成功時に推論エンジンやサーバーは起動しません。プロフィールや run config の設定値もこのコマンドからは保存しません。

## 使い方

```sh
# プロフィールを検証し、人向けの結果を表示
strata profile validate office

# JSON で検証結果と起動計画を取得
strata profile validate office --json
```

プロフィール名は小文字英字で始まり、小文字英字・数字・`_`・`-` を使う1〜64文字です。たとえば `office` は有効な名前です。

## 実行時の動作

コマンドはまず保存プロフィールを読み込み、ファイルの schema version、ID とファイル名の一致、絶対パス形式の `source_config`、override の型と値を検査します。続いて参照先 run config を JSON として読み、`args` が文字列配列であること、`exe` と `tokenizer` が空でない文字列であることを確認します。さらに設定・プロフィールの優先順位と相互制約を適用し、engine 引数を組み立てた plan を結果に含めます。

有効値はコマンドライン指定、保存プロフィール、run config、`STRATA_BATCH_TELEMETRY` 環境変数、既定値の順に選ばれます。ただし validate 自身は起動時の CLI override を受け取りません。主な検査は、値の範囲、`queue_timeout` 使用時に `max_queue` があること、プロフィールの `parallel` / `batch_groups` と run config の対応 engine 引数の競合、`offline` と `mcp_servers` / `before_load` の共存禁止です。

`--output human` では成功時に `Profile <name> is valid at revision <revision>` を表示します。`--output json` または `--json` では `ok: true`、プロフィール、revision、起動 plan を1つの JSON オブジェクトとして標準出力に出します。JSON の plan には source config、effective values とその由来、server/engine 引数などが含まれ、engine 引数中の key/token/secret/password/credential を含む option の値は伏せられます。

## 適用条件と副作用

- 保存プロフィール名を引数に取ります。JSON パスやパスらしい文字列を渡しても、このサブコマンドは明示的 run config として解決しません。`profiles.resolve` のパス解決は他のコマンド向けの挙動で、validate は `profiles.load(name)` を呼びます。
- 検証計画を作る際、`serve.server.engine_args` が drafter の選択を含む引数を計算します。この処理は GPU architecture 情報を取得できる場合に参照し、optional learned expert profile のヘッダーを読む場合があります。推論エンジンを実行する処理ではありません。
- 通常、validate はプロフィールや run config を書き換えません。ただしプロフィール読み込みでアクセス拒否が起きると `read_bytes_repairing` が Strata 管理下のアクセス権を修復して再読込する場合があります。また Windows では CLI 起動時に、プロセスが作成するファイル向けのユーザー既定 owner/ACL を設定しようとします。

## 出力とエラー

不正な引数は argparse が usage とエラーを標準エラーに出し、終了コード 2 になります。プロフィール名不正や schema / override の検査エラーなど通常の `ProfileError` は標準エラーに `strata: <message>` を出し、既定コード 2 で終了します。プロフィールがない場合や profile / run config ファイルの読み込みに失敗した場合はコード 5 です。OS ファイル操作エラーが `OSError` のまま伝わる経路ではコード 6 になります。JSON 出力ではエラーを `ok: false` と `error.code` / `error.message` を含む JSON として出します。

`--quiet` は one-shot コマンドの人向け標準出力を抑制し、失敗時には捕捉した人向け出力を標準エラーへ回します。JSON 出力時は quiet capture を行いません。

## 根拠

- Strata `strata_cli/cli.py:81-83` — `validate` の parser、必須位置引数と `--output` の既定値。
- Strata `strata_cli/cli.py:508-515,2217-2223,2232-2247` — `--json` / `--quiet` の追加、Windows 起動時処理、quiet と JSON 出力の扱い。
- Strata `strata_cli/cli.py:958-968,1015-1020` — プロフィール読込、validate 時の計画生成、成功メッセージ。
- Strata `strata_cli/cli.py:535-547,782-826` — 成功/失敗出力、run config 解決、計画作成と引数の秘匿。
- Strata `strata_cli/cli.py:740-779` — 有効値の優先順位、値検証、override の相互制約。
- Strata `strata_cli/cli.py:2119-2128,2166-2183` — profile dispatcher と `ValueError` / `OSError` の終了コード・出力処理。
- Strata `strata_control/profiles.py:25-55,120-147,150-166,382-388` — 名前・プロフィール・run config の検査、読み込みと参照解決。
- Strata `strata_control/private_files.py:349-355,476-484` — Windows の既定 owner/ACL と、アクセス拒否時の読み込み修復。
- Strata `serve/server.py:3061-3074,3077-3129` — engine 引数構築と GPU architecture 情報参照。
- Strata `serve/server.py:3197-3217` — optional learned expert profile のヘッダー参照。

関連するコマンドとオプションの索引は [`docs/cli/README.md`](../../../README.md) を参照してください。調査方法は [`001_investigation.md`](../../../001_investigation.md) に記載されています。
