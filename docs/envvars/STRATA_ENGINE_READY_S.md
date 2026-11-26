# `STRATA_ENGINE_READY_S`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（2026-11-26 時点、未コミット変更なし）。

## 役割

`strata serve`（Python サーバー）がエンジンを別プロセスで起動してから `READY` 行を受け取るまでの「無反応の許容時間」を秒で決める。既定は 900 秒で、ログが 1 行も増えずディスク読み取りも進まないままこの時間が過ぎると、サーバーはそのエンジンを終了させる。エンジンが動き続けて READY を返す限り、読み込むモデル、量子化、backend、生成結果は変わらない（値は待ち時間の上限だけ）。

実装は `terminal/serve/server.py` のモジュール定数 `ENGINE_READY_S`（`server.py:463`）、起動待ちを行う `StrataEngine.__init__`（`server.py:891-900, 974-989`）、期限計算の `ReadyDeadline`（`server.py:472-505`）。環境から読む箇所は `server.py:463` のみで、エンジン側の C++/CUDA/HIP/SYCL ソースは読まない。

## 値と判定

読み取りは共通 helper `_timeout_env`（`terminal/serve/server_parts/base.py:272-277`）で、`float(os.environ.get(name, default))` により**文字列全体を数値として parse** する。`float()` が失敗（`ValueError`）すれば既定値 900.0 に戻り、`v <= 0` なら `None`（期限なし）を返す。つまり設定の有無ではなく数値の符号で判定され、ブール文字列は受け付けない。

| 設定値 | 結果 | 理由 |
|---|---|---|
| 未設定 | 900.0 秒 | 既定値 |
| `""`（空文字） | 900.0 秒 | `float("")` が ValueError → 既定（無制限ではない） |
| `"600"` | 600.0 秒 | 数値として parse |
| `"12.5"` / `"1e3"` / `" 45 "` | 12.5 / 1000.0 / 45.0 | 小数・指数・前後空白は `float()` が許す |
| `"0"` | `None`（期限なし） | `0 <= 0` |
| `"-5"` | `None`（期限なし） | 負値も `<= 0` |
| `"abc"`・`"15m"`・`"true"`・`"yes"` | 900.0 秒 | ValueError → 既定。大小文字の解釈は無い |
| `"inf"` / `"nan"` | そのまま保持 | `float()` が通り `nan` は `<= 0` が偽。非有限値は弾いていない |

無効値を警告する行は無く、黙って既定に戻る（`base.py:273-276`）。

優先順位は「環境変数 < 実行 config の `engine_ready_s`」。起動時に `apply_ready_timeout(cfg)` が一度だけ呼ばれ（`server.py:9636`）、config に数値があれば global の `ENGINE_READY_S` を上書きする（`server.py:3656-3665`）。config 側は `int`/`float` かつ `> 0` のみ受け付け、`bool`・文字列・`0`・負値は `ValueError` となり `[strata] config ...` を出して起動が止まる（`server.py:3663-3664, 9637-9638`）。したがって**0 = 無期限を書けるのは環境変数だけ**で、`docs/DETAILS.md:1555` の「config に `0`」という案内はコードと食い違う。

## 有効になる条件

- `strata serve` のエンジン起動経路のみ。エンジンや他の同梱ツールを単体で起動しても、この値を読むコードは無い。
- 期限が働くのは起動中に READY が来ない場合だけ。READY 前にプロセスが終了した場合は `server.py:974-975` の "the engine exited before it was ready" 経路で、この時間は使われない。
- 無反応の兆候を検出できること: ログファイル（config の `log`、無ければ `None`）のサイズと、`psutil` が読む読み取りバイト数（`server.py:1240-1254`）。ログ無しで `psutil` も無い環境では兆候が常に `(0, 0)` になり、期限は延長されない。
- 値が `None`（`0` か負値）のときは期限も全体上限も作らず、READY まで無期限に待つ（`server.py:891-892`）。
- 実行 config の `"env"` にこの名前を書いても効かない。その map はエンジン子プロセスの環境に足されるだけで（`server.py:4110, 4127-4128`）、サーバー自身の `os.environ` は変わらない。
- replicas / split 構成でも各エンジンは同じ `StrataEngine` 起動なので、同じ窓が適用される（`server.py:9001-9002, 9069-9072`）。
- 起動後の無反応は別の変数 `STRATA_ENGINE_STALL_S`（既定 90 秒）の担当で、この変数とは独立（`server.py:443-449`）。

