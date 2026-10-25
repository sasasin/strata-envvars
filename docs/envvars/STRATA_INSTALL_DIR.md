# `STRATA_INSTALL_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Strata のインストールディレクトリを指定する環境変数です。主に、モデルの実行設定ファイル（`strata-*.json`）をどこから探すか、Terminal パッケージから完全版 Strata の installer や補助ツールをどこで見つけるか、Control モードの `setup.py` がどこへファイルを書き込むかを決めます。

これはエンジンの GPU 計算を制御する変数ではありません。読み取り側ごとに空文字や相対パスの扱いが異なるため、どの Strata 機能から参照するかで有効な指定条件が変わります。

## 値と判定

| 読み取り箇所 | 未設定時 | 空文字 | 設定値の扱い |
|---|---|---|---|
| `strata_control.discovery.places()` | Terminal 自身、記憶済みインストール、アプリの順で候補を探す | `raw is not None` なので明示指定として `Path("")`（現在ディレクトリ）だけを調べる | `expanduser()` して指定先だけを調べる。存在しない／設定ファイルがない場合も他候補へ進まない |
| `strata_control.models.resolve_install()` | 共通 discovery に委ねる | 環境変数が空文字なら `raw is not None` を満たし、絶対パスではないため `ProfileError`。空の `override` は偽として環境値へフォールバック | `expanduser()` 後、絶対パスかつ既存ディレクトリでなければ `ProfileError`。有効なら解決済みパスを返す |
| `setup.py` の Control モード | 書き込み先 `home()` は Strata ソースディレクトリ `ROOT` | `os.environ.get(...)` が偽になるため `ROOT` | `STRATA_CONTROL_INSTALL=1` かつ値が空でないときだけ、`Path(...).resolve()` を `home()` として使用 |
| `strata_cli.cli._install()` | `ROOT/setup.py` を使う | `or ROOT` により `ROOT/setup.py` を使う | 値を installer の親ディレクトリにせず、値そのものをディレクトリとして `setup.py` の場所に使う |
| `strata_cli.launch.catalog.install_root()`、`tools/_paths.py`、`strata_control.calibration`、ホスト側 JS | 各関数の記述する標準探索経路 | 多くは truthy 判定で無視。discovery 経由では上記の空文字例外がある | 一部は `expanduser()` し、一部はそのまま `Path` / `resolve()` に渡す。絶対パス・存在チェックは各処理の個別条件による |

パス文字列全体を共通形式に parse したり、全箇所で絶対パス検証を行ったりする共通 helper はありません。`~` の展開、相対パスの許可、ディレクトリ存在確認は呼び出し経路ごとに異なります。無効な値に対する単一の共通 fallback もありません。

## 有効になる条件

- `setup.py` で書き込み先を切り替えるには、別変数 `STRATA_CONTROL_INSTALL` の値が文字列全体で `"1"` である必要があります。`STRATA_INSTALL_DIR` だけを設定しても `setup.py` の `home()` は切り替わりません。
- Terminal のモデル探索では、CLI の `--install-dir` 引数が `discovery.places()` に `explicit` として渡されると、環境変数より優先されます。明示ディレクトリは唯一の探索先です。Terminal 側 `resolve_install()` も引数が truthy なら環境変数より優先し、ディレクトリが絶対パスかつ既存であることを要求します。
- アプリ側は通常、ホストプロセスが `STRATA_INSTALL_DIR` を読んで既定 install フォルダーを決め、installer 子プロセスに `STRATA_CONTROL_INSTALL=1` とともに渡します。明示的な `installDir` がなければ `STRATA_INSTALL_DIR` は子プロセス環境に追加されません。
- `strata tune` の calibration helper は環境変数で指定された場所に `setup.py` と `tools/calibrate.py` の両方がある場合にのみ、その場所を `sys.path` に追加して import を試みます。見つからない場合は `ProfileError` を返します。

## 実行時の詳細

### インストール先

