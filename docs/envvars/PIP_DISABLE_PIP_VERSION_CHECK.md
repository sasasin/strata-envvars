# `PIP_DISABLE_PIP_VERSION_CHECK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

Strata 自身がこの名前を親プロセスの環境から読み取って設定を切り替える実装は見つかりませんでした。Strata は Terminal 配布物のビルド時に、同梱 Python へロック済み wheel を入れる `pip` 子プロセスへ、この変数を固定値 `"1"` で渡します。したがって、ビルドを起動した側での未設定・空文字・任意の値は、この子プロセス向けには引き継がれません。

## 値と判定

`packaging/package_terminal.py` は `env = {**os.environ, ...}` で親環境を複製した後、`"PIP_DISABLE_PIP_VERSION_CHECK": "1"` を辞書リテラルで上書きします。Strata 側で親の値を parse・検証する処理はなく、未設定、空文字、`0` などの値に対する Strata 独自の判定や fallback はありません。子プロセスに渡す値は常に文字列 `1` です。

## 有効になる条件

- `packaging/package_terminal.py` を通常の依存同梱モードで実行し、`--skip-deps` を指定しないこと。`main()` はこの場合だけ `install_locked()` を呼びます。
- 対象 OS や CPU に対応するビルド環境であること。依存インストールは同梱インタープリター上で実行され、スクリプトは通常ビルドでホストと `--target` が異なる場合に終了します。
- `--wheelhouse` の有無は渡す wheel の場所を変えますが、この環境変数の固定値は変えません。

`--skip-deps` の場合、依存インストールの `pip` 子プロセスは起動されないため、この設定も適用されません。これは配布可能なアーカイブではなくレイアウト確認用とスクリプトの説明にあります。

## 実行時の詳細

`install_locked()` は環境辞書を作ってから、同じ辞書を `pip install`、`pip check`、`pip list` の各 `subprocess.run()` に渡します。環境辞書の作成時点で親の `os.environ` をコピーし、当該キーを `"1"` に置き換えるため、これらの各子プロセスに共通して渡されます。Strata による起動後の再読み込みや cache はありません。ここでの制御対象はパッケージ作成時の子プロセスだけで、生成された Terminal の通常実行時に Strata がこの環境変数を設定する経路ではありません。

最初の `pip install` と `pip check` は `check=True` で標準出力・標準エラーを捕捉せずに実行します。失敗時は `subprocess.run()` が例外を送出し、`install_locked()` 内で処理を回復するコードはありません。`pip list` も `check=True` で、標準出力を JSON として読みます。Strata はこの変数に関する独自ログ、警告、終了コードを追加しません。pip がこの値をどう解釈して何を表示するかは外部プログラムの挙動なので、ここでは扱いません。

`strata_control/offline.py` の `OFFLINE_ENV` にも同名キーと値 `"1"` が列挙され、`child_environment(offline=True)` はそれを返す辞書へ上書きします。一方、調査対象 commit の Strata 本番コードで `child_environment()` を呼び出す箇所は見つかりませんでした。したがって、この辞書定義だけからサーバーが起動する子プロセスへ実際に転送されるとは判断できません。offline が false のとき同 helper はキーを削除しますが、この関数にも親環境を読み取る動作はありません。

## 根拠

- `packaging/package_terminal.py:199-213` — 親環境の複製、値 `"1"` の設定、および `pip install` / `pip check` / `pip list` への環境引き渡し。
- `packaging/package_terminal.py:339-357,424-429` — `--skip-deps` オプションと、指定しない場合だけ依存 wheel をインストールする分岐。
- `packaging/package_terminal.py:360-362` — 通常ビルドにおける `--target` とホストの一致条件。
- `packaging/package_terminal.py:208-213` — 子プロセスの失敗判定、出力捕捉の違い。
- `packaging/README.md:128-140` — Terminal アーカイブの依存がビルド時に入ることと、`--skip-deps` がレイアウト確認用であること。
- `strata_control/offline.py:47-61,122-136` — offline 子環境辞書の定義と helper の動作。`child_environment` の本番呼び出し箇所はありません。
