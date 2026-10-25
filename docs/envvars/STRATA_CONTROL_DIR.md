# `STRATA_CONTROL_DIR`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

Strata App Host が使用する Strata Control コンポーネントの候補ディレクトリを指定します。Control はアプリに同梱または更新で配置された Python 実行環境と `strata_control` を含みます。有効な Control が選ばれると、ホストは Control の CLI や Python を使い、モデル・エンジンの状態確認、起動、更新などを行う packaged 経路に入ります。有効な Control が見つからない場合、ホストは従来のソース checkout 用経路を使います。

## 値と判定

| 値 | 扱い |
|---|---|
| 未設定または空文字 | 環境変数で指定した候補は加えません。ホスト隣接の `control` と、見つかった更新済み Control が引き続き候補になります。 |
| 空でないパス | `path.resolve()` で絶対パス化し候補に加えます。相対パスはプロセスの作業ディレクトリを基準に解決されます。 |
| 存在しない、または不完全なディレクトリ | Control 候補として採用されません。エラーにはせず、別候補を調べます。 |

候補を Control として認めるには、対象 platform の bundled Python（Windows: `python/python.exe`、それ以外: `python/bin/python3`）、`strata.py`、`strata_control` の3つが存在する必要があります。`BUNDLE.json` は任意で、読み込みに失敗しても候補の有効性は失われません。バージョン比較には `BUNDLE.json` の `version` を使い、そこになければ更新済み候補のポインタにある `version` を使います。バージョン文字列は `.` で分割し、各要素を10進 `parseInt` して比較します。変換できない要素は `0` として扱われ、文字列全体の厳密な形式検証はありません。

## 有効になる条件

`STRATA_CONTROL_DIR` の候補だけでなく、ホスト隣接の `control` と `STRATA_COMPONENTS_DIR` 等から解決する更新済み Control も候補になります。最も大きい比較バージョンの有効候補が選択され、同じバージョンなら候補順（環境変数、ホスト隣接、更新済み）の先にあるものが残ります。そのため、指定パスが有効でも、より新しいバージョンの別候補があればそちらが使われます。バージョン情報がない候補は比較上 `[0]` です。

Tauri シェルは、リソースディレクトリ内に bundled Python と `strata.py` がある場合、ホスト起動時に `STRATA_CONTROL_DIR` をその `control` ディレクトリに設定します。ホスト側ではさらに `strata_control` の存在も検証します。Tauri 側で同梱 Control が見つからない場合はこの値を上書きしません。

## 実行時の詳細

Node ホストの起動時に `findControl()` が環境変数を読み、結果を `CONTROL` に保持します。このため、ホスト起動後の環境変更は再評価されません。有効な Control が選ばれると `createControl()` と native control がそれを使います。CLI 呼び出しは選択した bundled Python と `strata.py` を使い、作業ディレクトリも Control のディレクトリになります。Control 用の子プロセス環境では `STRATA_CONTROL_DIR` は選択済みディレクトリの絶対パスで上書きされます。

有効候補がない場合、`findControl()` は `null` を返します。ホストは明示的な `STRATA_CONTROL_DIR` エラーを出さず、既存の checkout 用 native control 経路に進みます。環境変数そのものの値をアプリ内ログへ出す処理は確認できません。

## 根拠

- `apps/host/server/control-runtime.mjs:53-75`: 候補順、空値の除外、絶対パス化、必須ファイル、任意の `BUNDLE.json`、バージョン比較。
- `apps/host/server/control-runtime.mjs:77-100,113-119`: 選択した Control の環境変数上書きと子プロセス起動。
- `apps/host/server/index.mjs:119-121,130-145`: 起動時の選択と packaged/checkout 経路の分岐。
- `apps/desktop/src-tauri/src/main.rs:217-235,451-470`: 同梱 Control の検出とホスト起動時の設定。
- `packaging/README.md:82-92`: パッケージ構成とホストが Control を見つける経路の説明。上記の細かな候補選択・検証規則は実装を根拠としています。
