# `STRATA_NO_FAULTHANDLER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HTTP サーバープロセス起動時に Strata が呼び出す `arm_faulthandler()` の処理を止めるスイッチ。値が文字列 `1` の場合は `faulthandler.enable()` を呼ばず、それ以外の場合は CPython の `faulthandler` を import して `enable(all_threads=True)` を試みる。呼び出し箇所は `serve.server.main()` の起動直後で、エンジンや GPU backend の選択、CLI 引数には依存しない（`terminal/serve/server.py:8472-8483`、`terminal/serve/server_parts/http_api.py:846-870`）。

この設定はサーバープロセス自身の初期化だけに関係する。別プロセスの `strata-runtime-host` は `terminal/strata_control/runtime.py:1650-1656` で独立して `faulthandler.enable(all_threads=True)` を呼び、この環境変数を参照しない。

## 値と判定

`arm_faulthandler()` は実行時の環境マッピングから値を取得し、文字列 `"1"` と完全一致する場合だけ無効化する。真偽値変換・数値変換・空白除去・大文字小文字変換は行わない。通常の起動経路では引数 `env` を渡さず `os.environ` を参照する（`terminal/serve/server_parts/http_api.py:850-866`）。

| 条件（build など） | unset | 有効になる値（faulthandler の有効化を試行） | 無効になる値（有効化を行わない） |
|---|---|---|---|
| `serve.server.main()` の全起動経路 | `None` のため有効化を試行 | `""`、`"0"`、`"true"`、`"True"`、`" 1"`、`"1 "`、その他すべての文字列 | `"1"` のみ |

「有効」は有効化を試みることを指す。`faulthandler` の import または `enable()` が例外になると有効化できず、その例外は捕捉される。境界値・無効文字列の検査や別値への fallback はない（`terminal/serve/server_parts/http_api.py:864-872`）。

## 有効になる条件

- `STRATA_NO_FAULTHANDLER` が設定されていないか、その値が文字列 `"1"` と一致しないこと。
- そのプロセスで `serve.server.main()` が実行されること。サーバーの起動時に一度判定し、`--engine` などの CLI 引数やモデル状態では分岐しない（`terminal/serve/server.py:8472-8483`）。
- CPython の `faulthandler` import と `enable(all_threads=True)` が例外なく完了すること。失敗時は有効化されないが、例外は握りつぶされてサーバー起動を止めない（`terminal/serve/server_parts/http_api.py:867-872`）。

OS、backend、build macro、サーバーモード別の値判定はない。この変数は `strata-runtime-host` 側の独立した有効化には影響しない（`terminal/strata_control/runtime.py:1650-1656`）。

## 実行時の詳細

`serve.server.main()` は子プロセス向けの crash 環境を整え、メモリー arena を制限した後、activity lease や `_main()` の処理より前に `arm_faulthandler()` を一度呼ぶ（`terminal/serve/server.py:8472-8495`）。判定結果は static cache されず、その関数の呼び出し時に環境マッピングから読み取る。通常のサーバー経路では起動時の一度だけ読むため、起動後に環境値を変更してもそのプロセスで再評価されない。CLI 引数・設定ファイルとの優先順位はなく、両者からこのスイッチを上書きする処理もない。

値が `"1"` なら関数は `False` を返して終了し、その他の値では import と有効化を試す。例外時も `False` を返すだけで、`main()` は返り値を使って分岐せず処理を続ける。したがって、この失敗経路による Strata の警告、終了、再試行はない（`terminal/serve/server_parts/http_api.py:864-872`、`terminal/serve/server.py:8480-8495`）。

## ログと測定値

Strata は有効化の成功・失敗や無効化についてログを出さない。設定値 `"1"` は関数内で無言で終了し、import または `enable()` の例外も捕捉される。ソースの説明では、この仕組みは実行中には何も書かず、クラッシュ時のスタックをサーバー自身の出力へ残す意図とされている。性能測定値は該当しない（`terminal/serve/server_parts/http_api.py:850-872`、`terminal/serve/server.py:8480-8483`）。

## 根拠

- `terminal/serve/server_parts/http_api.py:846-872` — 環境変数名、完全一致判定、`faulthandler.enable(all_threads=True)` の呼び出し、例外の握りつぶし。
- `terminal/serve/server.py:250-275` — `arm_faulthandler` の import。
- `terminal/serve/server.py:8472-8495` — サーバー起動時の呼び出し位置と、その後の起動処理。
- `terminal/strata_control/runtime.py:1650-1656` — runtime host が別途有効化を試みる箇所。

