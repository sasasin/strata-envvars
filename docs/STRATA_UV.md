# `STRATA_UV`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。作業開始時の Strata リポジトリは `main` で、作業ツリーに変更はありません。外部ツール `uv` 自身の動作は対象外です。

## 役割

Linux の `setup.sh` が新しい `.venv` を作るとき、uv を使う経路を選びます。uv が PATH 上に見つかった場合は、uv 管理の Python 3.12 を指定して `.venv` を作成します。`STRATA_UV` は Strata エンジンや既存の Python 環境の実行設定ではなく、このセットアップ時の選択にだけ使われます。候補名の全検索では実装上の参照は `setup.sh` の1箇所で、ほかは同ファイルのコメントでした。

## 値と判定

| 状況 | uv 探索を行うか |
|---|---|
| `STRATA_UV` が文字列 `1` | 行う |
| `STRATA_UV` が未設定、空文字、または `1` 以外 | 行わない（ただし `/etc/os-release` の `ID=nixos` 判定が成立すれば行う） |
| `/etc/os-release` の行が大文字小文字を無視して `^ID=nixos` に一致 | 行う（`STRATA_UV` の値に関係しない） |

シェルの文字列完全一致で判定するため、`1` のみが環境変数による指定です。`01`、`1foo`、`true`、`TRUE` は一致せず、空白も除去されません。未設定と空文字はいずれもこの比較では一致しません。NixOS 判定は `grep -qi '^ID=nixos' /etc/os-release` で、大文字小文字を区別せず、行頭から一致することを確認します。

## 有効になる条件

uv の使用には、次の条件がすべて必要です。

- `setup.sh` が `.venv/bin/python` のない状態で venv 作成処理に入ること。
- `STRATA_UV=1` または NixOS 判定が成立すること。
- `command -v uv` で `uv` が見つかること。

このうちどれかを満たさない場合、スクリプトは通常の Python venv 作成経路に進みます。そこでは `python3`、次に `python` を探し、Python 3.10 以上かつ `venv` と `ensurepip` を import できるものを選びます。uv の有無だけを理由にセットアップを失敗させる経路はありません。

## 実行時の詳細

`setup.sh` は最初に `.venv/bin/python` が存在し、かつ `python -m pip --version` が失敗する場合、既存の `.venv` を削除します。その後 `.venv/bin/python` がなければ、uv の選択判定を行います。したがって、正常な pip を持つ `.venv` が既にあるときは `STRATA_UV` を変更しても環境を作り直さず、この変数は読まれません。pip のない既存環境が削除された場合は、新規作成の判定に進みます。

uv が見つかった場合、`setup.sh` は `uv venv --managed-python --seed --python 3.12 .venv` を実行します。失敗時は `Could not create the uv environment in .venv.` を表示して終了します。uv が選ばれないか PATH 上にない場合は、選定した Python の `-m venv .venv` を実行します。どちらの作成経路の後も `.venv/bin/python setup.py "$@"` を `exec` し、引数をそのまま渡します。スクリプト内に実行時再読込や子プロセス用の `STRATA_UV` 上書きはありません。

## 文書との照合

`docs/INSTALL.md` は Linux で `./setup.sh` を実行する手順を案内し、`README.ja.md` も同じ起動経路を示しますが、両文書に `STRATA_UV` の値や判定条件の説明はありません。したがって、ここでは記載のあるセットアップ経路を確認し、変数の挙動は現行ソースから記述しました。性能値や実測値は該当しません。

## 根拠

- `setup.sh:11-13`: pip のない既存 `.venv` の削除。
- `setup.sh:14-30`: venv 作成条件、`STRATA_UV` と NixOS の判定、uv 探索、および通常 Python の選択。
- `setup.sh:32-45`: 通常 Python が使えない場合のインストール案内と終了。
- `setup.sh:48-56`: uv または `python -m venv` による作成、エラー時の終了、`setup.py` への引き渡し。
- `docs/INSTALL.md:49-58`, `README.ja.md:90-92`: Linux セットアップ入口の案内。
