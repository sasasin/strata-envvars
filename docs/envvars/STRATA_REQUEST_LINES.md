# `STRATA_REQUEST_LINES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata の Python サーバーが engine のログを追い、request summary をサーバープロセス自身の stdout に再出力するための opt-in です。engine の stderr はログファイルへ送られるため、サーバーの stdout だけを読む supervisor などにもリクエスト単位の数値を見せます。生成処理や engine への引数を変える環境変数ではありません。

候補一覧にはありますが、値を実際に読む箇所は `serve/server.py` です。C++/CUDA/HIP/SYCL 側にこの名前の読み取りはありません。`docs/DETAILS.md` にこの名前の説明も見つかりませんでした。

## 値と判定

Python の `os.environ.get("STRATA_REQUEST_LINES")` の真偽値だけで判定します。文字列を `1` と比較したり、数値に変換したりはしません。

| 親サーバーの環境値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 `""` | 無効 |
| 空でない任意の文字列（`"1"`, `"0"`, `"false"` など） | 有効 |

したがって、`STRATA_REQUEST_LINES=0` や `false` も有効です。無効値用の警告や fallback はありません。根拠: `serve/server.py:1054-1056`。

## 有効になる条件

値が空でなくても、次の条件を満たすときだけ follower thread を開始します。

- `StrataEngine` が lazy でないこと。lazy 初期化はこの判定より前に return します。
- `log` が指定されていること。
- その絶対パスのログを、このサーバープロセスがすでに追跡対象にしていないこと。

この判定に OS、backend、モデル状態、CLI 引数による分岐はありません。同じ絶対パスにつき `_echoing` set により follower は一つだけです。ログを指定しない場合や lazy 初期化の場合は、変数が設定されていても何も出力しません。根拠: `serve/server.py:1043-1056`。

サーバー設定の `env` は `child_env()` が親プロセス環境をコピーした後で engine 子プロセス用の値を反映し、`StrataEngine` に渡します。一方、この変数の条件判定は `env` 引数ではなく `os.environ` を直接参照します。そのため設定ファイルの `env: {STRATA_REQUEST_LINES: ...}` だけでは有効になりません。根拠: `serve/server.py:104-1056, 3747-3760, 9278-9279`。

## 実行時の詳細

`StrataEngine.__init__` の lazy 判定後、ログを開いた時点で親プロセスの環境を読みます。値を別の変数に cache する処理はありませんが、ログごとに follower thread を一度だけ起動するため、既に追跡中のログについて後から環境を変更しても thread の開始・停止には反映されません。follower の開始位置は起動時点のログファイルサイズで、以後は追加行を読みます。EOF では 0.2 秒待って再読込します。engine は `--serve` で起動され、stdout は pipe、stderr はログファイルに接続されます。根拠: `serve/server.py:698-710, 1043-1056, 1077-1079`。

follower は `ENGINE_REQUEST` の正規表現に一致した行だけを拾います。一致すると、prompt token 数、再利用 token 数（出力では `cached`）、生成 token 数、prompt 読み取り時間、読み取り時間と生成時間の合計、prefill/decode tok/s を `[strata] request ...` 行として stdout に flush します。所要時間は `%.0f` で丸めて表示します。一致しない行は無視します。根拠: `serve/server.py:500-504, 690-710`。

現在の通常 engine の request summary は stderr に `strata serve: prompt ... tokens = ... reused + ... read ...` として出力されます。サーバーはその行から必要なフィールドを抽出し、engine の元の文面ではなく整形した行を再出力します。根拠: `src/program/generate.cpp:17462-17473`。この変数によって engine 側のログ出力自体が変更されるわけではありません。

## ログと失敗経路

この環境変数専用の有効化ログ、警告、エラー終了経路はありません。空値、未設定、ログなしでは follower が起動しません。一致する summary 行がなければ追加出力はありません。follower は daemon thread で、通常はログを読み続けます。根拠: `serve/server.py:698-710, 1050-1056`。
