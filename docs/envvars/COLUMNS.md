# `COLUMNS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Strata 本体が `COLUMNS` を読み取って端末幅や処理を決める実装は見つからなかった。確認できた Strata の動作は、launcher と `setup.py` が子プロセス向け環境を親プロセスの `os.environ` から複製するときに、この名前を特別扱いせず転送することだけである。子プロセスや端末ライブラリがこの値をどう使うかは、Strata の動作としては扱わない。

launcher は `Runner._env()` で環境を複製してから `quiet_crash_env()` に渡し、`Runner._spawn()` がその環境を `subprocess.Popen` に渡す。`setup.py` の `engine_env()` も同様に環境全体を複製し、HIP 用のライブラリパスを必要に応じて追加する（`strata_cli/launch/runner.py:641-651`、`setup.py:4720-4732`）。

## 値と判定

Strata は `COLUMNS` の値を parse・比較・数値変換しない。次の表は launcher の子プロセス環境を作る経路で、親の環境を辞書として複製することから分かる転送規則である（`strata_cli/launch/runner.py:641-646`）。

| 親プロセスの状態 | 子プロセス用環境での扱い |
|---|---|
| 未設定 | `COLUMNS` は追加されない |
| 空文字 | 空文字のまま複製される |
| `0`、`1`、`120` など | 文字列のまま複製される |
| `true`、`false`、`0anything`、空白を含む値など | 判定・変換せず、その文字列のまま複製される |

数値としての妥当性、正負、境界、大文字小文字は Strata では検査されない。launcher は環境を複製した後、`GGML_NO_BACKTRACE` や Strata 固有の変数を別途設定・削除するが、`COLUMNS` は変更しない（`strata_cli/launch/runner.py:641-646`、`strata_control/childenv.py:27-33`）。`setup.py` の `engine_env()` も環境全体を複製し、必要な `PATH` または `LD_LIBRARY_PATH` を更新する（`setup.py:4727-4732`）。

## 有効になる条件

- `Runner._env()` を使って `setup.py` などを起動する経路では、起動元プロセスに存在する `COLUMNS` が子プロセスへ引き継がれる。launcher はコピー後に `PYTHONUNBUFFERED`、`PYTHONIOENCODING` などを追加し、特定の Strata 変数を変更するが、`COLUMNS` 用の分岐はない（`strata_cli/launch/runner.py:641-651`）。
- `setup.py` の `engine_env()` を使って engine の情報取得用プログラムを起動する経路でも、環境を複製して `COLUMNS` を引き継ぐ（`setup.py:4720-4732`）。
- `COLUMNS` を読む Strata の設定分岐、CLI 引数との優先順位、OS/backend/build macro による値判定は確認できなかった。転送先で値がどう解釈されるかは本書の対象外である。

## 実行時の詳細

値は `Runner._env()` または `engine_env()` が子プロセス用辞書を作る時点で、親プロセスの環境から複製される。Strata は `COLUMNS` 専用の cache を持たず、実行中に親環境が変わった場合の再読込も行わない。次の子プロセス起動時に作られる環境辞書が、その時点の `os.environ` を基にする。`Runner._env()` の結果は後続処理で他のキーを追加・削除してから `Popen` に渡される（`strata_cli/launch/runner.py:641-651`）。

`setup.py` の `run()` は環境を複製して `subprocess.run(..., env=env)` に渡す。`engine_env()` は `os.environ` を複製した後、HIP ライブラリディレクトリを `PATH` または `LD_LIBRARY_PATH` の先頭に加える（`setup.py:904-908`、`setup.py:4720-4732`）。

## ログと測定値

`COLUMNS` の値に基づく Strata 固有のログ、警告、終了・失敗経路、測定値は確認できなかった。子プロセスへ転送する事実だけでは、端末幅や表示がどう変わるかは断定できない。

## 根拠

- `strata_cli/launch/runner.py:641-651` — 親環境を複製し、子プロセス起動時に環境として渡す。
- `strata_control/childenv.py:27-33` — launcher が呼ぶ環境調整 helper は `GGML_NO_BACKTRACE` を扱い、`COLUMNS` を参照しない。
- `setup.py:904-908` — `run()` が環境辞書を複製して子プロセスへ渡す。
- `setup.py:4720-4732` — engine 用環境を `os.environ` から複製し、ライブラリパスのみ必要に応じて更新する。
