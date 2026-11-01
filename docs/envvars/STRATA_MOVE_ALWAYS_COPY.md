# `STRATA_MOVE_ALWAYS_COPY`

調査対象: Strata `main` の HEAD `b478c6cc8764fe4451886652b2a8a565e751873f`（2026-11-01 時点）。

## 役割

モデル格納先を移動する Python 実装の同一ボリューム判定を上書きします。値が文字列 `1` と完全一致すると、実際には同じボリューム上でも `same_drive()` は `False` を返し、モデル移動は rename 経路ではなくコピー経路になります。モジュールの説明ではこの設定は「同じディスク上でコピー経路を試す」ためのものです。読み取りは `strata_control/models_move.py` にあり、モデル移動処理で使われます（`strata_control/models_move.py:1-12,104-111`）。

## 値と判定

`os.environ.get("STRATA_MOVE_ALWAYS_COPY") == "1"` で文字列全体を比較します。数値変換、空白除去、大文字小文字変換はありません。

| 環境値 | `same_drive()` の結果 | 意味 |
|---|---:|---|
| 未設定 | 実際のボリューム判定へ進む | `_near()` で得た既存パス同士の `st_dev` を比較 |
| 空文字 | 実際のボリューム判定へ進む | コピー強制にはならない |
| `1` | `False` | コピー経路を強制 |
| その他（例: `0`, `true`, `01`, `1 `） | 実際のボリューム判定へ進む | コピー強制にはならない |

環境値が `1` 以外の場合、または未設定の場合に `os.stat()` が `OSError` になれば、同関数は `False` を返します。この場合も呼び出し側ではコピー側の扱いになりますが、環境変数による強制とは別の fallback です（`strata_control/models_move.py:96-111`）。

## 有効になる条件

- `strata models move NEW` の計画・実行では、`plan()` が `same_drive()` を呼びます。`--plan` の結果にも、実移動にも反映されます（`strata_cli/cli.py:617-634,648`、`strata_control/models_move.py:137-184,379-401`）。
- 移動をコピー扱いにすると、計画はファイル合計の `int(total * 1.05)` バイトを必要容量として見積もります。同一ボリューム扱いなら必要容量は 0 です。コピー扱いで空き容量が足りないと、実移動は `MoveError("disk_full", ...)` で始まりません（`strata_control/models_move.py:31,170-180,391-394`）。
- コピー扱いの移動では通常、各ファイルを `.part` に書き、サイズと SHA-256 を確認して配置し、その後に元ファイルを削除します。同じ inode のハードリンクを検出した場合は `os.link()` を試し、失敗時に検証付きコピーへ fallback します。同一ボリューム扱いの経路は `os.replace()` による移動です（`strata_control/models_move.py:223-258,441-500`）。
- `strata models move --resume` は通常の `move()` に戻るため、再開時点の環境値で判定し直します（`strata_cli/cli.py:668-705`）。`--leave` による中断移動の後始末でも、元側に戻すファイルごとに `same_drive()` を呼びます。`1` なら復元もコピー経路になります（`strata_control/models_move.py:534-565`）。
- 既存データフォルダーと移動先が同一パスの場合や、片方が他方の内側の場合など、計画がそれ以前の検査で拒否される経路では同変数を使った移動判定に到達しません（`strata_control/models_move.py:156-170`）。

この判定に CLI オプションや他の環境変数との値の優先順位はありません。移動元・移動先などの CLI 指定は別途パスを選びます。なお、通常の `same_drive()` でも `st_dev` が異なればコピー経路です。環境変数が追加で強制するのは、通常なら同一ボリューム判定になるケースです。

## 実行時の詳細

読み取りはモジュール import 時ではなく、`same_drive()` が呼ばれた時に `os.environ.get()` で行われます。結果の `static` キャッシュ等はありません。`plan()` と `move()` では `move()` が呼ぶ `plan()` の結果を実際のファイル処理に使います。したがって、計画と後続の実移動でプロセス環境が変更されれば、それぞれの呼び出しで異なる結果になり得ます。`leave()` は対象ファイルの処理中に判定関数を呼ぶため、判定はファイルごとです（`strata_control/models_move.py:104-111,170,388-401,558-562`）。

この設定自体はログや警告を出しません。CLI の JSON/JSONL の計画結果・最終結果に `same_drive` が含まれ、強制時は `false` になります。JSONL では進捗イベントにも同値が含まれます。空き容量不足などの `MoveError` は JSON では `error`、通常出力では `strata: ...` と stderr に出て終了コード 5 になります。コピー経路の I/O・検証エラーも `MoveError` として CLI に返されます（`strata_control/models_move.py:140-149,423,510-511,241-255`、`strata_cli/cli.py:627-659`）。

## 根拠

- 候補一覧には `STRATA_MOVE_ALWAYS_COPY` が掲載されています（`docs/envvars/000_envvers.md:1107`）。実際の環境読み取りは `strata_control/models_move.py:104-111` の一箇所です。行 105 の説明コメントだけでなく、行 106 の `os.environ.get()` が読み取りを裏付けます。
- 計画上の空き容量見積もり: `strata_control/models_move.py:170-180`。
- rename/copy の分岐とコピー後の元ファイル削除: `strata_control/models_move.py:441-500`。
- 中断移動の復元経路: `strata_control/models_move.py:534-565`。
- CLI からの計画、実行、再開・後始末、および結果の表示: `strata_cli/cli.py:617-660,668-705`。
- 関連資料は `docs/release-notes-0.2.2.md:15`。同一ドライブでは rename、別ドライブでは検証付きコピーを行うという記述が実装と一致します。同資料はこの環境変数自体の値判定を説明していないため、値の規則は現行ソースに基づいています。
