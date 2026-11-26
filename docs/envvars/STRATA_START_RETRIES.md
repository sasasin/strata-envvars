# `STRATA_START_RETRIES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata serve` の Python サーバーがエンジンを起動した際、エンジンが `READY` を返す前に短時間で終わった場合のうち、GPU runtime の一時的な起動失敗と判定できるものを何回追加で起動し直すかを指定する。既定は追加 3 回（初回を含め最大 4 回）、`0` はこの再試行を無効にする。エンジンの生成処理やリクエスト後の再起動回数を直接指定する変数ではない。読み取りと再試行判定は `terminal/serve/server.py` の `START_RETRIES` と `StrataEngine.__init__` にある（`terminal/serve/server.py:506, 761-763, 886-902`）。

## 値と判定

モジュール読込時に `os.environ.get("STRATA_START_RETRIES", "3") or 0` を Python の `int()` に渡し、その結果を `max(0, ...)` で 0 以上に clamp する（`terminal/serve/server.py:506`）。

| 条件 | 未設定 | 設定時に有効になる値 | 無効・失敗になる値 |
|---|---|---|---|
| `terminal/serve/server.py` を読み込むサーバープロセス | `3` | 整数に変換できる文字列。例: `0`、`1`、`+2`、`-1`（負数は `0` に clamp）、前後に空白のある ` 2 ` | 空文字は `0`。小数 `1.5`、`0anything`、空白だけの文字列など `int()` が変換できない値は `ValueError` となり、サーバーモジュールの読込に失敗する。 |

文字列全体が整数として変換され、先頭だけの判定や部分文字列の読み飛ばしはない。大文字小文字の区別は関係しない。上限 clamp はなく、負数は再試行 0 回として扱われる。CLI 引数、設定ファイル、別の環境変数による上書きはない。`--engine mock` は再試行経路には入らないが、この値の変換はモード選択前のモジュール読込時に行われるため、無効な文字列は mock モードでもモジュール読込を失敗させる（`terminal/serve/server.py:506, 9157-9159, 9386-9394, 9484-9489`）。

## 有効になる条件

- `--engine strata` で設定された実エンジンを `StrataEngine` 経由で起動すること。単一エンジン、replica、split serving の各起動がこのクラスを使う（`terminal/serve/server.py:8788-8796, 8845-8852, 8899-8919`）。
- 起動した子プロセスが `READY` 前に終了し、READY 待ちの timeout ではなく、起動経過が 30 秒以内で、ログが再試行対象の一時失敗条件を満たすこと（`terminal/serve/server.py:509-530, 886-887`）。
- `STRATA_START_RETRIES` は設定可能な追加回数を残していること（`_attempt < START_RETRIES`）。他の API オプション、モデル名、GPU backend による値の変更はない。
- lazy load の場合もサーバーモジュール読込時に値は取得され、実エンジンを初めてロードするときに同じ上限を使う。環境を変更しても、既に読み込まれたモジュール内の値は変わらない（`terminal/serve/server.py:506, 798-800, 5032-5054`）。

## 実行時の詳細

`StrataEngine.__init__` はプロセス起動時刻を記録し、エンジンの標準出力から `READY` を待つ。READY 前にプロセスが終わった場合、timeout でなく、起動から 30 秒以内であることに加え、ログファイルが存在して読み出せることを確認する。ログの当該起動部分（最大 64 KiB）から空行を除き、`[strata]` で始まるサーバー自身の行を除いたエンジン行を調べる。`hsa_exception`、`HSA_STATUS_ERROR`、`hsaKmt` のいずれかをログに含む場合は、エンジン行が `terminate called` または `what()` で始まるか、それらのマークを含む場合だけ再試行する。このマーク分岐では終了コードによる追加除外はしない。マークがない場合はエンジン自身の行が一つもなく、終了コードが `1` でなく、システムによる crash 終了と認定されない場合だけ再試行する。ログがない・読めない、30 秒超、上記以外のエンジン行、（マークなしの場合の）終了コード `1` または OS crash code、READY timeout はこの再試行の対象外（`terminal/serve/server.py:509-530, 886-887`; `terminal/serve/server_parts/engines.py:292-300, 347-365`）。

再試行間隔は 2、4、8 秒…と試行ごとに倍増し、成功すれば READY 後の通常処理へ進む。`START_RETRIES=N` のとき、初回と追加 N 回を合わせて最大 N+1 回起動する。上限に達した場合や対象外の失敗では `EngineDied` を発生させ、「the engine did not report READY within … s」または「the engine exited before it was ready」を理由に、終了情報やログ末尾を付ける（`terminal/serve/server.py:888-902, 929-939`）。

この判定に該当しない失敗では、別機能として VRAM 不足時に drafter なしで再起動する経路や、Auto 選択した DFlash2 の起動失敗時に MTP で再起動する経路が続けて判定される。これらは `STRATA_START_RETRIES` の回数に含めず、条件が一致した一時失敗の再試行より後に評価される（`terminal/serve/server.py:903-927`）。エンジンの通常 restart は `restart()` の別の `tries` 制御を持つが、その各起動も `__init__` を呼ぶため、この変数の起動失敗判定を通る（`terminal/serve/server.py:1206-1232`）。

値は `server.py` の import 時に一度だけ読み取られ、リクエストごとや起動試行ごとには読み直さない。子プロセス用の `child_env` は現在の `os.environ` のコピーから作るため、親に設定済みの `STRATA_START_RETRIES` は通常そのまま子の環境にも含まれる。設定ファイルの `env` に同名キーがあれば、その値がコピー後に上書きされる。ただし、Strata ソース内でこの名前を値として読む箇所は親サーバーの上記一箇所だけであり、子への転送値は親サーバーの再試行上限を変えない（`terminal/serve/server.py:4007-4028, 506, 833-835`）。

## ログと測定値

一時的な GPU runtime 失敗と判定した場合、サーバー stdout に `[strata] the engine stopped while the GPU runtime was starting ...: starting it again in N s (try X of Y)` を出す。ログに runtime のマークがなく、エンジン自身が何も書かずに終わった場合は、`[strata] the engine exited before it wrote anything to its log ...; it may be a GPU runtime that was not ready yet: starting it again in N s (try X of Y)` を出す。ここで `X` は次の試行番号、`Y` は初回を含む最大試行数。別の失敗ではこの再試行通知を出さず、READY timeout または起動前終了の `EngineDied` 経路になる（`terminal/serve/server.py:890-900, 929-939`）。

`docs/DETAILS.md` にこの変数や再試行回数の説明は見つからなかったため、測定値は記載しない。

## 根拠

- 値の読取・既定値・clamp: `terminal/serve/server.py:506`
- エンジンの起動と READY 待ち: `terminal/serve/server.py:761-763, 798-835, 841-870`
- 一時失敗の判定と通知・間隔・回数: `terminal/serve/server.py:509-530, 886-902`
- GPU runtime の判定語と crash 終了の判定: `terminal/serve/server_parts/engines.py:292-300, 347-365`
- 対象となる実エンジンモードと mock 経路: `terminal/serve/server.py:9157-9159, 9386-9394, 9484-9489`
- 別の起動 fallback と restart 経路: `terminal/serve/server.py:903-927, 1206-1232`
