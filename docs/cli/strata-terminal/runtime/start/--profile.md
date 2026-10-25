# `--profile`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime start` |
| オプション | `--profile` |
| 別名 | なし |
| 値 | 保存済みプロフィール名。小文字 `a-z` で始まり、小文字英字・数字・`_`・`-` を使う最大64文字の名前 |

## 役割

起動する保存済みプロフィールを指定します。このプロフィールの参照元 run config と保存済み serving overrides から起動内容を組み立て、ローカル owner host の管理下でサーバーを起動します。プロフィール名は runtime の識別子にも使われます。

## 使い方

`four-gpu` というプロフィールが保存済みの場合:

```sh
strata runtime start --profile four-gpu
```

起動内容を確認するだけなら `--plan` を付けます。既存の利用例にも、計画表示と実起動が別々に記載されています（`docs/TERMINAL.md:63-69`）。

## 値と既定値

- 値は必須で、省略時に使われる既定値はありません（`strata_cli/cli.py:203-206`）。
- 有効なプロフィール名は `[a-z][a-z0-9_-]{0,63}` に一致する必要があります（`strata_control/profiles.py:25,48-55`）。
- 値は保存済みプロフィール名として解釈されます。`runtime start` は runtime 側で名前を検証し、保存済みプロフィールを読み込みます（`strata_control/management.py:188-211`）。したがって、run config JSON のパスを直接渡す用途ではありません。共通の参照関数は JSON パスも扱いますが、runtime の名前検証が先に適用されます（`strata_control/profiles.py:382-388`）。
- 同じ `--profile` を複数回指定した場合の扱いを Strata 独自に定める処理はありません。parser は `argparse` の通常の値格納 action を使用しています（`strata_cli/cli.py:206`）。

## 実行時の動作

`--profile` で受け取った名前は `_runtime()` から `management.runtime_action()` に渡されます。`start` はプロフィールを読み込み、`_start_candidate()` で起動計画と参照元設定の SHA-256 を計算します。計画ではプロフィールの設定を有効値に展開し、run config とプロフィール overrides の値を含む起動内容を確認します（`strata_cli/cli.py:1331-1356,782-826`; `strata_control/management.py:188-230`; `strata_control/runtime.py:458-462`）。

`--plan` を付けない場合、同じプロフィール名で operation journal を通して runtime を開始します（`strata_control/management.py:220-230`）。owner host は CLI の終了後も稼働し、サーバーを提供し続けます。通常は `strata runtime stop --profile <同じ名前>` で停止します（`strata_control/runtime.py:518-530,559-599`; `strata_cli/cli.py:197-205`）。

プロフィールが持つ serving overrides は run config の値より優先されます。起動時の有効値にはプロフィールの `host`、`port`、`parallel`、`batch_groups`、`max_queue`、`queue_timeout`、`offline`、`batch_telemetry` が反映されます（`strata_cli/cli.py:745-779,794-805`）。各値の検証や run config 引数との衝突も起動候補の組み立て時に行われます。

## 適用条件と副作用

- 指定名のプロフィールが保存されている必要があります。保存場所は `STRATA_PROFILE_DIR`、Windows では `%APPDATA%/Strata/profiles`、それ以外では `$XDG_CONFIG_HOME/strata/profiles`（未設定時は `~/.config/strata/profiles`）です（`strata_control/profiles.py:38-45,150-166`）。
- `--plan` の場合もプロフィールと起動候補を検証しますが、結果は `would_start: false` で、起動処理は行いません（`strata_control/management.py:207-219`）。
- 実起動では、runtime はプロフィール別のログを追記モードで開き、owner host を別プロセスとして起動します。起動前に同プロフィールの孤立した server/engine を確認・終了し、古い状態があれば復旧を試みます（`strata_control/runtime.py:546-582`）。
- `--die-with-pid` が併用された場合は、その PID が実行中か確認し、指定プロセスが終了したときに runtime を止める情報を owner host に渡します。これは `--profile` 自体の既定動作ではありません（`strata_cli/cli.py:207-208`; `strata_control/runtime.py:531-537,568-570`）。

## 出力とエラー

- 通常出力はプロフィール名と状態（成功時は `ready` または `starting` など）を表示します。`--output json` またはその alias `--json` では JSON を出力します（`strata_cli/cli.py:1331-1373,508-515`）。
- `--profile` の省略は parser の必須引数エラーになります。形式不正は「profile name must start...」、未保存名は `strata profile create` を案内するエラーになります。プロフィール読み込み・起動候補の検証に失敗した場合も `ProfileError` が CLI のエラー出力へ変換されます（`strata_cli/cli.py:206,2166-2173`; `strata_control/profiles.py:48-50,150-166`）。
- 起動前の engine 検査失敗はそのエラーを返します。owner host を起動できない場合はログ位置を案内し、待機時間内に ready にならない場合は `startup_wait_expired`（終了コード8）を返します（`strata_control/runtime.py:465-482,546-599`）。

## 根拠

- parser と必須指定: `strata_cli/cli.py:197-212`
- CLI から runtime 操作への引き渡しと出力: `strata_cli/cli.py:1331-1373`
- runtime 操作での名前検証、プロフィール確認、plan と実起動: `strata_control/management.py:188-230`
- プロフィール名の形式、保存データの検証と読み込み、参照解決: `strata_control/profiles.py:25,38-55,120-166,382-388`
- 起動候補のプロフィール解決と起動計画: `strata_cli/cli.py:745-826`; `strata_control/runtime.py:458-462`
- owner host の起動、ログ、待機と失敗: `strata_control/runtime.py:518-599`
- 関連する利用例: `docs/TERMINAL.md:61-70`

調査対象の checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。CLI `--help` は補助実行していません。調査日は上記のとおりです。
