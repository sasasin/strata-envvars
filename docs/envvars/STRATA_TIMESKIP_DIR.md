# `STRATA_TIMESKIP_DIR`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。外部ライブラリの環境変数は対象外。

## 役割

Time-skip の実行記録を保存・参照する state directory を指定します。Strata CLI の `timeskip run/list/status/apply` が使用し、App Host の旧来（`legacy: true`）Time-skip API 経路も同じディレクトリを使います。App Host の既定の新しい fork 型 Time-skip 経路は `store.DATA_DIR/timeskip-fork` を使うため、この変数の対象外です。

## 値と判定

| 入力 | 選ばれる場所 |
|---|---|
| CLI の `--state-dir DIR` が空でない | `DIR`（環境変数より優先） |
| `--state-dir` が未指定または空、環境変数が空でない | 環境変数の値をそのまま `Path` として使用 |
| `--state-dir` が未指定または空、環境変数が未設定または空文字 | OS ごとの既定ディレクトリ |

Python CLI は `if env:` で判定するので、空文字は未設定同様です。値を数値や真偽値に変換せず、空白除去や絶対パス化もしません。相対パスなら CLI の作業ディレクトリ基準になります。値が非空なら、パスの妥当性や書き込み可能性は選択時に検査されず、その場所を記録ストアとして使おうとします。

既定値は POSIX で `$XDG_STATE_HOME/strata/time-skip`（`XDG_STATE_HOME` が空・未設定なら `~/.local/state/strata/time-skip`）、Windows で `%LOCALAPPDATA%\Strata\time-skip`（`LOCALAPPDATA` が空・未設定ならホーム配下の `AppData\Local\Strata\time-skip`）です。Host 側も POSIX では `XDG_STATE_HOME`、Windows では `LOCALAPPDATA` を使います。

## 有効になる条件

- 直接 CLI では `strata timeskip run`, `list`, `status`, `apply` の state store に適用されます。各サブコマンドの `--state-dir` が非空なら環境変数より優先します。
- App Host では旧来経路（`POST /api/timeskip/start` に `legacy: true`）で作成・参照する Time-skip 記録に適用されます。既定の fork 型経路は別ディレクトリです。
- CUDA/HIP/SYCL、GPU、モデル状態には依存しません。

## 実行時の詳細

CLI は `_timeskip()` 実行時にまず `--state-dir`、次に `os.environ.get("STRATA_TIMESKIP_DIR")` を評価し、選んだ root から `TimeSkipStore` を作ります。run の記録はその root の下に run ID のディレクトリを作り、`run.json` へ保存されます。list/status/apply も同じ root を参照します。環境値は CLI コマンド実行ごとに読み直され、プロセス起動後の環境変更も、次に `_timeskip()` が呼ばれれば反映されます。

Host は起動時に `process.env` をコピーして Time-skip サービスへ渡します。未設定なら空文字を設定した状態で渡しますが、Host の `timeSkipDir()` は `env.STRATA_TIMESKIP_DIR || ...` と判定するため、空文字は既定値になります。旧来経路が CLI 子プロセスを起動するとき、Host が解決した root を子の環境へ設定し、既存値や `extraEnv` より優先させます。したがって Host 起動後に親環境を変更しても既存サービスの root は変わりません。Host の新しい fork 型経路は別の保存先を使います。

選択したディレクトリは store 作成時に親ディレクトリごと作成されます。作成・アクセスに失敗するパスでは Python の `OSError` 経路となり、CLI はエラー JSON/メッセージと終了コード 6 を返します。Host の旧来 detached 経路では子プロセスが run record を作れずに終了した場合、そのエラー出力を API エラーとして返します。Host の一覧 API は解決した state directory も `stateDir` として返します。

## 根拠

- `strata_cli/cli.py:350-380` — `timeskip` コマンドと `run/status/list` の `--state-dir`、既定値のヘルプ。
- `strata_cli/cli.py:1483-1494,1496-1515,1533-1537,1566-1580` — CLI の優先順位と全サブコマンドでの root 利用。
- `strata_control/paths.py:13-21` — POSIX/Windows の state base。
- `strata_control/time_skip.py:321-347,695-716` — run ID ごとの保存先、directory 作成、`run.json` の参照。
- `strata_cli/cli.py:2188-2195` — ファイル I/O `OSError` の CLI エラー処理。
- `apps/host/server/platform-paths.mjs:16-33` — Host の OS 別既定パスと空文字を fallback とする判定。
- `apps/host/server/index.mjs:913-918,1175-1185,1205-1219` — Host 起動時の環境スナップショット、一覧 API、legacy 経路と新 fork 経路の分岐。
- `apps/host/server/timeskip.mjs:26-29,300-307,364-375,444-479` — state root の使用、CLI 子プロセスへの root の設定、起動失敗の返却。
