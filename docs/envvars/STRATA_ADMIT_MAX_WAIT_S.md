# `STRATA_ADMIT_MAX_WAIT_S`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この変数は、サーバーが初回の prompt admission の順番を短い prompt 優先にするとき、長い prompt も待機時間が指定秒数に達すれば短い側として扱う閾値です。単独では順番を変えず、生成内容や prompt の読み取り方も変えません。対象実装は `terminal/serve/server.py` の `StrataEngine._admit_next` です（`terminal/serve/server.py:443-451,1912-1922`）。

## 値と判定

サーバー起動時に `_timeout_env` が `os.environ.get(name, default)` の値を `float` に変換します。未設定なら `30.0`、空文字または数値に変換できない文字列なら `ValueError` を捕捉して `30.0` に戻ります。変換後の値が `<= 0` なら helper は `None` を返し、呼び出し側の `or 0.0` により `0.0` になります。正の値はそのまま使われ、範囲制限や丸めはありません（`terminal/serve/server_parts/base.py:260-265`; `terminal/serve/server.py:451`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| すべての OS（Python サーバー） | `30.0` 秒 | `float` が受理する正の有限値。例: `0.1`, `30`, ` 2.5 ` | `0`, `-1`, `-inf` は `0.0` 扱い。空文字、`true`、`0anything`、`1s` は変換失敗して既定値 `30.0` |

大文字小文字や空白の独自判定はなく、Python の `float` 変換に従います。前後の空白は数値文字列として受理されます。`nan` も変換自体は成功し、`nan <= 0` は偽なので `nan` のまま残ります。`inf` は正の値として残ります。どちらにも clamp や警告はありません。`nan` と `inf` は経過時間との `>=` 比較が成立しないため、長い prompt が待機時間だけを理由に短い側へ昇格しません（`terminal/serve/server_parts/base.py:260-265`; `terminal/serve/server.py:1921-1922`）。

## 有効になる条件

- `STRATA_ADMIT_SHORT_FIRST` が正の整数として有効である必要があります。同変数が未設定、空文字、`0`、負数、整数に変換できない文字列の場合は `ADMIT_SHORT_FIRST` が `0` となり、admission 順序の制御自体が無効です。この場合、この変数の値も使われません（`terminal/serve/server.py:443-451,1809-1815`）。
- Strata engine が実行時に batch slot を 1 個以上報告し、`generate` から `generate_batched` に入る必要があります。mock engine と、実効 batch slot がない Strata engine ではこの判定経路を通りません（`terminal/serve/server.py:2531-2541`; `terminal/serve/server.py:960-975`）。
- 並べ替えの対象は `_take_control(..., new=True)` で登録される初回 admission です。slot 内での後続処理や、譲った control line を再取得する待機は対象外です（`terminal/serve/server.py:1787-1795,2022-2024,2041-2046`）。
- `--queue-timeout` / `queue_timeout` が設定されている場合は、初回 engine turn を待つ別の期限が適用されます。期限切れは `QueueWaitExpired` になり、`STRATA_ADMIT_MAX_WAIT_S` はその期限を延長・上書きしません（`terminal/serve/server.py:8667-8670,5689-5692,1800-1801`）。

## 実行時の詳細

サーバーのモジュール初期化時に定数 `ADMIT_MAX_WAIT_S` として読み取られ、そのプロセスの間 cache されます。リクエストごとの再読込はないため、実行中に環境を変更しても反映されず、値を変えるにはサーバーを再起動します（`terminal/serve/server.py:451`; helper は `terminal/serve/server_parts/base.py:260-265`）。CLI 引数による直接の上書きはありません。

複数の初回 admission が control line を待つと、サーバーは到着時刻と prompt token 数を待機リストへ登録します。`STRATA_ADMIT_SHORT_FIRST=N` が有効な場合、prompt が `N` token 以下か、到着からこの閾値以上待った request を「短い側」として先に選びます。両条件に当てはまる request の間は到着順です。したがって既定の `30` 秒は長い prompt が短い prompt に追い越され続けるのを抑えます。値が `0.0` の場合、経過時間は常に `>= 0.0` となるため、待機中の全 request が短い側になり、実質的に到着順で選ばれます。順番が変わるだけで、engine が読む prompt や生成する token は変更されません（`terminal/serve/server.py:1791-1795,1912-1922`）。

## ログと測定値

この変数の値の採用・無効値への fallback・待機時間による昇格について、専用のログや警告はありません。数値変換できない値も既定値に戻るだけです（`terminal/serve/server_parts/base.py:260-265`; `terminal/serve/server.py:451,1921-1922`）。

## 根拠

- `terminal/serve/server_parts/base.py:260-265` — env helper の取得、`float` 変換、無効文字列の fallback、非正値の扱い。
- `terminal/serve/server.py:443-451` — `STRATA_ADMIT_SHORT_FIRST` と対象変数の module-level 設定。
- `terminal/serve/server.py:1787-1815` — 初回 admission の待機登録と順番判定。
- `terminal/serve/server.py:1912-1922` — 待機時間と prompt 長による選択規則。
- `terminal/serve/server.py:2531-2541` — 有効 batch slot がある場合の batched 経路。
- `terminal/serve/server.py:5689-5692` — 別設定である queue timeout の期限設定。
