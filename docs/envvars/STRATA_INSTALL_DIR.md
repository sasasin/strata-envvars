# `STRATA_INSTALL_DIR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata のインストールフォルダー、特に Terminal / Control がモデルの run config を探す場所と、Control モードの setup がユーザー別の成果物を書き込む場所を指定する。エンジンの推論設定や GPU backend を直接変更する変数ではない。

モデル探索では `strata_control.discovery.places()` がこの値を明示指定として扱い、指定フォルダーだけを候補にする。`strata models list` / `inspect` では `--install-dir` が環境変数より優先される。`models.resolve_install()` は `--install-dir` が truthy ならそれを使い、そうでなければ環境変数を読む。明示パスは既存の絶対ディレクトリーでなければ `ProfileError("install directory must be an existing absolute directory", 5)` になる（`terminal/strata_control/models.py:69-79,200-225`、CLI 引数と呼び出しは `terminal/strata_cli/cli.py:168-176,626-635`）。

Control インストールでは、別変数 `STRATA_CONTROL_INSTALL=1` も設定されている場合に限り、値を setup の書き込み先 `home()` にする。ここには run config、ログ、`third_party`、engine feed などが置かれる。モデルのデータ置き場は別の `--data-dir` / 保存済み設定で決まり、モデル固有ファイルには `--models-dir` や `--gguf-dir` も使われるため、この変数だけで全データの保存先が一律に決まるわけではない（`terminal/setup.py:97-108,2115-2120,7419-7447,10062-10066`）。

## 値と判定

パス文字列として読み、数値・真偽値への変換や文字列の大文字小文字判定はない。パスの存在・絶対性チェック、空文字の扱いは呼び出し経路ごとに異なる。

| 経路 | unset | 設定時に使われる値 | 空文字・無効値 |
|---|---|---|---|
| `discovery.places()` | `--install-dir`、実行中の checkout / Control install、記憶済み install、app install などを順に調べる | `Path(raw).expanduser()` を唯一の探索場所にする。明示 `--install-dir` があれば環境変数より優先 | 空文字も `raw is not None` により設定扱いとなり、`Path("")`（現作業ディレクトリー）だけを候補にする。相対・不存在でも拒否せず、config が無ければ空の場所になる（`terminal/strata_control/discovery.py:174-209`） |
| `models.resolve_install()` | `discovery.find_install(here=ROOT)` の結果 | `--install-dir` が truthy ならそれ、次に環境変数。`expanduser()` 後 `resolve()` したパスを返す | 空の CLI override は環境変数へ進む。一方、環境変数が空なら `raw == ""` で `raw is not None` を通り、既存絶対ディレクトリー検査でエラー。相対パス・存在しないパス・ファイルもエラー（`terminal/strata_control/models.py:69-79`） |
| `catalog.install_root()` / CLI `strata install` | 発見した install または `ROOT` | truthy な環境変数をそのまま `Path` にする。`strata install` はその下の `setup.py` を選ぶ | 空文字は unset と同じ。相対・不存在の値もここでは事前検証しない。setup.py が無ければ CLI は終了コード 5 の案内を出す（`terminal/strata_cli/launch/catalog.py:237-246`; `terminal/strata_cli/cli.py:2139-2157`） |
| `terminal/setup.py` | `ROOT` が書き込み先 | `STRATA_CONTROL_INSTALL` が文字列 `"1"` で、かつ値が truthy なら `Path(value).resolve()` | 空文字は `_CONTROL_HOME=None` となり `ROOT` に戻る。Control install が `"1"` 以外ならこの変数は `home()` を変えない。数値形式などの検査はなく相対パスも resolve される（`terminal/setup.py:97-108`） |
| 補助処理（キャリブレーション、GGUF 探索、アクセス修復） | それぞれ import 済み checkout / 他の install 候補 / 他のユーザーデータ root | 多くは truthy な値だけパス候補・修復 root に加える | 空文字は未設定相当。個別の条件は「実行時の詳細」を参照 |

空白だけの文字列も trim されないため空文字とは異なる非空パスとして扱われる経路がある。`~` 展開は `discovery`、`models`、キャリブレーション、GGUF helper では行うが、`catalog.install_root()` は `Path(env)` のままである。OS/backend/build macro による値の parse 差は見つからなかった。

## 有効になる条件

