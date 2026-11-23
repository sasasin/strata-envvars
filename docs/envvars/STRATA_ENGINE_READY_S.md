# `STRATA_ENGINE_READY_S`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の Python サーバーがエンジン子プロセスから `READY` 行を受け取るまでの待ち時間を制限する。既定は 900 秒で、0 以下を指定すると待ち時間の上限をなくす。上限に達するとサーバーは子プロセスを kill し、起動失敗として扱う。エンジンの計算設定や READY 行の生成方法を変える変数ではない。参照はサーバーの `terminal/serve/server.py` にあり、エンジン側のソースにはこの名前の読み取り箇所がない（全参照検索結果はサーバーコードと記録資料）。`terminal/serve/server.py:827-840, 841-864, 867-879`

## 値と判定

`terminal/serve/server_parts/base.py` の `_timeout_env` が `os.environ.get(name, default)` を `float` に変換する。`ValueError` の場合は既定値に戻し、変換値が `<= 0` なら `None`（上限なし）にする。文字列全体を浮動小数点数として変換するため、`1anything` や `true` は無効で既定値に戻る。Python の `float` が受け付ける前後空白は許容される。空文字は `ValueError` となる。有限値かどうかの追加検査はない。`base.py:260-265`; `server.py:456`

| 環境変数の値 | サーバー側の結果 |
|---|---|
| 未設定 | 900 秒 |
| 空文字、`true`、`0anything` など数値変換できない文字列 | 900 秒に fallback |
| `1`、`900`、` 1 ` | それぞれ指定秒数の上限 |
| `0`、`-1` | `None` となり無期限待ち |
| `nan`、`inf` | `float` 変換と `<= 0` 判定を通過する。有限値検査はないため、これらの期限値での実行時挙動はコードから安全に特定できない |

起動時に `engine_ready_s` がサーバー設定 JSON に存在し、値が `None` でなければ、設定値が環境変数から得た値を置き換える。この設定値は bool 以外の int/float で、0 より大きい場合だけ受理される。0、負数、文字列、bool は設定エラーとなり、`[strata] config ...` を付けてサーバーを終了する。設定値には有限性チェックもない。`server.py:3456-3465, 8935-8939`

## 有効になる条件

- `terminal/serve/server.py` の Strata 実エンジン起動経路で使われる。`--engine strata` は `--config` を必要とし、初期化後に `apply_ready_timeout(cfg)` を呼ぶ。`server.py:8641-8644, 8870-8873, 8935-8961`
- `--engine mock` には Strata エンジンの READY 待ちがなく、この変数による制御はない。Strata エンジンの起動ロジックは `StrataEngine` で行われる。`server.py:827-840`
- 設定 JSON に `engine_ready_s` があれば、正の数値である限りその値が環境変数より優先される。専用の CLI timeout 引数は見当たらない。`server.py:3456-3465, 8641-8644`
- OS、CUDA/HIP/SYCL backend、GPU 世代、モデル状態による別の値判定はない。どの設定でも READY 行を受信した時点で待機を終える。`server.py:841-864`

## 実行時の詳細

環境変数は `server.py` のモジュール読み込み時に一度 `ENGINE_READY_S` として評価される。サーバー起動時には設定の `engine_ready_s` を適用し、その後のエンジン開始ごとに `time.monotonic()` から deadline を計算する。READY 待ちでは別スレッドが標準出力行をキューへ渡し、期限が来る前に `READY` で始まる行を受信すると `max_context` と対応能力を設定して成功する。`server_parts/base.py:260-265`; `server.py:456, 839-864, 8935-8939`

期限は起動ごとに計算されるが、環境変数自体を起動ごと・リクエストごとに再読込する処理はない。プロセス起動後に環境を書き換えても反映されない。設定値もサーバー起動時に適用され、そのサーバープロセスが後で再起動するエンジンに同じ値を使う。`server.py:841-849, 8935-8961`

## ログと測定値

timeout すると `timed_out` となり、まだ READY を報告していない子プロセスに `kill()` を試みる。失敗理由は `the engine did not report READY within {秒} s` で、`EngineDied` として起動時の失敗経路へ渡される。timeout でない早期終了は別理由 `the engine exited before it was ready` となる。timeout 時は終了コード由来の `start_exit_note` を付けないが、ログがあれば `start_log_tail` の内容を失敗理由に連結する。`server.py:841-849, 865-879, 923-933`

この環境変数について、条件付き性能測定値は該当しない。索引に関連する bench 記録は設定値 `0` を記録しているだけで、挙動や性能の根拠にはしていない。

## 根拠

- `terminal/serve/server_parts/base.py:260-265` — 環境値の取得、float 変換、無効文字列の fallback、0 以下を無期限にする処理。
- `terminal/serve/server.py:433-456` — READY timeout 群の説明と既定値 900 秒。
- `terminal/serve/server.py:827-864` — エンジン子プロセス起動、期限作成、READY 行待ち。
- `terminal/serve/server.py:865-933` — timeout 時の kill、再試行条件、失敗理由と `EngineDied`。
- `terminal/serve/server.py:3456-3465, 8935-8939` — JSON 設定による上書きと値検証。
