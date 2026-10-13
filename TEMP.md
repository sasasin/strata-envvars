# `TEMP`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。Strata 所有ソースの明示的な参照を調査。外部ランタイム内部の挙動は対象外。

## 役割

Strata の Windows 起動用 `START-HERE.bat` は、Python インストーラーのダウンロード先と起動元に `%TEMP%` を使います。また、`serve/server.py` は HIP バックエンドのエンジン用子プロセス環境を作る際、設定済みで書き込み不能な `TEMP` を検出し、書き込み可能な一時フォルダーへ置き換えます。

## 値と判定

| 箇所 | `TEMP` が未設定または空 | `TEMP` が非空 | 判定・結果 |
|---|---|---|---|
| `serve/server.py` の HIP 環境ガード | 検査対象にならず、子環境ではそのまま（未設定なら未設定） | `tempfile.TemporaryFile(dir=TEMP)` が成功するかを検査 | 成功なら値を維持。`OSError` なら書き込み不能としてフォールバック候補にする |
| `START-HERE.bat` の Python 導入 | 特別な処理なし | `strata-python-setup.exe` の保存先・起動元として展開 | 値の検証、空文字時の fallback、パスの正規化はしない |

サーバーの判定は「値が存在するか」だけでなく、Python の `env.get(k)` が truthy かを見ます。したがって空文字は未設定同様に検査されず、`"0"` や空白だけの値も非空値としてパス検査に進みます。パス検査は `TemporaryFile` の作成が `OSError` を起こすかどうかであり、文字列の形式やディレクトリの存在だけを個別判定するものではありません。

## 有効になる条件

- サーバーが Strata エンジンを起動し、`child_env(cfg)` で子プロセス環境を構成する経路で適用されます。通常起動と replica 起動の両方がこの関数を使います。
- `child_env` が HIP バックエンドと判定したときだけ `hip_env_guard` を呼びます。CUDA その他のバックエンドでは、このガードは `TEMP` を検査・変更しません。
- `child_env` はまず親プロセスの環境をコピーし、設定ファイルの `cfg["env"]` を文字列化して上書きした後に HIP ガードを実行します。そのため設定の `env` にある `TEMP` も同じ検査対象です。
- `START-HERE.bat` の参照は Windows の初回セットアップで Python が見つからず、python.org からインストーラーを取得する経路です。`winget` 経由で導入できる経路ではこの `%TEMP%` のダウンロード処理に入りません。

## 実行時の詳細

HIP ガードは非空の `TEMP`、`TMP`、`TMPDIR` のうち書き込み不能なものをまとめて `bad` にします。1つでもあれば、まずログファイルの親ディレクトリ（ログがなければ設定 `cwd`、それもなければ Strata のルート）の隣にある `tmp`、次に Strata ルート直下の `tmp` を作成・検査し、最初に書き込み可能だった同じディレクトリを `bad` に含まれる変数すべてへ設定します。`TEMP` が有効で `TMP` だけが不正なら `TEMP` は変更しません。

両方の候補が使えない場合、ガードは環境値を変更せず、stderr に `strata serve: AMD: ... not writable (AMD's runtime needs a writable temporary folder)` を出します。値を変更した場合は、変数ごとに `strata serve: AMD: TEMP=<旧値> is not writable: using <新しいパス>` の形式で stderr に出します。検査と変更はエンジン起動前の環境辞書上で行われ、その辞書がエンジン子プロセスへ渡されます。ガード自身が親サーバーの `os.environ` を書き換える処理はありません。

`START-HERE.bat` は `%TEMP%\strata-python-setup.exe` にダウンロードし、同じ場所にファイルが存在すれば `/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0` で起動します。ダウンロード失敗時に別のパスへ切り替える処理はこの箇所にはありません。

Python の `Vision.work_dir()` も `tempfile.mkdtemp()` を `dir` 未指定で呼び出しますが、Strata ソースはその箇所で `TEMP` を直接読み取っていません。Python 標準ライブラリがどの環境変数をどう解釈するかは、この調査の Strata 固有の挙動としては断定しません。

## 根拠

- `serve/server.py:2622-2639`: 親環境のコピー、設定 env の上書き、HIP のみのガード呼び出し。
- `serve/server.py:2642-2647,2650-2680`: 一時ファイル作成による書き込み検査、候補パス、変数の置換、stderr ログ。
- `serve/server.py:6234-6238,6375-6393`: replica と通常起動の子環境の利用。
- `START-HERE.bat:18-21`: インストーラーの `%TEMP%` への保存と起動。
- `docs/TROUBLESHOOTING.md:148-153`: Windows AMD での説明はガード実装と一致し、手動起動時は `TEMP` と `TMP` を書き込み可能なフォルダーにするよう案内しています。