- モデル一覧・詳細表示で環境変数が探索先を絞るのは、`--install-dir` が指定されていない場合。CLI override を使う場合、`models.resolve_install()` 側で値が有効な既存絶対ディレクトリーか検査される（`terminal/strata_cli/cli.py:168-176,626-635`; `terminal/strata_control/models.py:69-79`）。
- `discovery.places()` は非空／空を問わず環境値が存在すれば他の install 候補探索を打ち切る。空フォルダー、相対パス、不存在フォルダーに config がなければモデル候補は見つからない（`terminal/strata_control/discovery.py:174-209`）。
- setup の書き込み先変更には `STRATA_CONTROL_INSTALL=1` が必要。通常の source checkout の setup では `home()` は `ROOT` のまま（`terminal/setup.py:97-108`）。
- `strata install` は選んだフォルダー直下に `setup.py` がある場合だけ子プロセスを起動する。Terminal bundle の場合は `STRATA_CONTROL_INSTALL=1` とし、環境変数が未設定なら `install_root()` の結果を `STRATA_INSTALL_DIR` として子へ追加する。既に環境変数があれば `setdefault` により保持する（`terminal/strata_cli/cli.py:2139-2157`）。
- Terminal launch runner が Control の setup / `--prepare-pack` を起動する経路では、親の値を継承せず `cat.root` を `STRATA_INSTALL_DIR` に設定して子に渡す（`terminal/strata_cli/launch/runner.py:1719-1730,1868-1876`）。Desktop の installer environment も `installDir` が truthy な場合にその値で設定する（`app/host/server/control-runtime.mjs:114-120`）。
- `strata_control.calibration` は `setup` / `tools.calibrate` を import できない Terminal archive で値を使い、指定先に `setup.py` と `tools/calibrate.py` の両方がある場合だけ import 候補にする。満たさないと `ProfileError` となり、「engine calibrate needs a full Strata folder ...」のエラーを返す（`terminal/strata_control/calibration.py:41-64,67-79`）。
- GGUF 準備ツールは値を install root 候補に加え、その下の `third_party/strata-gguf-py` と converter を探す。ただし先行候補や vendored copy に該当ファイルがあればそちらが使われる（`terminal/tools/_paths.py:29-43,46-54,81-86`）。
- Windows のアクセス権修復では、truthy な値をユーザー所有 root および既知の Strata root に追加する。`repair_known_roots()` 自体は Windows 以外では何もしない。通常コマンドの PermissionError 再試行や明示修復から呼ばれる（`terminal/strata_control/private_files.py:418-442,509-555`; `terminal/strata_cli/cli.py:2160-2189`）。
- Desktop native control は、truthy な値があれば `resolve()` した場所を既定 install に用い、なければ components folder の隣の `install` を使う。既存の `preferences.installDir` が存在すればそれが先に使われる。環境値が不正でディレクトリーを作成できない場合のエラーは `installRoot()` 呼び出し元へ伝わる（`app/host/server/native-control.mjs:146,181-190`）。
- Desktop updater は値のパスを install 先にするのではなく、空でない環境変数名を `customProfileEnv` 情報に含める（`app/desktop/src-tauri/src/updater.rs:28-36,73-79,181-197`）。

## 実行時の詳細

`discovery.places()`、`models.resolve_install()`、`catalog.install_root()`、キャリブレーション、GGUF helper は関数呼び出し時に `os.environ` を参照する。値はこれらの関数内で static cache されない。対して `terminal/setup.py` の `_CONTROL_HOME` はモジュール import 時に一度評価され、その後 `home()` が同値を返す。プロセス内で環境値を変更しても、import 済み setup の `_CONTROL_HOME` は更新されない（`terminal/setup.py:102-108`）。

Setup の Control mode で値が有効なとき、`home()` は resolve 済み install root を返し、その root が config やログ、engine feed 等の基準になる。データフォルダーは保存済み `data_dir` があればそれを優先し、なければ `home()` の隣の `Strata-data` を既定とする。指定 data dir の作成に失敗すれば警告後 `home()` に fallback する（`terminal/setup.py:7419-7447`）。

Desktop native control の `defaultInstall()` は呼び出し時の `process.env` を確認する。`installRoot()` は先に既存の `preferences.installDir` を採用し、該当しなければ `defaultInstall()` を作成して実パスを得る（`app/host/server/native-control.mjs:146,181-185`）。

## ログと測定値

測定値は該当しない。変数単独で常時出る有効化ログは見つからなかった。観測可能な失敗として、`strata install` 先に `setup.py` がない場合は `_error(...)` から終了コード 5 の案内、`models.resolve_install()` の不正パスは上記の `ProfileError`、キャリブレーション用ファイルが不足する場合は上記の `ProfileError`、GGUF パッケージ候補が尽きた場合は `SystemExit("gguf-py was not found. ...")` となる（`terminal/strata_cli/cli.py:2143-2148`; `terminal/strata_control/models.py:73-78`; `terminal/strata_control/calibration.py:61-64`; `terminal/tools/_paths.py:46-54`）。

## 根拠

- `terminal/strata_control/discovery.py:174-220` — env / explicit path の優先順位、fallback 探索と config 有無。
- `terminal/strata_control/models.py:69-88,200-225` — install path 検証、一覧結果。
- `terminal/strata_cli/launch/catalog.py:223-246`、`terminal/strata_cli/cli.py:2139-2157` — catalog / installer 選択と子プロセス環境。
- `terminal/setup.py:97-108,7419-7447` — Control mode 条件、import-time cache、書き込み先と data dir。
- `terminal/strata_cli/launch/runner.py:1719-1730,1868-1876`、`app/host/server/control-runtime.mjs:114-120` — 子 setup への明示設定。
- `terminal/strata_control/calibration.py:41-79`、`terminal/tools/_paths.py:29-54,81-86` — calibration と GGUF tool 候補。
- `terminal/strata_control/private_files.py:418-442,509-555`、`terminal/strata_cli/cli.py:2160-2189` — Windows 修復 root。
- `app/host/server/native-control.mjs:146,181-190`、`app/desktop/src-tauri/src/updater.rs:28-36,73-79,181-197` — Desktop install root と custom-profile 検出。
