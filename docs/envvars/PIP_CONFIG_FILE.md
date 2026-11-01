# `PIP_CONFIG_FILE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata 本体の実行時設定ではありません。この名前は `packaging/package_terminal.py` の `install_locked()` でのみ参照され、Strata が組み立てる環境変数辞書に `os.devnull` を設定し、バンドル用 Python の pip subprocess に渡されます。親環境の `PIP_CONFIG_FILE` を読む箇所はなく、継承された値をそのまま pip に渡すこともありません。対象は Terminal 配布物を作るビルド時の依存導入経路です。

## 値と判定

Strata は親環境の値を parse・比較しません。環境辞書を `os.environ` のコピーから作った後、同じキーを `os.devnull` で常に上書きします。

| 親プロセスの状態 | Strata が subprocess に設定する値 |
|---|---|
| 未設定 | `os.devnull` |
| 空文字 | `os.devnull` |
| その他の値 | `os.devnull` |

この変数に対する Strata 側の数値変換、文字列判定、境界値処理、無効値 fallback はありません。`os.devnull` の実際の値は実行 OS によります。pip がこの値をどう解釈するかは外部ツール側の動作なので、ここでは扱いません。

## 有効になる条件

- `packaging/package_terminal.py` を実行して Terminal アーカイブを作るときに限ります。通常の Strata CLI、サーバー、エンジン実行がこの変数を読む実装は見つかりません。
- `--skip-deps` を指定すると `install_locked()` が呼ばれず、この設定も行われません。
- 依存導入を行う場合は `--target` がホスト対象と一致する必要があります。この条件を満たさない場合、依存導入に進む前に `SystemExit` で終了します。
- `--wheelhouse` の有無はこの値の設定を変えません。

## 実行時の詳細

`install_locked()` は `os.environ` のコピーを作成し、`PIP_CONFIG_FILE` を `os.devnull` に設定します。同じ環境辞書は `pip install`、`pip check`、`pip list` の3つの subprocess に渡されます。この設定辞書は `install_locked()` の呼び出し時に作られ、プロセス起動後の親環境の変更を監視したり cache したりするコードはありません。`PIP_INDEX_URL` と `PIP_EXTRA_INDEX_URL` など別のキーは辞書から削除されますが、Strata によるそれらとの優先順位判定はありません。

依存導入の開始時には `installing the locked runtime wheels into the bundled interpreter (build time only)` を出力します。各 subprocess は `check=True` で起動されるため、終了コードが非ゼロなら Python の `subprocess.CalledProcessError` が発生し、パッケージ作成処理は成功しません。pip が環境変数をどう扱うか、またその結果として出すメッセージの内容は Strata の挙動として断定しません。

## 根拠

- `packaging/package_terminal.py:199-210` — `install_locked()` の役割、親環境のコピー、`PIP_CONFIG_FILE` を `os.devnull` で上書きする処理、および `pip install` 実行。
- `packaging/package_terminal.py:205-213` — 同じ環境辞書で pip の3コマンドを実行し、周辺キーを辞書から削除する処理。
- `packaging/package_terminal.py:339-362,424-428` — `--skip-deps`、対象 OS の条件、依存導入から `install_locked()` へ至る呼び出し。
- `packaging/package_terminal.py:565-566` — スクリプト実行時に `main()` の戻り値を終了コードにする箇所。
- `packaging/README.md:128-135` — Terminal アーカイブと依存 wheel の導入がビルド時に行われることの説明。

候補一覧 `000_envvers.md` には名前がありますが、Strata が親環境から値を読む実装はありません。確認できた Strata の処理は、上記の限定されたパッケージ作成経路で子プロセス用の値を設定することです。
