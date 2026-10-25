# `STRATA_UV`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。Strata 所有のソースと同梱スクリプトを対象とし、外部ツール内部の動作は対象外。

## 役割

Linux/macOS 用の `setup.sh` が新しい `.venv` を作る際、`uv` を使うか選びます。`uv` が選ばれた場合、スクリプトは `uv` に Python 3.12 の managed interpreter を指定して仮想環境を作らせます。これは Strata 本体の実行時設定ではありません。

## 値と判定

`setup.sh` の `[ "${STRATA_UV:-}" = "1" ]` は、変数が unset または空文字なら空文字として扱い、文字列全体が `1` と一致する場合だけ真です。数値変換や前後空白の除去はありません。

| 状態 | NixOS 判定に不一致 | NixOS 判定に一致 |
|---|---|---|
| unset / 空文字 | `uv` を探さない | `uv` を探す |
| `1` | `uv` を探す | `uv` を探す |
| その他（例: `0`, `true`, ` 1`） | `uv` を探さない | `uv` を探す |

OS 判定は `/etc/os-release` に `^ID=nixos` と一致する行があるかを `grep -qi` で調べます。大文字小文字は無視され、`ID=nixos` で始まる行なら後続文字があっても一致します。該当行が読めない、または一致しない場合は NixOS 判定になりません。

## 有効になる条件

`STRATA_UV=1` だけで常に `uv` が実行されるわけではありません。

- `python/bin/python3` が実行可能なら、`setup.sh` はその同梱 Python で `setup.py` を直接起動し、変数を判定しません。
- 同梱 Python がなくても、動作可能な `.venv/bin/python` と `pip` が既にあれば、環境作成を飛ばして既存の `.venv` で `setup.py` を起動します。この場合も変数は判定されません。
- 新しい `.venv` が必要な場合に限り、`STRATA_UV=1` または NixOS 判定が `uv` の検索条件になります。
- 条件に合っても `command -v uv` が見つけられなければ、通常の Python 探索と `python -m venv` に進みます。見つかった `uv` の `venv` コマンドが失敗した場合はエラーを表示して終了し、標準 venv に切り替えません。

## 実行時の詳細

環境作成が必要なとき、スクリプトはまず既存の `.venv/bin/python` に `pip` があるかを調べます。Python は `python3`、次に `python` の順で `venv` と `ensurepip` が import でき、Python 3.10 以上のものを探します。`uv` が見つかった分岐ではこの通常探索を行わず、`PY=3.12` として次を実行します。

```sh
"$UV" venv --managed-python --seed --python "$PY" .venv
```

成功後は `.venv/bin/python setup.py "$@"` を `exec` します。`uv` がない分岐では、選んだ Python に `-m venv .venv` を実行します。通常の Python が見つからない場合は OS のパッケージマネージャーによるインストールを試みるコードがあります。これらの後続処理は `STRATA_UV` を再評価しません。

`setup.sh` は `update.sh` からも呼ばれる旨を記しています。その場合も環境変数は通常のプロセス環境として引き継がれますが、判定は上記の `.venv` 作成条件に限られます。起動後に環境変数を変更して再評価する処理や、子プロセス向けの値の上書きはありません。

## 根拠

- `setup.sh:7-13`: 同梱 Python がある場合の早期 `exec` と環境変数分岐の回避。
- `setup.sh:17-27`: 壊れた `.venv` の削除、既存環境の判定、`STRATA_UV` の厳密な文字列比較、NixOS 条件と `uv` 検索。
- `setup.sh:28-37,39-51`: `uv` がある場合の Python 3.12 指定、ない場合の Python 探索と macOS 用フォールバック。
- `setup.sh:52-74`: Python 不足時の処理、`uv venv` と標準 `venv` の分岐および失敗時の終了。
- `setup.sh:76`: `.venv` での `setup.py` 起動。

ソース全体で `STRATA_UV` の直接参照を確認できたのは `setup.sh` のコメント2箇所と判定1箇所です。`docs/INSTALL.md` などの関連資料にもこの変数の追加説明はありませんでした。
