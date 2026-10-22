# `STRATA_DOCUMENTS_DIR`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。Strata 所有コードを対象とし、テストコードと外部依存は挙動の根拠に含めていない。

## 役割

ユーザーの Documents フォルダーを明示する環境変数。主に二つの経路で使われる。

- Terminal / CLI の既存モデルデータ探索では、この値に `Strata` を加えたフォルダーを候補にする。
- デスクトップアプリでは、新しいモデルライブラリの既定位置を決める際、この値に `Strata/Models` を加えた位置を使う。

いずれもこの変数だけで保存先が必ず決まるわけではない。既存設定、既存データ、書き込み可否などが優先・介在する。

## 値と判定

値は文字列として扱われ、数値変換や大小文字比較はない。空文字は未指定と同じ扱い。

| 読み取り経路 | 設定値 | 結果 |
|---|---|---|
| Python `strata_control.discovery.documents_dirs()` | 空でない値 | `Path(value)` を Documents 候補の先頭に加える。絶対パスかどうかの検査や `~` 展開はしない。 |
| Node `defaultModelDirectory()` | 空でない絶対パス | `STRATA_MODELS_DIR` が空でない場合を除き、既定モデルフォルダーの基点にする。 |
| Node `defaultModelDirectory()` | 相対パスまたは空文字 | 相対パスは採用せず、OS ごとの Documents 探索へ進む。 |
| どちらも | 未設定または空文字 | OS ごとの Documents 既定値・探索方法を使う。 |

Node のパス絶対判定は実行プラットフォームに対応する `path.isAbsolute()` による。Python 側は存在確認を `data_dir()` の候補採用時に行うが、候補列挙自体では値を検証しない。

## 有効になる条件

### Terminal / CLI の既存データ探索

`discovery.data_dir()` は、まず Terminal とデスクトップアプリの設定ファイルに記録されたデータフォルダーを同期・評価する。その後、Documents 候補として得た各フォルダーに `Strata` を加え、`Models`、`models`、`packs` のいずれかが存在し、かつ中に項目がある場合に採用する。設定済みのフォルダーや既存のアプリデータフォルダーが採用された場合、Documents 候補には進まない。条件を満たす候補がなければ呼び出し元から渡された既定値を返す。

`STRATA_SETTINGS_FILE` が真の値でアプリ内モードと判定される場合、アプリデータとの同期と Documents 候補の探索を行わない。Terminal の既定候補は `XDG_DOCUMENTS_DIR` と `~/Documents`（Windows では `%USERPROFILE%/Documents`、および設定された OneDrive の Documents）であり、重複パスは一度だけ残す。

### デスクトップアプリの新規モデル保存先

`STRATA_MODELS_DIR` が真の値なら、それを `path.resolve()` したパスが優先され、`STRATA_DOCUMENTS_DIR` は使われない。それ以外ではこの変数を優先し、Windows では値が空の場合に Windows Known Folder の Documents を取得する。Linux では値が空の場合に `XDG_DOCUMENTS_DIR`、次いで `user-dirs.dirs` の値を調べる。Linux 側で `user-dirs.dirs` を読む際は `$HOME` / `${HOME}` を展開し、残る `$` がなく、絶対パスである場合だけ使う。どの方法でも Documents を得られなければ `home/Documents` にフォールバックする。

この Documents 位置は、アプリ起動時に一度計算される既定値である。モデルディレクトリの決定では、保存済み `state.modelsDir` が最優先。次に `STRATA_MODELS_DIR` が未指定なら `STRATA_HOME/models` 以下に既存重みがある場合それを維持する。それ以外で既定 Documents 配下を作成・読み書きできれば採用し、失敗すれば `STRATA_HOME/models` にフォールバックして警告を出す。したがって `STRATA_DOCUMENTS_DIR` を変更しても、保存済み選択や既存ライブラリ、権限エラーが優先される場合がある。

## 実行時の詳細

Python 側では `documents_dirs()` が環境辞書を参照するたびに値を読み、`data_dir_choices()` と `data_dir()` がそれを用いて既存モデルデータを探す。CLI カタログの `data_dir()` はこの関数を呼び出し、モデル一覧などの既存データ位置判定につなぐ。実行中に同じプロセスの `os.environ` を変更すれば後続の Python 読み取りに反映されうるが、親シェル側の環境変更は起動済みプロセスには反映されない。

アプリ側では `defaultModelDirectory()` が `process.env` を参照し、その結果を `store.mjs` のモジュール初期化時に `DEFAULT_MODELS_DIRECTORY` として保持する。アプリ起動後の環境変更では再計算されない。保存済みモデルフォルダーを変更する Settings の操作は別経路で `state.modelsDir` を更新する。

アプリの既定 Documents フォルダーを作成できない場合、`store.mjs` は `Strata could not use ... for models (...), so models go to ...` 形式の警告を stderr の `console.warn` に出し、`STRATA_HOME/models` を選ぶ。

## 根拠

- `strata_control/discovery.py:64-87`: 環境値の取得、OS 別 Documents 候補の追加と重複除去。
- `strata_control/discovery.py:238-286`: 設定値との優先関係、アプリ内モード、候補採用条件と既定値へのフォールバック。
- `strata_control/discovery.py:289-293`: Documents/Strata がデータ候補として認められる条件。
- `strata_cli/launch/catalog.py:470-477`: CLI カタログからデータ位置探索を呼ぶ箇所。
- `apps/host/server/model-directory-default.mjs:7-20`: Node 側の `STRATA_MODELS_DIR` 優先、Documents の値判定、OS 別フォールバックと `Strata/Models` の構成。
- `apps/host/server/store.mjs:60-87`: 既定位置の初期化、保存済みモデルフォルダー・既存ライブラリとの優先関係、失敗時のフォールバックと警告。

`docs/DETAILS.md` にこの環境変数の個別説明は見当たらなかったため、動作の説明は上記の実装に基づく。
