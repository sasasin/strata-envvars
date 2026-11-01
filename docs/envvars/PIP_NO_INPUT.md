# `PIP_NO_INPUT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main`。

## 役割

Strata 自身の通常の CLI、サーバー、エンジン実行時に読む設定ではありません。Terminal 配布物のビルドスクリプト `packaging/package_terminal.py` が、バンドル用 Python にロック済み wheel を入れるときに、pip を起動する子プロセスの環境へ `PIP_NO_INPUT="1"` を明示して渡します。候補名のソース全体検索では、この設定箇所だけが見つかりました。

## 値と判定

Strata はこの変数の既存値を読み取ったり parse したりしません。`install_locked()` 内で `env = {**os.environ, ...}` を作り、同じ辞書定義で `PIP_NO_INPUT` を文字列 `"1"` に設定します。そのため、呼び出し元プロセスで未設定、空文字、`0`、その他の文字列のどれであっても、pip 子プロセスに渡す値は常に `"1"` です。ユーザーが CLI 引数でこの値を指定する経路も、このスクリプトにはありません。

| ビルド時の条件 | 子プロセスに渡す値 |
|---|---|
| `install_locked()` が実行される | `"1"` |
| `--skip-deps` が指定され、ロック済み依存の導入を省略する | `PIP_NO_INPUT` を含むこの辞書を作らず、pip の install/check/list も起動しない |

## 有効になる条件

この設定が行われるのは `packaging/package_terminal.py` による Terminal アーカイブのビルド時だけです。依存導入をスキップしない場合、対象 OS 用のバンドル済み Python で `install_locked()` が実行されます。CLI の `--skip-deps` はこのインストール経路全体を飛ばします。対象ターゲットは Windows x86_64、Linux x86_64 / aarch64、macOS arm64 ですが、依存導入を行うビルドでは選択ターゲットがホストターゲットと一致することを先に検査します。

この環境辞書は親プロセスの `os.environ` を基に作られますが、`PIP_NO_INPUT` は固定値で上書きされます。同じ辞書から `PYTHONHOME`、`PYTHONPATH`、`PIP_REQUIRE_VIRTUALENV`、`PIP_INDEX_URL`、`PIP_EXTRA_INDEX_URL` は削除され、`PIP_CONFIG_FILE` は `os.devnull` に設定されます。これらは同じビルド処理の環境構成であり、ここでは pip 側の解釈を Strata の動作として扱いません。

## 実行時の詳細

`install_locked()` は呼び出されるたびにローカルの環境辞書を生成し、以下の3つの `subprocess.run()` に同じ `env` を渡します。

1. バンドル用 Python で `pip install` を実行し、ロックファイルに基づいて依存を導入する。
2. `pip check` を実行する。
3. `pip list --format=json --isolated` を実行し、結果を読み取ってロックとの一致を確認する。

Strata が値をプロセス内に cache する処理はありません。この設定は親プロセスの環境変数の変化を監視するものでもなく、各 `install_locked()` 呼び出し時に辞書へ固定値を設定します。対象呼び出しが終わった後の Terminal アプリ実行やサーバーモードへ、この辞書を引き継ぐ処理はありません。

ビルドでは依存導入を始める前に `installing the locked runtime wheels into the bundled interpreter (build time only)` を標準出力へ表示します。3つの subprocess は `check=True` なので、いずれかが非ゼロ終了すると Python の `subprocess.run()` が `CalledProcessError` を送出し、ビルド処理は後続の pip 呼び出しやアーカイブ生成へ進みません。このスクリプトに `PIP_NO_INPUT` 固有のログ、警告、失敗メッセージはありません。pip 自身の表示や挙動については本調査の対象外です。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:496-500`。
- 唯一の完全一致ソース参照、および親環境の複製後に `"1"` で上書きする設定、他の環境変数の削除と `PIP_CONFIG_FILE` 設定: `packaging/package_terminal.py:199-206`。
- pip の install / check / list へ同じ辞書を渡す箇所: `packaging/package_terminal.py:207-219`。
- `--skip-deps` とターゲット制約、ビルド時のインストール呼び出しと開始ログ: `packaging/package_terminal.py:339-362,424-440`。
- `check=True` の例外が `main()` から捕捉されずスクリプト終了へ伝播する構造: `packaging/package_terminal.py:208-213,533-534`。
- Terminal 依存がビルド時のみ導入される説明: `packaging/README.md:128-140`。
