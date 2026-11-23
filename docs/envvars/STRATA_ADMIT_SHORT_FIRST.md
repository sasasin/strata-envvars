# `STRATA_ADMIT_SHORT_FIRST`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

サーバーが batch slot を使う場合に、新規リクエストが engine の control lines を得る順を短い prompt 優先にします。値 `N > 0` のとき、prompt token 数が `N` 以下の新規リクエストを、より長い新規リクエストより先にし、各群では到着順にします。長いリクエストも `STRATA_ADMIT_MAX_WAIT_S` の待ち時間に達すると短い群として扱われます。この設定が変えるのは最初の admission の順序だけで、prompt の内容・読み取る token・生成結果を変更する処理はありません（`terminal/serve/server.py:1912-1922`）。

## 値と判定

サーバーモジュールの import 時に `os.environ.get(...) or 0` を `int` に変換し、`max(0, ...)` で負数を 0 にします。`int` が `ValueError` になる文字列は例外を捕捉して 0 にします。値の先頭・末尾の空白や整数の符号は Python の `int` 変換規則に従い、数値の後ろに余分な文字がある値は全体の変換に失敗します。大文字小文字の真偽値比較はなく、`true` / `false` は整数化に失敗します（`terminal/serve/server.py:447-450`）。

整数化に失敗して無効化された場合に、この変数自身について警告やエラーを出す処理はありません（`terminal/serve/server.py:447-450`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| サーバーの読み込み | `0` | 正の整数（例: `1`, `32`, `+4`, `1_000`）。この値以下の prompt が短い群になる | 空文字は `0`。`0`, `-1` など 0 以下は clamp 後 `0`。`true`, `1.0`, `0anything` など整数に変換できない文字列は捕捉されて `0` |

有効な整数に上限 clamp はありません。正の値でも、実行中の engine が batch slot を報告せず `self.batch == 0` の場合はこの優先制御を通りません（`terminal/serve/server.py:960-966, 2531-2541`）。

## 有効になる条件

- サーバーが `StrataEngine.generate()` から `generate_batched()` を使うこと、つまり engine が実際に 1 個以上の batch slot を報告することが必要です。`--batch` / `--slots` / `--parallel` で指定した数が engine で使えず `batch_slots` が 0 なら、通常の逐次経路となりこの設定は順序を変えません（`terminal/serve/server.py:960-966, 2531-2541`）。
- 値が正の場合、最初の control lines 取得では `new=True` の entry だけを `_admit_next()` で比較します。slot 待ちや譲り返し後に同じリクエストが control lines を取り直す経路は `new` を指定しないため、この変数による優先順位付けの対象外です（`terminal/serve/server.py:1787-1791, 2022-2023, 2041-2044, 2162-2164, 2174-2177`）。
- `STRATA_ADMIT_MAX_WAIT_S` は長い prompt を短い群に昇格させる時間条件です。既定値は 30 秒で、timeout helper は不正な float を既定値に戻し、0 以下を 0 とします。これにより長い prompt が短い prompt 群より永久に後回しにならないようにします（`terminal/serve/server.py:451`; `terminal/serve/server_parts/base.py:260-265`; `terminal/serve/server.py:1912-1922`）。
- この値を別の CLI 引数や設定ファイルから上書きする処理は見つかりません。`--batch` 等は batch 経路を成立させる側の条件であり、この値自体の優先度を上書きしません（`terminal/serve/server.py:960-966, 2531-2541`）。

## 実行時の詳細

`ADMIT_SHORT_FIRST` は `terminal/serve/server.py` のモジュール初期化中に設定される定数です。server プロセス起動後に環境を書き換えても、この値は再読込されません（`terminal/serve/server.py:447-451`）。

batch 経路の各新規生成は prompt 長と到着時刻を待ち行列に登録します。control lines を使える順番の確認と lock 取得後の再確認の両方で、`_admit_next()` が短い群を先にし、その群内では到着時刻が早い entry を選びます。長さは `len(prompt)`、すなわち server が保持する prompt token 列の要素数です。閾値判定は `<=`、待ち時間判定は `>=` です（`terminal/serve/server.py:1787-1795, 1807-1820, 1832-1837, 1912-1922`）。

control lines の lock を得た後の通常処理は同じで、独立した冷 prompt の読み込みを並列化する設定ではありません。batch admission が成立した後は通常どおり `BGEN` / `BGENI` を送り、その後の slot 処理・出力を続けます（`terminal/serve/server.py:1978-1986, 2183-2209`）。通常サーバーの逐次経路は `generate_batched()` を呼びません（`terminal/serve/server.py:2531-2544`）。

## 根拠

- `terminal/serve/server.py:443-451` — 設定値の読み取り・変換・不正値 fallback、および待ち時間設定。
- `terminal/serve/server.py:960-966, 2531-2541` — 実際の batch slot 数と batch / 逐次経路の切替。
- `terminal/serve/server.py:1787-1855, 1912-1922` — 待ち entry、control lock、優先順位、到着順と待ち時間昇格。
- `terminal/serve/server.py:1978-1986, 2022-2027, 2183-2209` — batch 生成処理と新規 admission の入口。
- `terminal/serve/server_parts/base.py:260-265` — `STRATA_ADMIT_MAX_WAIT_S` の float 変換、fallback、非正値処理。
- `docs/BATCHING.md:125` — 値が新規 prompt の admission 順を変え、待ち時間後に長い prompt を短い群として扱うという説明。現行ソースの挙動と一致。
