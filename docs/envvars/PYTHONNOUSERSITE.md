# `PYTHONNOUSERSITE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

確認した Strata 所有ソースでは、`PYTHONNOUSERSITE` の既存値を読み取って Strata 自身の処理を切り替える箇所はありません。Strata がこの変数を明示的に設定するのは、主に同梱 Python で Control や CLI を起動する経路です。これらの経路では値を文字列 `1` にして子プロセスへ渡します。Python がこの値をどう扱うかという外部ランタイム側の挙動は、本調査の対象外です。

## 値と判定

Strata による真偽値・数値変換、空文字判定、範囲検査はありません。該当する設定コードはいずれも `1` を直接代入します。

| 経路 | `PYTHONNOUSERSITE` の扱い |
|---|---|
| POSIX `bin/strata` で、選択された Python のパスが launcher 隣接の `python/` 以下 | `1` に設定し、`PYTHONHOME` と `PYTHONPATH` を削除してから `strata.py` を起動 |
| Windows `bin/strata.cmd` / `bin/strata.ps1` で同梱 Python を選択 | `1` に設定し、`PYTHONHOME` と `PYTHONPATH` を削除して起動 |
| それらの launcher で `STRATA_PYTHON`、`.venv`、または PATH 上の Python を選択 | この変数は launcher によって設定されず、継承した環境値のまま |
| 新しい Control への hand-over | 継承環境の値を常に `1` で上書き |
| モデル準備用 `setup.py`、host が起動する Control / installer | 継承環境の値を常に `1` で上書き |

したがって、未設定・空文字・`0` などの値を Strata が判定して fallback する規則はありません。明示設定の値が残る経路では、Strata はその値を検査しません。CLI 引数との優先順位もありません。

根拠: POSIX launcher の Python 選択と設定 `bin/strata:31-49,128-133`、Windows launcher `bin/strata.cmd:29-43`, `bin/strata.ps1:25-46,53-56`、hand-over `strata_cli/handover.py:117-123,126-158`、モデル準備 `strata_cli/launch/runner.py:1142-1153`、host の Control 環境 `apps/host/server/control-runtime.mjs:88-103`。

## 有効になる条件

- POSIX `bin/strata` は `$STRATA_PYTHON` が指定されていればそれを優先し、同梱 runtime の候補はその後に探します。変数の設定は、選んだ Python のパスが `$HERE/../python/*` または `$HERE/python/*` に一致する場合だけ行います。PATH 上の Python やその他の場所を使う場合は、この launcher は値を変更しません（`bin/strata:31-49,128-133`）。
- Windows の `bin/strata.cmd` と `bin/strata.ps1` も、明示した `STRATA_PYTHON` や `.venv` / PATH の Python を選ぶ経路では設定せず、バンドル内 `python` を選んだ分岐で設定します（`bin/strata.cmd:29-43`; `bin/strata.ps1:25-46`）。
- hand-over は新しい Control があり、hand-over が無効化されておらず、実行元が source checkout ではない等の既存条件を満たした場合だけ発生します。その子プロセス環境は `_child_env()` が作り、そこで既存値を `1` に上書きします。POSIX では `execve`、Windows では `subprocess.call` に渡します（`strata_cli/handover.py:117-123,126-158`）。
- `strata launch` のモデル準備では、既存環境を元にした子プロセス環境へ `1` を設定し `setup.py` に渡します。これはモデル準備 subprocess の設定であり、通常の engine 実行に対する独立した判定ではありません（`strata_cli/launch/runner.py:1142-1153`）。
- host server の packaged Control 経路では `controlEnvironment()` が入力環境を複製し、Python 関連の一部変数を削除した後、`PYTHONNOUSERSITE: '1'` を加えて subprocess に渡します。`installerEnvironment()` も同じ環境を引き継ぎます。source checkout を使う経路は `process.env` を元に別の変数だけを加えるため、この値を上書きしません（`apps/host/server/control-runtime.mjs:88-111,129`; `apps/host/server/native-control.mjs:55,106`）。

## 実行時の詳細

値の設定時期は各 launcher / 子プロセス環境を組み立てる時点です。Strata は利用者の環境値を確認せず、設定する経路では無条件で `1` を与えます。POSIX launcher では、`serve` / `bench` 用の依存関係 probe を行った後、最終的な `strata.py` の `exec` 前に bundled runtime の場合だけ設定します（`bin/strata:109-130,133`）。hand-over は親プロセスの環境を複製して上書きし、切り替え後の Control に渡します（`strata_cli/handover.py:117-123,148-158`）。

他にも、updater が staged Control の `--version` を確認する subprocess、desktop の Control 自己確認 subprocess、Terminal 配布物の build-time pip / import probe、setup 用 launcher が `1` を渡します（`strata_control/updater.py:1306-1324`; `apps/desktop/src-tauri/src/main.rs:625-660`; `packaging/package_terminal.py:199-213,434-440`; `setup.sh:7-13`; `START-HERE.bat:44-49`）。これらも Strata 側では値を parse しません。

この変数の値による Strata 固有のログ、警告、終了コード、失敗分岐は見つかりませんでした。起動失敗や警告は別の条件に対して実装されています。ソース全体の名前検索では C++ / CUDA / HIP / SYCL の読み取り箇所も見つからず、既存値の読み取りや cache の有無を論じる Strata 実装はありません。

## 根拠

- bundled runtime を選ぶ POSIX CLI launcher と設定箇所: `bin/strata:31-49,128-133`。
- Windows CLI launcher: `bin/strata.cmd:29-43`; `bin/strata.ps1:25-46,53-56`。
- 新しい Control への値の上書きと環境転送: `strata_cli/handover.py:117-123,126-158`。
- モデル準備 subprocess: `strata_cli/launch/runner.py:1142-1153`。
- host Control / installer subprocess 環境と packaged / checkout 分岐: `apps/host/server/control-runtime.mjs:88-111,129`; `apps/host/server/native-control.mjs:55,106`。
- updater の staged Control 確認: `strata_control/updater.py:1306-1324`。
- build-time runtime 作成・probe: `packaging/package_terminal.py:199-213,434-440`。
- セットアップ launcher: `setup.sh:7-13`; `START-HERE.bat:44-49`。
