# `STRATA_STATE_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`STRATA_STATE_DIR` は通常のアプリ状態ディレクトリを選ぶ設定としては読み取られていません。Windows のアクセス権修復処理が「ユーザー自身のデータ領域」とみなす場所の候補に追加されます。具体的には、対象パスがユーザー領域内か判定する処理と、既知のユーザーデータ領域を走査してアクセス権を修復する処理の両方で参照されます（`strata_control/private_files.py:418-442,509-540`）。

## 値と判定

| 状態 | 判定・処理 |
|---|---|
| 未設定 | `os.environ.get()` は `None` を返し、候補へ追加されません。 |
| 空文字 | 偽値として扱われ、候補へ追加されません。 |
| 空でない文字列 | 数値変換や形式検査をせず `Path(value)` として扱います。空白だけの値も候補になります。 |
| 不正なパス・利用できないパス | `user_roots()` は `resolve()` が `OSError` を起こした候補を除外します。`known_roots()` は存在するかを検査し、存在しない候補を除外します。 |

`user_roots()` では値を `Path` 化し、後で各候補を `resolve()` します。`known_roots()` では値をそのまま `Path` 化し、存在確認後に走査対象へ加えます。`known_roots()` で他の候補と文字列（小文字化後）が重複する場合は、先に現れた候補を残します。どちらの関数にも `STRATA_STATE_DIR` 専用の優先順位や fallback はなく、他のデータ領域候補と併用されます（`strata_control/private_files.py:421-433,512-527`）。

## 有効になる条件

- `repair_access()` は `WINDOWS` が真の場合だけユーザー領域判定へ進みます。したがって `STRATA_STATE_DIR` が設定されていても、Windows 以外では、この修復経路で対象パスの許可判定に使われません（`strata_control/private_files.py:14,445-454`）。
- 既知の領域を走査する `repair_known_roots()` は Windows 以外では空の件数レポートを返し、`known_roots()` を呼びません（`strata_control/private_files.py:530-540`）。
- CLI の `repair-access` は `repair_known_roots()` を呼びます。CLI 実行中にアクセス拒否で再試行する場合も、共有違反でなければ修復走査後にコマンドを一度再実行します（`strata_cli/cli.py:2085-2104,2107-2116`）。
- これは修復処理の候補ディレクトリ指定です。通常のアプリ設定や他の CLI 引数による状態ディレクトリ選択との優先順位は、この変数の読み取り箇所には実装されていません。

## 実行時の詳細

環境変数はモジュール import 時にキャッシュされません。`user_roots()` または `known_roots()` が呼ばれるたびに `os.environ.get("STRATA_STATE_DIR")` を評価するため、呼び出し間にプロセス環境が変更されれば次の呼び出しで新しい値を読みます（`strata_control/private_files.py:418-425,509-520`）。

`user_roots()` の候補は `APPDATA`、`LOCALAPPDATA`、`STRATA_HOME`、`STRATA_PROFILE_DIR`、`STRATA_INSTALL_DIR`、`STRATA_RUNTIME_DIR`、`STRATA_STATE_DIR`、`Path.home()` の順です。`repair_access()` は入力パスと各候補を解決した上で、入力が候補そのものまたはその配下にある場合だけ、Windows のアクセス権修復を試します。対象が候補外なら `False` を返し、修復しません（`strata_control/private_files.py:418-442,445-476`）。

`known_roots()` は `APPDATA/Strata`、`LOCALAPPDATA/Strata`、`~/.strata` に加えて、`STRATA_HOME`、`STRATA_PROFILE_DIR`、`STRATA_RUNTIME_DIR`、`STRATA_STATE_DIR`、`STRATA_INSTALL_DIR` の各設定値を候補にします。存在確認は `Path.exists()` であり、ディレクトリかどうかの検査はありません。したがって既存のファイルなども候補になり得ますが、`os.scandir()` が `OSError` になればその候補は走査されず、件数レポートにも失敗として加算されません。走査は既定で合計 20,000 件までです。シンボリックリンク、指定されたディレクトリ名、特定の拡張子はスキップし、アクセスできないファイル・フォルダーには `repair_access()` を試します（`strata_control/private_files.py:505-527,530-579`）。

CLI の `repair-access` は人間向け出力で `checked … entries, repaired …, could not repair …` を表示し、失敗があれば `ACCESS_MESSAGE` も表示して終了コード 5 を返します。JSON 出力では `ok` と件数を出し、同じく失敗時に終了コード 5 です（`strata_cli/cli.py:2107-2116`）。コマンド中のアクセス拒否への自動再試行が修復後も失敗した場合は、エラー文を出して終了コード 5 を返します（`strata_cli/cli.py:2092-2104`）。

## 根拠

- 全参照と環境値読み取り: `strata_control/private_files.py:421-425,517-520`。両方とも環境変数名をキー列挙し、`os.environ.get(key)` で取得します。
- 値をユーザー所有領域の判定に使う経路: `strata_control/private_files.py:418-476`。
- 値を修復対象ディレクトリの候補に加える経路: `strata_control/private_files.py:509-579`。
- CLI からの手動・自動修復呼び出しと観測可能な結果: `strata_cli/cli.py:2085-2116`。
