# `APPDATA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。調査対象 checkout は `main` で `## main...origin/main`、作業ツリーに未コミット変更はなかった。

## 役割

Windows でコマンドライン Strata が使うユーザー設定ディレクトリの基点を選ぶ。`Strata/settings.json`（setup の `data_dir` と過去 install 情報）、`Strata/profiles`（プロファイルとそこから派生する設定）、`Strata/connections` の場所に使う。デスクトップ app は `STRATA_SETTINGS_FILE` があれば自身の設定ファイルを優先し、ホスト側の共有処理は `STRATA_TERMINAL_SETTINGS_FILE` を別途優先する。Linux/macOS ではこれらの APPDATA 分岐は使わず、設定ごとの XDG または home 配下へ進む。設定パスの中心は `terminal/setup.py` と `terminal/strata_control/discovery.py`、接続・プロファイルは `terminal/strata_cli/connections.py` と `terminal/strata_control/profiles.py`、app 側の共有は `app/host/server/model-folder.mjs` である。

また、app の agent 子プロセス用環境を作る `agentEnvironment` は APPDATA を許可名に含め、元の環境に存在する値をそのまま転送する。ここで APPDATA の値を解釈・変更はしない（`app/host/server/agent/harness-runtime.mjs:20-36`）。

## 値と判定

APPDATA の値自体は文字列としてパスに使い、数値・真偽値への変換や形式検証はしない。Windows の設定ファイル・接続・プロファイルでは、未設定と空文字のどちらも home の `AppData/Roaming` に fallback する。空白だけの値や相対パスは「空」ではないためそのまま基点となる。Node ホストも `env.APPDATA || ...` で同じ falsey 判定をする。Strata はそのパスを `Strata` 以下へ結合する。

| 利用箇所・条件 | 未設定 | 有効になる値（例） | 無効・fallback 例 |
|---|---|---|---|
| Windows の setup / Terminal 設定 | `Path.home()/AppData/Roaming` | `C:\Users\u\AppData\Roaming` → `.../Strata/settings.json` | 空文字 → home fallback。`0` や `false` という文字列も通常のパス値 |
| Windows のプロファイル | `Path.home()/AppData/Roaming` | 同上 → `.../Strata/profiles` | 空文字 → home fallback |
| Windows の接続 | `Path.home()/AppData/Roaming` | 同上 → `.../Strata/connections` | 空文字 → home fallback |
| Windows の app host による Terminal 設定共有 | `homedir()/AppData/Roaming` | `env.APPDATA` → `.../Strata/settings.json` | 空文字 → home fallback |
| Windows 以外 | APPDATA は参照しない | 該当なし | APPDATA に何を設定してもこの分岐には影響しない |

環境別の優先順位は次のとおり。

- `setup.py` と `discovery.own_settings_file`: 非空 `STRATA_SETTINGS_FILE` → Windows なら非空 APPDATA、そうでなければ home の Roaming。非 Windows なら非空 `XDG_CONFIG_HOME` → `~/.config`。`STRATA_SETTINGS_FILE` と APPDATA/XDG の判定には Python の `or` を使う（`terminal/setup.py:7276-7289`, `terminal/strata_control/discovery.py:126-134`）。
- `app/host/server/model-folder.mjs`: 非空 `STRATA_TERMINAL_SETTINGS_FILE` → Windows なら非空 APPDATA、そうでなければ `XDG_CONFIG_HOME` → home の `.config`。この関数が返すのはコマンドライン Terminal の設定ファイルである（`app/host/server/model-folder.mjs:67-72`）。
- プロファイル: 非空 `STRATA_PROFILE_DIR` が最優先。Windows では次に APPDATA、空または未設定時に home の Roaming。非 Windows は `XDG_CONFIG_HOME`（`terminal/strata_control/profiles.py:38-45`）。
- 接続: 非空 `STRATA_CONNECTION_DIR` が最優先で、絶対パスでなければ `STRATA_CONNECTION_DIR must be absolute` の `ConnectionError`。その設定がない Windows では APPDATA、それ以外は home の Roaming。非 Windows は `XDG_CONFIG_HOME`（`terminal/strata_cli/connections.py:72-90`）。

## 有効になる条件