## 実行時の詳細

- 値はモジュール import 時に一度だけ読まれ、定数 `ENGINE_READY_S` に入る（`server.py:463`）。サーバー起動後に環境を書き換えても反映されない。
- エンジン起動ごとに `ready_window = ENGINE_READY_S` を読み直し（`server.py:891`）、`ReadyDeadline(window, self._ready_signs)` を作る（`server.py:892`）。`deadline = 開始 + window`、`hard = 開始 + max(7200, 4 × window)`（`server.py:477-482`、全体上限 `READY_CEILING_S = 7200.0` は `server.py:468`）。
- 待ちループは最大 `READY_POLL_S = 5.0` 秒おきに目を覚まして兆候を調べ（`server.py:469, 897-900`）、ログサイズか読み取りバイト数が増えていれば `deadline = min(now + window, hard)` へ前進させる（`server.py:492-502`）。`READY` 行で `max_context` と `stop`/`hold` 機能を設定して抜ける（`server.py:909-915`）。
- 期限切れでは `proc.kill()` して 5 秒待ち、`EngineDied` を送出する（`server.py:918-930, 988-989`）。起動待ちだったリクエストは 503 で終わる（`server.py:981-982`）。
- 期限切れは `transient_start_failure` による自動再試行の対象外（`server.py:931` の `if not timed_out and ...`）。`STRATA_START_RETRIES` を増やしても READY 待ちの timeout は再試行されない。
- lazy 起動、`/unload` 後の再ロード、異常終了後の `restart()` も `__init__` を通るため、起動のたびに同じ窓が新しく作られる（`server.py:1287, 5096`）。
- ターミナルやアプリからの起動では、自身の起動待ちが 600 秒を超えると config に `engine_ready_s` を書き足す（`terminal/strata_cli/launch/runner.py:2231-2233`、`app/host/server/native-control.mjs:644`）。その config 値は環境変数より優先されるので、大きなモデルの自動起動では環境変数の値が上書きされ得る。

## ログと測定値

- 値そのものは起動時に表示されない。成功時の起動行は "loading the model (the first start takes a minute or two) ..."（`server.py:9607-9608`）。
- 期限切れの文言は実装どおり `the engine did not report READY within 900 s`（既定時）。兆候で期限が延びた場合は ` of its last sign of life (it ran 1234 s in all)` が続き、さらに `; "engine_ready_s" in the run config (seconds, 0 = no limit) or STRATA_ENGINE_READY_S sets how long a start may stay without a sign of life`、` (see <log>)`、ログ末尾が付く（`server.py:974-989`）。
- `docs/DETAILS.md:555` の説明（兆候のたびに 1 周期延びる、全体は 2 時間または 4 周期の長い方）はコードと一致する。同ファイル 1555 行の「config に `0`」だけが食い違う。

## 根拠

- `terminal/serve/server.py:463`（読み取りと既定 900）、`:464-469`（#7060 の意味、`READY_CEILING_S` / `READY_POLL_S`）
- `terminal/serve/server_parts/base.py:272-277`（`_timeout_env` の parse と `<= 0` の扱い）
- `terminal/serve/server.py:472-505`（`ReadyDeadline` の期限と延長）、`:891-915`（起動待ちループ）、`:918-989`（timeout 時の kill・503・文言）
- `terminal/serve/server.py:1240-1254`（兆候の取得）、`:3656-3665`（config の上書き）、`:9634-9638`（起動時の適用）
- `terminal/serve/server.py:4110, 4127-4128`（config の `"env"` は子プロセス向け）
- `terminal/strata_cli/launch/runner.py:2231-2233`、`app/host/server/native-control.mjs:644`（config へ書き足す側）
- `docs/DETAILS.md:555, 1555`
