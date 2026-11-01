# `STRATA_MOVE_ALWAYS_COPY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

`strata models move` とデスクトップアプリが共有するモデルファイル移動処理で、移動元と移動先が同じボリュームでもコピー経路を強制します。主な用途は、同一ボリューム上でコピー処理を試すことです。通常、同じボリュームならファイルを rename（`os.replace`）し、別ボリュームならコピー・検証後に元ファイルを削除します。環境変数を有効にすると、同じボリュームの場合も後者の経路を使います。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | `os.environ.get()` は `None`。環境変数による強制はなく、`os.stat(...).st_dev` で同一ボリュームかを判定する |
| 空文字 | `"1"` と一致しないため強制しない |
| 文字列 `1` | 同一ボリューム判定を `False` にする |
| その他（例: `0`, `true`, `01`, ` 1`） | `"1"` と完全一致しないため強制しない |

数値変換や前後空白の除去、大文字小文字の正規化はありません。値が `"1"` でも、移動元と移動先が別ボリュームなら判定結果は元から `False` なので、移動処理上の経路は変わりません。`same_drive()` は呼び出されるたびに環境を参照し、値を static/global cache しません。

## 有効になる条件

- `strata models move --plan` では `plan()` が同一ボリューム判定を行い、結果の `same_drive` と必要空き容量に反映します。同一ボリューム扱いなら必要容量は 0 ですが、この変数でコピーを強制すると `int(total * 1.05)` が必要になります。
- 通常の `strata models move` は `move()` 内で `plan()` を呼んでから、その結果に応じて rename またはコピーを選びます。CLI 引数にこの判定を上書きするものはありません。
- 中断した移動の `--leave` 処理では、コピー先にしかないファイルを元フォルダーへ戻す際にも `same_drive()` を呼びます。この変数が `1` なら同一ボリュームでも検証付きコピー後にコピー先を削除します。`--status` は移動状態を読むだけで、この判定を使いません。
- 判定は Python プロセスの環境を読むため、そのプロセスに環境変数が渡っている場合に適用されます。ソース上に OS、backend、build macro、モデル形式による追加条件はありません。

## 実行時の詳細

`same_drive(a, b)` は最初に `os.environ.get("STRATA_MOVE_ALWAYS_COPY") == "1"` を調べ、一致すれば `False` を返します。それ以外は `_near()` で各パスの存在する親を探し、`os.stat(...).st_dev` を比較します。stat が `OSError` になった場合も `False` を返すため、コピー経路になります（`strata_control/models_move.py:96-111`）。この関数は計画時に呼ばれ、`move()` は計画結果の値をその実行中に使います。環境値を再評価するのは別の `same_drive()` 呼び出し時です（同: `170`, `379-423`）。

強制されたコピー経路では、移動先に一時 `.part` ファイルを作り、サイズと SHA-256 を照合し、存在すれば元ファイルの `.done` にある固定 SHA-256 とも比較してから `os.replace()` で配置します。その後に元ファイルを削除します。共有 inode のファイルは可能なら hard link を使う特例があります（同: `223-258`, `451-500`）。

`--plan` の結果は通常出力または JSON に現れます。移動実行では JSONL の progress event に `same_drive: false` が含まれます。環境変数専用のログや警告はありません。容量不足は `MoveError("disk_full", ...)`、コピー照合不一致は `MoveError("verify", ...)`、I/O 失敗は `MoveError("io", ...)` となり、CLI は失敗 JSON または stderr の `strata: ...` を出して終了コード 5 を返します。コピー検証で失敗した場合は `.part` を削除し、元ファイルはその経路では削除しません（同: `223-258`, `388-394`, `491-500`; `strata_cli/cli.py:627-660`）。

## 根拠

- `strata_control/models_move.py:104-111` — 値の完全一致判定、未設定時のボリューム比較、stat 失敗時の fallback。
- `strata_control/models_move.py:166-180` — 判定結果と必要空き容量の関係。
- `strata_control/models_move.py:223-258` — コピー、サイズ・SHA-256 検証、`.part` cleanup と失敗分類。
- `strata_control/models_move.py:379-423,441-511` — 計画結果に基づく移動経路、進捗値、コピー後の元ファイル削除。
- `strata_control/models_move.py:534-565` — `--leave` での復元経路。
- `strata_cli/cli.py:617-660,668-705` — CLI の plan / move / resume / leave 呼び出しと観測可能な終了・出力。
- `strata_control/models_move.py:1-11` — デスクトップアプリと Terminal が共有する移動処理であること。