`setup.py` は import 時に `STRATA_CONTROL_INSTALL == "1"` を評価し、同時に `STRATA_INSTALL_DIR` が truthy の場合だけ `_CONTROL_HOME` を作ります。`home()` は `_CONTROL_HOME` があればそれを返し、なければ `ROOT` を返します。Control モードの setup はこの `home()` を使い、たとえば llama.cpp の `third_party/`、engine feed、モデル実行設定・ログなどの出力先を install directory 配下にします。通常モードでは `_CONTROL_HOME` がなく、`STRATA_INSTALL_DIR` は `home()` を変更しません。値はモジュール import 時に定数へ保存されるため、その後の環境変更は setup プロセス内では反映されません。

Terminal の `_install()` は値が指定されていればその場所の `setup.py` を探します。Terminal bundle の場合、installer に `STRATA_CONTROL_INSTALL=1` をセットし、値がまだ環境にない場合は `install_root()` の結果を `STRATA_INSTALL_DIR` に設定して子プロセスを起動します。

### モデル探索

共通 discovery は環境変数（または明示引数）が `None` でなければ、そのディレクトリだけを候補にして、直下の `strata-*.json` 設定ファイルを数えます。Terminal の `strata models list`、launch 画面などがこの探索を利用します。変数未設定時には Terminal 自身、ユーザー設定に記録された以前の install、desktop app の install などを順に探索します。指定先に設定ファイルがない場合でも他の install にフォールバックしません。

### 補助処理

- `tools/_paths.py` は `$STRATA_GGUF_PY`、エンジン同梱の `third_party/llama.cpp/gguf-py`、開発用 checkout に続き、指定 install directory の `third_party/llama.cpp/gguf-py` を探します。見つからなければ `STRATA_GGUF_PY` の指定または setup 実行を案内して終了します。
- calibration helper は未 import の `setup` / `tools.calibrate` を指定 install directory から見つけられるか確認します。preview の `tool_available` と `--measure` 可否にも同じファイル存在条件を使います。
- `strata_control.private_files` は指定値をユーザー所有ディレクトリ群の一つとして扱います。`is_users_own()` はその配下のファイルをユーザー自身のものとして修復対象になりうるか判定します。`known_roots()` は値が truthy で、そのパスが存在する場合に private-file 調査対象へ追加します。
- desktop host の `defaultInstall()` は値が truthy なら Node.js の `resolve()` に渡し、未設定または空文字なら components ディレクトリの隣の `install` を使います。

## 観測できる結果と文書照合

`strata models list` の `--install-dir` / `STRATA_INSTALL_DIR` は指定ディレクトリだけを調べると `docs/TERMINAL.md` と `docs/TERMINAL_LAUNCH.md` に記されています。discovery の実装とも一致します。setup の per-user install は `docs/MAC.md` にも Control モードの説明があります。`docs/DETAILS.md` にはこの変数固有の説明を確認できませんでした。変数値そのものを表示する共通ログは確認できず、探索不能時や installer 不在時は各機能のエラー文を返します。

## 根拠

- `setup.py:71-83,3054-3060,4105,7184-7190,7507-7510` — Control モードの判定、書き込み先 `home()`、利用例。
- `strata_control/discovery.py:153-189` — explicit 環境値の判定、指定先だけの探索、未設定時の探索順。
- `strata_control/models.py:62-81` — CLI override と環境値の優先、絶対パス・既存ディレクトリの検証。
- `strata_cli/cli.py:2051-2069` — installer の選択と Control installer への環境値設定。
- `strata_cli/launch/catalog.py:164-180` — launch/catalog の install directory 解決。
- `strata_cli/launch/runner.py:749-757`, `tools/strata_mcp.py:2537-2548`, `apps/host/server/control-runtime.mjs:95-100`, `apps/host/server/native-control.mjs:47-51` — Control installer 子プロセスへの設定と desktop app の既定値。
- `tools/_paths.py:17-44` — install directory 内の `gguf-py` 探索。
- `strata_control/calibration.py:41-79` — calibration 用フル Strata folder の発見と判定。
- `strata_control/private_files.py:415-439,506-524` — ユーザー所有パス判定と private-file roots。
- 照合した文書: `docs/TERMINAL.md:26`, `docs/TERMINAL_LAUNCH.md:90-93`, `docs/MAC.md:78`。
