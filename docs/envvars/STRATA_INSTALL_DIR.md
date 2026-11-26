# `STRATA_INSTALL_DIR`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（`2026-11-26` 時点）。

## 役割

モデルの run config を置くインストールフォルダー、または Control セットアップが書き込み先にするユーザー領域を指定するパスである。Terminal のモデル探索、セットアップ、Desktop の Control 起動、調整ツールの探索で参照される。GPU backend や engine の計算方式は制御しない。

単一の共通パーサーはなく、呼び出しごとに `Path` 化・`resolve()`・絶対パス検査の有無が異なる。したがって、全経路で共通の「有効なパス」判定はない。主な実装は `terminal/strata_control/discovery.py`、`terminal/strata_control/models.py`、`terminal/setup.py`、`terminal/strata_cli/cli.py`、Desktop の `app/host/server/native-control.mjs` にある。

## 値と判定

文字列の内容を数値や真偽値に変換する変数ではない。パス文字列として扱われるが、空文字・相対パス・存在しないパスの扱いは経路別である。

| 経路 | 未設定 | 空文字 | パスの扱い・無効時 |
|---|---|---|---|
| `strata models list` / `inspect` の探索 (`discovery.places`) | Terminal 自身、記憶済みフォルダー、Desktop の順で探索 | `raw is not None` のため明示指定扱い。`Path("")` はカレントディレクトリーとなり、そこだけを探索 | `expanduser()` のみ。存在確認・絶対パス検査はせず、run config がなければ明示場所の結果は空 |
| `models.resolve_install()` | `find_install()` の探索結果 | 空文字も `raw is not None` となり、`.` が相対パスとして拒否される | `expanduser()` 後に既存かつ絶対ディレクトリーでなければ `ProfileError("install directory must be an existing absolute directory", 5)` |
| `strata launch` の catalog (`install_root`) | `find_install()` の探索結果 | `if env` が偽なので `find_install()` へ進む。そこでは空文字を明示場所として扱う | 非空値はそのまま `Path(env)`。この関数では存在・絶対パス検査や `expanduser()` をしない |
| Terminal の `strata install` (`cli._install`) | `ROOT/setup.py` を使う | `or ROOT` により `ROOT/setup.py` を使う | 指定先の `setup.py` がなければ終了コード 5 と説明文を返す |
| Control セットアップ (`setup.py`) | `_CONTROL_HOME` は `None`、書き込み先は `ROOT` | `os.environ.get(...)` が偽となり `ROOT` | `STRATA_CONTROL_INSTALL == "1"` のときだけ非空値を `Path(...).resolve()` して使用。相対値も解決されるが、事前の存在・書込可能性検査はない |
| Desktop (`native-control.mjs`) | components の隣の `install` | JS の truthy 判定が偽となり既定値 | 非空値を `resolve()` する。既存の `preferences.installDir` があればそちらが先に使われる。作成や実利用で失敗した場合の扱いは各処理による |
| Calibration (`calibration.py`) / GGUF helper (`tools/_paths.py`) | import 済みのローカル実装や通常の探索先を使う | `if raw` が偽で、この変数由来の候補を追加しない | 非空値は `expanduser()` して必要ファイルの有無を検査する。Calibration は不足時に拒否し、GGUF helper は候補を飛ばして次を探す |
| Desktop updater のカスタム環境検出 (`updater.rs`) | `customProfileEnv` に含めない | `var_os` の空値判定で含めない | パスとして検証せず、非空なら変数名を status 情報に含める |

Terminal では `--install-dir` が環境変数より優先する経路がある。`models.resolve_install(override)` は非空の `override` を優先し、`discovery.places(explicit=...)` は `explicit is not None` を優先する。CLI の `models list` と `inspect` は `a.install_dir` を `models.list_installed()` / `models.inspect()` に渡す。`--served` では `--install-dir` 自体が「applies only to local installed models」として終了コード 2 で拒否される。出典: `terminal/strata_control/models.py:69-79`、`terminal/strata_control/discovery.py:174-181`、`terminal/strata_cli/cli.py:168-176,602-635`。

## 有効になる条件

- モデル探索では、変数が指定されると通常の複数場所探索に代わりその場所だけが対象になる。`models.resolve_install()` 経由では値が絶対パスかつ既存ディレクトリーであることも必要。`strata models list` が対象に run config を見つけられない場合は `No installed models found. Looked in: ...` と `--install-dir FOLDER` の案内を表示する（`terminal/strata_cli/cli.py:626-634`）。
- Terminal のセットアップ引き渡し先を変えるには、値の指す場所に `setup.py` が必要。Terminal bundle ではさらに `ROOT/python` と `ROOT/VERSION` がある場合に Control install モードとなり、子プロセスへ `STRATA_CONTROL_INSTALL=1` と install directory を渡す（`terminal/strata_cli/cli.py:2139-2161`）。
- `setup.py` で per-user home を使うには `STRATA_CONTROL_INSTALL` が文字列全体で `"1"` で、かつ `STRATA_INSTALL_DIR` が非空であることが必要。前者が未設定・空・`"true"` などの場合、または後者が空の場合は `_CONTROL_HOME` が設定されず `ROOT` が home になる（`terminal/setup.py:97-108`）。
- Calibration の追加探索は、通常の Python import で `setup` / `tools.calibrate` が見つからない場合に限られる。環境変数の場所に両方のファイルがなければ追加候補にせず、利用箇所では `ProfileError` で full Strata folder を要求する（`terminal/strata_control/calibration.py:41-64,67-79`）。
- Desktop では packaged Control がある経路でのみ `installerEnvironment()` が `STRATA_CONTROL_INSTALL=1` と選択した installDir を Control の installer 子プロセスに付ける。モデル起動や通常の server 環境は別経路で、ここから変数を GPU engine へ適用する処理は確認できない（`app/host/server/control-runtime.mjs:88-119, app/host/server/native-control.mjs:143-146,201-215`）。
- Desktop updater の `customProfileEnv` はこの変数を含むカスタム環境変数の非空有無を報告するだけで、パスをセットアップ先として解決する判定とは別である（`app/desktop/src-tauri/src/updater.rs:28-36,73-79,181-197`）。

