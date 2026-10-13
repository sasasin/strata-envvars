# `STRATA_ENGINE_READY_S`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata --serve` を起動する Python サーバーが、engine 子プロセスから `READY` 行を受け取るまで待つ上限時間を秒単位で指定します。生成リクエスト中の無応答時間や画像 encoder の待ち時間を制御する変数ではありません。server は engine の起動時に `READY` 前の標準出力を別スレッドからキューへ送り、期限付きで読みます（`serve/server.py:674-699`）。

## 値と判定

`_timeout_env()` が `os.environ.get(name, default)` の値を Python `float()` で変換します。判定は次のとおりです（`serve/server.py:238-244,264`）。

| 環境変数の値 | 結果 |
|---|---|
| 未設定 | 既定値 `900.0` 秒 |
| 有効な正数 | その秒数を待ち時間にする。小数も使用可能 |
| `0` または負数 | `None` に変換され、期限を設けず待つ |
| 空文字、数値に変換できない文字列 | `ValueError` を捕捉し、既定値 `900.0` 秒に戻る |

文字列全体が `float()` で解釈できる必要があり、部分一致や整数への丸めはしません。前後空白や指数表記も Python の `float()` が受け付ける形式なら変換されます。明示値に CLI 引数や設定ファイルからの上書きはありません。`nan` / `inf` のような非有限値を明示的に拒否する検査もありません。

## 有効になる条件

サーバープロセスが `serve.server` を読み込むときに環境変数を評価します。そのため、通常はサーバー起動前に設定します。engine を起動するたび（遅延起動後や再起動を含む）にこのグローバル値が使われますが、サーバー稼働中に環境を変更しても値は再評価されません（`serve/server.py:238-264,623-648,678`）。

サーバー側の待ち時間設定です。`StrataEngine` に渡す `env` は engine 子プロセスの環境ですが、この変数の評価はその子プロセス起動より前にサーバープロセス内で行われます（`serve/server.py:671-678`）。

## 実行時の詳細

待ち時間は `time.monotonic()` による期限で管理されます。engine 出力中の `INFO` 行は `self.info` に反映し、`READY` で始まる行を受け取ると待ちを終えます。正の期限内に `READY` が来なければ server は engine を `kill()` し、最大5秒の終了待ちと pipe/log の後始末を試みた後、`EngineDied` として起動失敗を返します。エラー理由は `the engine did not report READY within <秒> s` で、ログがあればログ参照と起動失敗ヒントを付けます。期限より先に engine の出力が閉じた場合は、`the engine exited before it was ready` になります（`serve/server.py:680-720`）。

0以下の指定では deadline を作らず、`READY` または出力終了まで待つため、この待ち処理自体はタイムアウトしません。engine 起動タイムアウト時の `EngineDied` は、起動を待っているリクエストをエラー応答にする経路へ渡されます（`serve/server.py:715-720`）。

## 資料との照合

`docs/DETAILS.md` の環境変数を含む該当箇所では、同じ `READY` 起動待ち変数の既定秒数や既定値の説明は見当たりません。ベンチマーク記録のコマンドに `STRATA_ENGINE_READY_S=0` はありますが、測定記録であり挙動の実装根拠には使っていません（`bench/results/2026-10-08-community-2x-rtx3080-20gb-ud-q4-k-xl-512k-pool/start-command.txt:41`）。

## 根拠

- `serve/server.py:230-244`: 起動時の読み取り待ちタイムアウトの説明と、共通 parser の変換・fallback・0以下の扱い。
- `serve/server.py:262-264`: 関連する画像 encoder / readiness timeout と `ENGINE_READY_S` の既定値。
- `serve/server.py:623-678`: engine 子プロセス起動と READY 待ち期限の設定。
- `serve/server.py:680-720`: INFO/READY の処理、timeout 時の kill、エラー内容。
- `serve/server.py:864-878`: READY 前の標準出力をキューへ送る reader。
