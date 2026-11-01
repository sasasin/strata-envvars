# `STRATA_CONTROL_INSTALL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

`setup.py` と `tools/strata_mcp.py` を Strata Control / Terminal の同梱 Python 向けインストールモードで動かすための内部フラグです。`setup.py` では Python パッケージや通常のエンジン実行ファイルをインストールする代わりに、モデルを準備してエンジン component を参照する設定を作る経路を選びます。`tools/strata_mcp.py` では MCP サーバー自身の Python をインストール用にも使い、インストール子プロセスへ Control mode を渡します。

これは一般的なモデル設定やサーバー実行時の推論設定ではありません。通常のフルソース版セットアップで明示しなければ Control mode にはなりません。

## 値と判定

両方の読み取り箇所が `os.environ.get("STRATA_CONTROL_INSTALL") == "1"` で判定します。数値変換や truthy 判定はせず、文字列全体の完全一致です。

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `1` | 有効 |
| `0`、`01`、`true`、`1 `、その他の文字列 | 無効 |

未設定時の既定は無効です。CLI 引数でこの値判定を上書きする処理はありません。ただし Strata の起動ラッパーは、対象モードで `1` を環境へ設定してから `setup.py` を起動します。判定値は各 Python モジュールの import 時にモジュール定数 `CONTROL` へ保存されます。そのプロセス内で後から環境を書き換えても再判定されません。子プロセスの環境は呼び出し元が明示的に構成します。

## 有効になる条件

### `setup.py`

環境変数が厳密に `1` であることが必要です。さらに、実際に通る OS・CLI 経路によって効果が変わります。

- macOS では Control mode の場合に `mac_control_setup()` または DeepSeek 用 `mac_dsv41_setup()` へ進みます。通常の macOS セットアップが `metal/setup_mac.py` に委譲される経路は `CONTROL` が偽の場合です (`setup.py:9062-9069, 9218-9223`)。
- Windows/Linux の通常セットアップでは `engine_step()` が Control 専用の `control_engine_step()` を使います (`setup.py:7772-7777`)。
- `--backend sycl` は Control 判定後の通常分岐で SYCL セットアップへ委譲します。従って同オプションでは Control 専用 engine step は使われません (`setup.py:9220-9225`)。
- `STRATA_INSTALL_DIR` が設定され、かつ空でなければ、その値を絶対パス化した場所が書き込み先 `home()` になります。Control mode でも `STRATA_INSTALL_DIR` が未設定または空なら `ROOT` が使われます (`setup.py:82-88`)。

Control mode の実行時効果は次のとおりです。

- `pip_install()` は必要パッケージが同梱 Python にあるかを確認し、不足があればエラーにします。パッケージのインストールは行いません (`setup.py:3562-3571`)。FP4-Local の変換に PyTorch 等が不足すると、別の準備方法を案内して失敗します (`setup.py:3601-3617`)。
- `run()` は外部コマンドを実行する前に、実行対象を現在の Python が起動する同梱 `tools/` または `tools/dsv41/` 内の準備ツールに制限します。許可外コマンドは `AcquisitionRefused` になります (`setup.py:959-967`)。
- エンジン段階では component を検索し、エンジンを取得・ビルドしません。設定の `exe` はエンジン実行ファイルのパスではなく `component:strata-engine` です (`setup.py:7736-7747, 7772-7777, 6643-6645`)。モデル準備をエンジンなしで継続できる経路では警告が出ます。`STRATA_NEED_ENGINE=1` かつ `STRATA_ALLOW_NO_ENGINE!=1` ならモデル取得前に `fail()` で停止します (`setup.py:7751-7763`)。
- Hip tuning の一部は通常セットアップでは設定ファイルへ直接書かれますが、Control mode ではその処理を行わず、コメント上はサーバー側の選択に委ねています (`setup.py:10305-10315`)。

### `tools/strata_mcp.py` と起動元

MCP サーバーの `CONTROL` も起動時に同じ完全一致で決まります。このとき `Strata.python_override` はサーバーの `sys.executable` になり、インストールジョブの spec に `control: true` が記録されます (`tools/strata_mcp.py:46-48, 493-508, 2417-2427`)。ジョブ実行時は子 `setup.py` の環境で `STRATA_CONTROL_INSTALL=1`、`STRATA_INSTALL_DIR=<root>`、`PYTHONNOUSERSITE=1` を設定し、`PYTHONHOME`、`PYTHONPATH`、`VIRTUAL_ENV` を取り除きます (`tools/strata_mcp.py:2841-2852`)。

Strata の起動元には、Terminal の `strata launch` が setup 子プロセスへ `1` を設定する経路 (`strata_cli/launch/runner.py:1142-1153`)、Terminal の `strata install` が Terminal バンドルと識別できた場合に設定する経路 (`strata_cli/cli.py:2064-2082`)、デスクトップアプリの環境構築 (`apps/host/server/control-runtime.mjs:106-111`) と staging 検査 (`apps/desktop/scripts/stage-control.py:162-168`) があります。Dockerfile もビルド時の setup 呼び出しで `1` を明示しています (`Dockerfile:83`, `docker/Dockerfile:44`)。これらは環境値を設定・転送する箇所であり、別の値判定実装ではありません。

## 実行時の詳細

`setup.py` は import 時に `CONTROL` と `_CONTROL_HOME` を決めます。setup の各工程でその定数を参照するため、値の変更はその setup プロセスを起動し直すまで反映されません。Control mode で作成された run config は `component:strata-engine` を記録し、実際のエンジン component はモデル実行時に解決されます。Control mode の setup 自身がエンジンを取得する分岐はありません (`setup.py:77-88, 7736-7747, 8029`)。

変数の値そのものを示す専用の有効化ログは見当たりません。周辺工程で同梱 Python のパッケージ不足、エンジン不足などがあれば `fail()` / `warn()` によるメッセージが出ます。Control mode の不足パッケージは再インストール案内を伴って失敗し、エンジン不足は `STRATA_NEED_ENGINE` と `STRATA_ALLOW_NO_ENGINE` の組み合わせで停止または警告付き継続になります。`setup.py` の正常終了コードは選択したセットアップ経路の戻り値によります。MCP インストール子プロセスは終了コードを記録し、`strata-mcp: setup ended with exit code ...` を出力します (`tools/strata_mcp.py:2855-2859`)。

`docs/MAC.md` も、アプリと `strata launch` の Mac セットアップについて、Control mode はモデルファイルを取得・準備し `component:strata-engine` を記録し、Metal engine をビルドしないと説明しています (`docs/MAC.md:115-125`)。これは上記の実装分岐と一致します。

## 根拠

- 環境値の全直接読み取りと import 時判定: `setup.py:77-88`; `tools/strata_mcp.py:46-48`。
- Control mode の外部コマンド制限、Python パッケージ確認、engine component 選択: `setup.py:959-975, 3541-3571, 3601-3617, 6643-6645, 7736-7777`。
- Engine 不在時の停止条件と警告: `setup.py:7751-7769`。
- macOS と SYCL の分岐: `setup.py:9062-9069, 9218-9225`。
- Terminal / app / MCP からの設定・転送: `strata_cli/launch/runner.py:1142-1153`, `strata_cli/cli.py:2064-2082`, `apps/host/server/control-runtime.mjs:106-111`, `apps/desktop/scripts/stage-control.py:162-168`, `tools/strata_mcp.py:2417-2433, 2841-2859`。