## 実行時の詳細

- Python の `models.resolve_install()`、`discovery.places()`、Calibration、`tools/_paths.py` は関数呼び出し時に環境を参照する。これらの関数内に値の static cache はない。`discovery.places()` の未指定時は、明示場所に続けて `STRATA_DATA_DIR/install`、Terminal 自身、記憶済み install、Desktop install などを調べ、run config のある最初の場所を使う（`terminal/strata_control/discovery.py:174-220`）。
- `setup.py` の `CONTROL` と `_CONTROL_HOME` はモジュール読み込み時に評価され、その後 `home()` はキャッシュ済み `_CONTROL_HOME` または `ROOT` を返す。Control mode ではセットアップの run config、ログ、その他 install 出力がこの home を使う。たとえば run config と log のパスは `home()` から作られ、起動スクリプト作成前に home directory が作られる（`terminal/setup.py:97-108,9242-9249,9453,10023`）。プロセス実行中に環境変数を書き換えても `_CONTROL_HOME` は再評価されない。
- `strata install` は環境を複製して installer を子プロセスとして起動する。Terminal bundle の場合は、`STRATA_INSTALL_DIR` が未設定なら `catalog.install_root()` を `setdefault()` で設定し、ディレクトリーを best effort で作る。`setup.py` 側の書き込み失敗は同スクリプトが報告する（`terminal/strata_cli/cli.py:2139-2161`）。
- Desktop は `defaultInstall()` を呼ぶたびに環境値を解決し、環境値がなければ components 隣の `install` を作成する。既存の設定 `preferences.installDir` があれば `installRoot()` はそれを優先し、設定変更時は永続化して refresh する（`app/host/server/native-control.mjs:146,183-190,242`）。installer job には選んだ folder が `installerEnvironment(..., {installDir: folder})` 経由で渡される（`app/host/server/native-control.mjs:201, app/host/server/control-runtime.mjs:110-119`）。
- `strata_control.calibration` は install folder に `setup.py` と `tools/calibrate.py` が揃えば import path に追加して使用する。`tools/_paths.py` はこの folder の `third_party/strata-gguf-py` や converter を他候補とともに探す。見つからない場合 GGUF helper は `gguf-py was not found...` または converter 不在のメッセージで終了する（`terminal/strata_control/calibration.py:41-64, terminal/tools/_paths.py:29-54,81-86`）。
- `private_files.user_roots()` と `known_roots()` はこの値を個人用ファイルの修復対象ルートに追加する。前者は resolve 可能なものを返し、後者は存在するルートだけを返す。CLI の PermissionError 再試行処理から `repair_known_roots()` が呼ばれる経路がある（`terminal/strata_control/private_files.py:418-433,509-530; terminal/strata_cli/cli.py:2164-2183`）。

## ログと測定値

この変数自体を表示する専用ログや測定値は確認できない。観測可能な結果は各経路の出力である。Terminal の installer がない場合は `set STRATA_INSTALL_DIR to that folder...` を含む説明と終了コード 5、model inventory が空なら探索先を示す案内が出る。Calibration の必要ファイルが見つからない場合は `engine calibrate needs a full Strata folder...` の `ProfileError` となる。Desktop updater は非空値を `customProfileEnv` フィールドに含める（`terminal/strata_cli/cli.py:2143-2148,626-634; terminal/strata_control/calibration.py:61-64; app/desktop/src-tauri/src/updater.rs:181-197`）。

## 根拠

- `terminal/strata_control/discovery.py:1-20,174-220` — 明示 install と探索順、未指定時の fallback。
- `terminal/strata_control/models.py:69-92` — `--install-dir` 相当 override、環境変数、絶対パス・既存ディレクトリー検査。
- `terminal/strata_cli/cli.py:168-176,602-635,2139-2161` — CLI 優先、出力・終了経路、installer の選択と子プロセス環境。
- `terminal/setup.py:97-108,9242-9249,9453,10023` — Control 条件、module import 時の home 決定、home を使う出力例。
- `terminal/strata_control/calibration.py:41-79`、`terminal/tools/_paths.py:29-54,81-86` — 追加 import 探索と不足時の扱い。
- `terminal/strata_control/private_files.py:418-433,509-530` — repair 対象ルートとしての読み取り。
- `app/host/server/native-control.mjs:143-146,181-190,201-215,242`、`app/host/server/control-runtime.mjs:88-119` — Desktop の既定先、設定優先、Control installer への転送。
- `app/desktop/src-tauri/src/updater.rs:28-36,73-79,181-197` — 非空値の custom profile status への反映。
