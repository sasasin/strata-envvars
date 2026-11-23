# `STRATA_CONTROL_INSTALL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Control（デスクトップアプリ、および Terminal bundle の `strata launch`）が `setup.py` と `strata_mcp.py` を専用のインストール経路で動かすためのプロセス内フラグ。Python モジュール読み込み時に値を判定し、`CONTROL` 定数として保持する。GPU engine 自身や通常のモデル実行を直接制御する変数ではない。未設定または値が厳密に `1` でない場合、通常の Terminal installer / MCP server 経路になる（`terminal/setup.py:97-108`, `terminal/tools/strata_mcp.py:54-56`）。

Control 経路では、モデルをダウンロード・準備し、設定に `component:strata-engine` を記録する。engine は Control の component として別途解決し、setup が通常の pip install や engine の取得・コンパイルを行わない。準備用ツールや gguf-py 用ソースの取得は別であり、すべてのネットワーク取得を無効にするフラグではない（`terminal/setup.py:1131-1157`, `4311-4316`, `7620-7628`, `9373-9377`, `9513-9520`）。

## 値と判定

両読み取り箇所とも `os.environ.get("STRATA_CONTROL_INSTALL") == "1"`。文字列全体を大文字小文字区別で比較し、数値変換や trim はしない。未設定、空文字、`0`、`true`、`True`、`01`、` 1`、`1 `、`1anything` はすべて無効。`1` だけが有効。空文字は「設定済み」として扱われない。境界値や負値の数値判定はない（`terminal/setup.py:102`, `terminal/tools/strata_mcp.py:56`）。

| 読み取り箇所 | unset / 空文字 | 有効値 | 無効値の例 |
|---|---|---|---|
| `terminal/setup.py` | `CONTROL=False` | 文字列 `1` | `0`, `true`, `01`, ` 1`, `1 ` |
| `terminal/tools/strata_mcp.py` | `CONTROL=False` | 文字列 `1` | `0`, `true`, `01`, ` 1`, `1 ` |

既定値を CLI 引数で上書きする仕組みはない。CLI の `--backend sycl` などは Control 判定後に分岐を選ぶ別条件である。`STRATA_INSTALL_DIR` は別変数で、Control が有効かつ空でない場合にのみ `setup.py` の書き込み先 `home()` をその絶対パスにする。未設定・空文字なら `ROOT` が書き込み先になる（`terminal/setup.py:103-108`）。

## 有効になる条件

- `setup.py` では import 時に `CONTROL` が確定する。通常の Windows/Linux installer 経路では `engine_step()` が Control 用の component 解決へ進む。モデル設定の engine 名は `component:strata-engine` になる（`terminal/setup.py:7620-7628`, `9513-9520`）。
- macOS では通常モデルの経路が Control 用 `mac_control_setup()` へ進む。ただし Hy4-Flash と Inkling-2-Mini は先に専用 handler へ分岐するため、この通常 Control 経路とは異なる（`terminal/setup.py:11216-11219`, `11407-11417`）。
- `--backend sycl` の場合、Control 有効時は Intel Arc 用の `intel_control_setup()` に進む。Linux 対応の Arc、対応モデル、および既存 GGUF ファイルが必要で、モデルファイルのダウンロードも engine のコンパイルも行わない。Control 無効時は source build の `sycl_setup()` に進む（`terminal/setup.py:9267-9272`, `9301-9325`, `11414-11417`）。
- Control installer の `run()` は、同梱 preparation tool の実行（および Hy4/Inkling の tokenizer export）に実行対象を制限する。Python package は同梱済みか検査し、不足時は `this copy of Strata Control lacks ...` として終了する。NVIDIA FP4-Local の変換に必要な PyTorch 等が不足する場合も、Control 経路では別 installer を案内して失敗する（`terminal/setup.py:1131-1140`, `4286-4316`, `4346-4359`）。
- engine component が見つからない場合、通常は警告後もモデルを準備できる。`STRATA_NEED_ENGINE=1` かつ `STRATA_ALLOW_NO_ENGINE` が厳密な `1` でなければ、ダウンロード前に失敗する。`strata launch` はこれらを自身の engine 状態に応じて子プロセスへ設定する（`terminal/setup.py:9387-9399`, `terminal/strata_cli/launch/runner.py:1650-1658`）。

## 実行時の詳細

- 値は `setup.py` と `strata_mcp.py` の各モジュール import 時に一度読み、`CONTROL` に保存される。プロセス稼働中に環境を変更しても読み直さない。子プロセスには起動時の環境が継承されるか、呼び出し側が `1` を明示して渡す。
- `strata_mcp.py` の Control モードは現在の `sys.executable` を installer Python として使い、`.venv` を作らない。MCP の install job は `setup.py` を起動するとき `STRATA_CONTROL_INSTALL=1` と `STRATA_INSTALL_DIR=<root>` を設定し、Python 環境上書き用の3変数を除去する（`terminal/tools/strata_mcp.py:580-590`, `802-806`, `2727-2743`, `3134-3164`）。
- デスクトップ app は installer environment に `STRATA_CONTROL_INSTALL=1` を設定する。Terminal bundle の `strata install` も bundle 判定時に同じ値を設定し、`strata launch` はモデル準備と Intel pack 準備の `setup.py` 子プロセスに設定する（`app/host/server/control-runtime.mjs:110-120`, `terminal/strata_cli/cli.py:2139-2157`, `terminal/strata_cli/launch/runner.py:1650-1661`, `1797-1805`）。
- `CONTROL=True` では `setup.py --update` の git pull をスキップする（`terminal/setup.py:8302-8308`）。通常モデルの setup は model files を取得・準備し、run config を書く。Control 用 engine が未導入でも config は component 名を保持し、engine をモデル読み込み時に解決する（`terminal/setup.py:9373-9399`, `9840-9857`）。
- 失敗・進捗はこの変数専用のログではない。setup の共通出力は stdout に表示される。engine 不在で続行する場合は `no engine is installed for this PC yet ...`、engine 必須で止める場合は engine 案内のエラーを出し、setup は exit code 1 で終了する（`terminal/setup.py:997-1005`, `1039-1056`, `9387-9399`）。

## 根拠

- 値の読み取りと install root: `terminal/setup.py:97-108`。
- installer の subprocess 制限・package/engine の扱い: `terminal/setup.py:1131-1157`, `4286-4316`, `9513-9520`。
- Control server の Python 選択と install job: `terminal/tools/strata_mcp.py:54-56`, `580-590`, `2727-2743`, `3134-3164`。
- app / Terminal launcher からの環境設定: `app/host/server/control-runtime.mjs:110-120`, `terminal/strata_cli/cli.py:2139-2157`, `terminal/strata_cli/launch/runner.py:1650-1661`。
- engine 不在時の継続・終了、Intel Arc 経路: `terminal/setup.py:9267-9325`, `9373-9405`, `9840-9857`。
- 関連資料 `docs/MAC.md:119-129` は Mac の Control install が model files を準備し、component engine を run config に書くことを説明している。上記の他 OS の差や値判定はソースコードで確認した。