- `os.name == "nt"` または Node の `platform === 'win32'` の分岐でのみ、APPDATA が設定・接続・プロファイルの場所に使われる。setup も `WIN` が真のときだけ APPDATA を参照する（`terminal/setup.py:7283-7289`; `terminal/strata_control/profiles.py:42-45`; `terminal/strata_cli/connections.py:78-82`; `app/host/server/model-folder.mjs:68-72`）。
- settings path では非空の `STRATA_SETTINGS_FILE`（Python）または `STRATA_TERMINAL_SETTINGS_FILE`（Node）があると APPDATA は path 選択に使われない。Windows の desktop-control プロセスは `STRATA_SETTINGS_FILE` を付け、Terminal の古い install 一覧を app 自身の settings と混同しない（`terminal/strata_control/discovery.py:126-134`; `app/host/server/native-control.mjs:187-189,201`; `terminal/strata_control/discovery.py:62-65`）。
- `STRATA_PROFILE_DIR` と `STRATA_CONNECTION_DIR` が非空なら APPDATA を使わない。プロファイル設定は `profiles.profile_dir()` を基点にするため、`run-defaults.json`、`launch-presets`、`presets`、`draft-costs` も同じ親ディレクトリの配置になる（`terminal/strata_control/profiles.py:38-45`; `terminal/strata_cli/launch/runner.py:621-623`; `terminal/strata_cli/launch/store.py:33`; `terminal/strata_control/presets.py:50`; `terminal/serve/server_parts/engines.py:956`）。
- app が packaged mode で実行されるとき、`shareDataFolder()` は APPDATA 等で解決した Terminal settings と app settings の `data_dir` を同期する。APPDATA は Terminal 側ファイルの場所にだけ関わり、どちらの保存値が勝つかは `data_dir_at` の時刻で決まる（`app/host/server/native-control.mjs:187-189`; `app/host/server/model-folder.mjs:57-86`）。
- APPDATA は `private_files.user_roots()` と `known_roots()` にも含まれる。Windows で CLI がアクセス拒否を再試行する際の権限修復や `strata repair-access` はこの既知の APPDATA 配下も対象にし得る（`terminal/strata_control/private_files.py:418-433,509-540`; `terminal/strata_cli/cli.py:2160-2179,2182-2191`）。

## 実行時の詳細

設定先は呼び出しごとに環境を参照して組み立て、APPDATA の値をモジュール内 cache に保存しない。setup は `settings_path()` を設定読み込み・保存時に呼び、設定ファイルを読めない場合は `{}` として扱い、保存時に親ディレクトリを作る。書き込み失敗は `could not save <path> (<error>)` の警告となる（`terminal/setup.py:7283-7306`）。setup が読む `data_dir` は通常のデータフォルダ選択に使われ、`--data-dir` など明示的な setup 引数から選んだ場所を `save_settings` で記録できる。これは APPDATA の保存先を変更する引数ではない（`terminal/setup.py:7513-7527`; `docs/DETAILS.md:1540`）。

Terminal の install discovery は APPDATA 側の settings JSON から過去 install の一覧を読み、他の候補より後の候補として追加する。`STRATA_INSTALL_DIR` や `--install-dir` の明示指定はその探索を一か所に限定する。データフォルダ同期では Terminal settings と app settings が別の `data_dir` を持つ場合、時刻が新しい方を採用して古い側のファイルも更新するが、app 側の保存先がまだ存在しないフォルダを指す場合はそれを採用しない（`terminal/strata_control/discovery.py:180-208,258-276`）。設定探索は app mode (`STRATA_SETTINGS_FILE`) では行わない（同 `:62-65,258-265`）。

接続・プロファイルの保存場所も各操作で helper を通じて決まり、`STRATA_CONNECTION_DIR` は絶対パス制約を検査する。接続フォルダは作成時に private directory として作り、既存ディレクトリの型などを検査する（`terminal/strata_cli/connections.py:72-94`）。プロファイル操作やそこから派生するユーザー設定の場所は `profile_dir()` を呼ぶ（`terminal/strata_control/profiles.py:38-55`; `terminal/strata_cli/launch/runner.py:621-623`）。

Agent 子プロセスについては、ホスト起動時の環境から `externalEnvironment` と allowlist に通った APPDATA をそのまま子環境へ入れる。個別に APPDATA を削除・上書きする処理はこの関数にはない（`app/host/server/agent/harness-runtime.mjs:25-36,80-82`）。

## ログと測定値

setup の settings 保存失敗時は `could not save {settings_path()} ({e})` を `warn` に渡す（`terminal/setup.py:7303-7306`）。APPDATA の値そのものに対する警告・ログは見つからなかった。接続ディレクトリの非絶対 `STRATA_CONNECTION_DIR` は上記例外経路となるが、APPDATA 自体に値検証エラーはない（`terminal/strata_cli/connections.py:72-90`）。測定値の該当はない。

## 根拠

- setup の設定ファイル決定、read/write、失敗警告: `terminal/setup.py:7276-7306`。
- Terminal discovery の優先順位、既知 install の探索、data-dir 同期: `terminal/strata_control/discovery.py:126-134,180-208,258-276`。
- MCP 同梱ツールの設定ファイル決定と `data_dir` 読み込み: `terminal/tools/strata_mcp.py:780-793`。
- プロファイルと派生パス: `terminal/strata_control/profiles.py:38-55`; `terminal/strata_cli/launch/runner.py:621-623`; `terminal/strata_cli/launch/store.py:33`; `terminal/strata_control/presets.py:50`; `terminal/serve/server_parts/engines.py:956`。
- 接続ディレクトリ: `terminal/strata_cli/connections.py:72-94,149-164,190-205`。
- Windows app host が参照する Terminal settings と同期: `app/host/server/model-folder.mjs:57-86`; `app/host/server/native-control.mjs:187-189`。
- APPDATA の子プロセス転送: `app/host/server/agent/harness-runtime.mjs:20-36,80-82`。
- access repair が対象にするルート: `terminal/strata_control/private_files.py:418-433,509-555`; `terminal/strata_cli/cli.py:2160-2191`。
- 現行説明との照合: `docs/DETAILS.md:1540` は settings の保存場所と `--data-dir` の役割を説明しており、setup/discovery の実装と一致する。
