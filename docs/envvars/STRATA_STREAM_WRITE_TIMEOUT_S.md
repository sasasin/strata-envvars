# `STRATA_STREAM_WRITE_TIMEOUT_S`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

`strata --serve` のストリーミング HTTP 応答で、イベント書き込みに使う接続 socket の timeout を秒単位で設定します。既定値は 60 秒です。値が 0 以下なら timeout 設定を行いません。対象は OpenAI Chat Completions、OpenAI Responses、Anthropic Messages の SSE 応答です。ストリーミングしない応答には適用されません。

## 値と判定

モジュール読み込み時に `float(os.environ.get("STRATA_STREAM_WRITE_TIMEOUT_S", "60") or 0)` で一度変換されます。設定値は Python の `float()` が受理する文字列である必要があります。

| 環境変数の状態 | 結果 |
|---|---|
| 未設定 | `60.0` 秒 |
| 空文字 | `0.0` 秒。timeout を設定しない |
| 数値文字列 | `float()` で変換した値を使用。正数なら timeout を設定し、0 または負数なら設定しない |
| `nan` など | `float()` の変換結果をそのまま使い、`> 0` の判定に従う。`nan` は条件を満たさない |
| 数値に変換できない文字列 | モジュール読み込み時に `ValueError`。この箇所に fallback や例外処理はなく、サーバーは通常の起動経路に進めない |

値の clamp や整数化はありません。正の値は秒単位の浮動小数として `connection.settimeout()` に渡されます。正の無限大など、極端な値が各 OS の socket 実装でどう扱われるかは Strata のソースでは定めていません。

## 有効になる条件

- Strata の Python HTTP サーバーを起動していること。
- リクエストが SSE ストリーミング応答を選んでいること。非ストリーミング応答では `_sse()` を通りません。
- 変換後の値が `0` より大きいこと。

CLI 引数、設定ファイル、リクエスト値、他の環境変数による上書きはこの実装にはありません。環境変数は `serve/server.py` のモジュールレベル定数として読み込まれるため、サーバープロセス起動後に環境を変更しても再評価されません。`docs/DETAILS.md` にこの変数の説明は見つかりませんでした。

## 実行時の詳細

SSE 応答では、サーバーが HTTP 200 とイベントストリーム用ヘッダーを送信した後、正数の場合に `self.connection.settimeout()` を呼びます。この設定後、各イベントや keep-alive の書き込みと flush が続きます。クライアントが読み取りを止め、書き込みが進まない状態が socket timeout などの `OSError` になると、各ストリーム処理は切断として記録します。Chat Completions、Responses、Anthropic の通常ストリームでは `note_client_disconnect()` によって request の cancel event を立て、ストリーム iterator を閉じます。Responses の事前完了イベント経路では切断結果を記録します。

timeout は SSE を開始する段階で接続に設定されます。コード上、ストリーム単位で元の timeout を復元する処理はありません。`settimeout()` 自体が `OSError` を返した場合は無視して処理を続けます。

## 根拠

- `serve/server.py:318-321` — 変数の役割を示す注釈と、モジュール読み込み時の既定値・変換。
- `serve/server.py:8530-8542` — SSE ヘッダー送信後の正数判定、socket timeout 設定、および `OSError` の無視。
- `serve/server.py:8643-8656` — Chat Completions の非ストリーム分岐、SSE 書き込み、切断処理。
- `serve/server.py:8674-8685, 8727-8768` — Responses のストリーム経路と非ストリーム経路、切断処理。
- `serve/server.py:8879-8894` — Anthropic Messages の非ストリーム分岐、SSE 書き込み、切断処理。
- `serve/server.py:4941-4950` — `note_client_disconnect()` が cancel event を設定する処理。
