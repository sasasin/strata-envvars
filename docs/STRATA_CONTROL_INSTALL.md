# `STRATA_CONTROL_INSTALL`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Strata の `setup.py` と `tools/strata_mcp.py` を、Strata Control（デスクトップアプリ）の Python・エンジンコンポーネントを使うインストール経路に切り替えます。これは通常の推論エンジンが読む設定ではなく、インストーラーと MCP サーバーの起動時に使われるモード指定です。

`setup.py` では、Control モードはモデルをダウンロード・準備して実行設定を書く一方、Python パッケージやエンジンのインストール、エンジンのビルドを行わず、実行設定の `exe` に `component:strata-engine` を指定します。macOS では Control モード専用のモデル設定経路を通ります。エンジンはモデル読み込み時にコンポーネントとして解決されます（`setup.py:72-83,6125-6127,7160-7193,7196-7201,7941-7944`）。

## 値と判定

| 値 | `setup.py` と `tools/strata_mcp.py` での結果 |
|---|---|
| unset | 無効 |
| 空文字 | 無効 |
| `1` | 有効 |
| その他（例: `0`, `true`, `01`, ` 1`） | 無効 |

両ファイルとも `os.environ.get("STRATA_CONTROL_INSTALL") == "1"` で文字列全体を比較します。数値変換、空白除去、大文字小文字変換はありません。判定はモジュール読み込み時に `CONTROL` 定数へ保存されるため、同じプロセス内で環境変数を後から変更しても、そのモジュールの分岐は再評価されません（`setup.py:77`, `tools/strata_mcp.py:48`）。

## 有効になる条件

- 変数が `"1"` の場合に限り、setup.py の Control 用分岐が選ばれます。通常の `setup.py` 実行や通常の MCP サーバー起動では、コード自身がこの変数を有効にしません。
- MCP サーバーが Control モードのインストールジョブを起動するとき、子プロセス環境に `STRATA_CONTROL_INSTALL="1"` と `STRATA_INSTALL_DIR=<install root>` を設定します。その際 `PYTHONNOUSERSITE="1"` も設定し、`PYTHONHOME`、`PYTHONPATH`、`VIRTUAL_ENV` を取り除きます。この代入はインストール子プロセスに対するもので、MCP サーバーの既存プロセス環境を変更しません（`tools/strata_mcp.py:2537-2548`）。
- `setup.py` は Control モードかつ `STRATA_INSTALL_DIR` が空でない場合に限り、その値を `Path(...).resolve()` したパスをインストール先 `home()` に使います。未設定または空文字なら `home()` はソースディレクトリ `ROOT` です。`STRATA_INSTALL_DIR` はこの箇所で別途 truthy 判定されます（`setup.py:77-83`）。
- macOS で Control モードの場合、`setup.py` は `mac_control_setup()` を呼び、Metal エンジンのビルド用 `metal/setup_mac.py` を実行しません。macOS で Control モードでなければ通常の `mac_setup()` 経路です（`setup.py:7802-7803,7941-7942`）。
- 他の対応経路では `engine_step()` が Control 用 `control_engine_step()` に分岐し、エンジンコンポーネントを検索します。コンポーネントが見つからない場合も、`STRATA_NEED_ENGINE="1"` かつ `STRATA_ALLOW_NO_ENGINE` が厳密に `"1"` でない場合を除き、警告を出してモデルのダウンロード・準備を続ける経路があります（`setup.py:7160-7187,7196-7201`）。
- Control モードの `run()` は、起動するコマンドが現在の Python で、`-m` ではなく、`ROOT/tools` 内のスクリプトであることを要求します。条件外なら `AcquisitionRefused` になります（`setup.py:747-755`）。また pip パッケージ導入は行わず、バンドル済みモジュールが欠けていればエラーで終了します。NVIDIA FP4-Local 変換に必要な PyTorch / transformers がない場合も、このモードではソース版インストーラーを使うよう案内して失敗します（`setup.py:3117-3133,3162-3178`）。

## 実行時の詳細

`setup.py` は起動時に `CONTROL` と `_CONTROL_HOME` を評価します。Control モードでは `home()` がインストール用のユーザーデータ領域を返し、ソースコード・ツールは `ROOT` に残ります。通常モードでは `home()` は `ROOT` です。後続の設定出力は `CONTROL` に応じて実行エンジンをファイルパスではなく `component:strata-engine` として記録します（`setup.py:71-83,6125-6127`）。

Control 用エンジン経路は、既存コンポーネントを解決して情報を表示します。エンジンが未導入でも、`STRATA_NEED_ENGINE` による明示的な必須指定がない場合は「まだインストールされていない」旨を警告してモデル準備を続行します。画像エンコーダーがエンジンにない場合は画像機能を無効にします（`setup.py:7160-7193`）。macOS の Control 用経路もエンジンをコンポーネントとして扱い、準備した設定のエンジン名を `component:strata-engine` にします（`setup.py:7623-7628`, `docs/MAC.md:76-80`）。

MCP サーバーが生成するインストールジョブでは、子プロセスへ Control モードを明示的に渡して setup.py を実行します。通常起動の継承環境に含まれる `STRATA_NO_ACQUIRE` はこの明示的なインストールジョブでは子環境から除かれます。Control モード自体は `run()` のコマンド制限や pip / エンジン取得制限によって、通常のビルド・インストール経路とは異なる動作になります（`tools/strata_mcp.py:2537-2548`, `setup.py:740-755,3124-3145,7160-7165`）。

## 根拠

- `setup.py:71-83` — `CONTROL` の完全一致判定、任意の `STRATA_INSTALL_DIR` と `home()`。
- `setup.py:747-766,3117-3145,3162-3178` — Control モードのコマンド制限、パッケージ導入分岐。
- `setup.py:6125-6127,7160-7201,7802-7803,7941-7944` — 実行エンジン指定、コンポーネント解決、OS ごとの経路。
- `tools/strata_mcp.py:46-48,2537-2548` — MCP サーバーでの判定と、Control インストール子プロセスへの環境設定。
- `docs/MAC.md:76-80` — macOS のアプリと Control モードに関する説明。コードの分岐と照合。
