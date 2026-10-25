# `STRATA_BENCHMARK_API_KEY`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリ、ベンチマーク結果・記録の内容、およびテストコードは実装根拠から除外した。

## 役割

この名前を読む箇所は、日付付きベンチマーク結果ディレクトリ `bench/results/2026-10-09-community-rtx5090-9800x3d-swift-1m/` 内の `replay.py` だけである。記録済みの HTTP リクエストを、すでに起動・設定済みの Strata サーバーへ再送する再生ハーネスが、サーバー認証用 bearer token を任意で付ける。通常の Strata engine や server の環境変数設定としては読まれていない。

このファイルはベンチマーク結果に同梱された再生ツールである。調査手順で除外対象となるベンチマーク結果・記録の領域にあるため、ここで説明するのは当該ツールの動作に限られ、一般利用者向け Strata 設定としての機能を示すものではない。

## 値と判定

Python の `os.environ.get("STRATA_BENCHMARK_API_KEY", "")` で、モジュール読み込み時に一度読み取る。文字列の parse、trim、文字種検査はない。

| 状態 | ツール内の値 | HTTP header |
|---|---|---|
| 未設定 | 空文字列 `""` | `Authorization` を付けない |
| 明示的な空文字 | 空文字列 `""` | `Authorization` を付けない |
| 空でない任意の文字列 | その文字列をそのまま保持 | `Authorization: Bearer <値>` を付ける |

大文字小文字、空白、値の形式、長さはこのコードでは検証しない。空白だけの値も truthy な文字列なので header にそのまま入る。コマンドライン引数や設定ファイルによる上書きは実装されていない。

## 有効になる条件

`replay.py` を実行する場合に限る。環境変数が空でなければ、`Client.headers()` が生成する header が `json_request()` と `stream()` の HTTP 要求に使われる。したがって status/health の確認、チャット補完の再生、および slot save/restore 要求にも同じ header が適用される。

値が未設定または空なら、認証 header を付けずに要求する。接続先が認証を必要とするか、空や不正な token をどう扱うかは接続先サーバーの動作であり、この変数を読むツールの説明範囲外である。

## 実行時の詳細

値は `replay.py` の import 時にモジュール定数 `SECRET` として取得される。プロセス起動後に環境を書き換えても `SECRET` は再取得されない。コードに子プロセスへの引き渡しはない。

`Client.headers()` は通常要求に `Content-Type: application/json` を付け、stream 要求にはさらに `Accept: text/event-stream` を付ける。`SECRET` が空でなければ両方に `Authorization: Bearer ` と値を連結した header を追加する。`Client.json_request()` は `/v1/status`、`/health`、slot 操作要求でこの関数を使い、`Client.stream()` は `/v1/chat/completions` への要求で使う。

例外文字列に秘密値が含まれる場合、`error_text()` は値が空でないときにその部分を `[redacted]` に置換する。再生結果の error 欄や stderr に保存・表示するエラーで使われる。一方、HTTP header 自体はログへ書き出す処理が見当たらない。

## 根拠

- `bench/results/2026-10-09-community-rtx5090-9800x3d-swift-1m/replay.py:23-24`: import 時の取得と既定値。
- `replay.py:35-37`: エラー文字列内の秘密値の置換。
- `replay.py:44-64`: HTTP header の組み立て。空文字でない場合だけ bearer header を追加。
- `replay.py:66-79,81-88`: JSON 要求と status/health 確認で共通 header を使用。
- `replay.py:90-91,179-180`: streaming chat completion 要求で同じ header 関数を使用。
- `replay.py:317-398`: CLI に API key 引数がなく、再生・slot 操作のどちらも同じ `Client` を使う。
- `bench/results/2026-10-09-community-rtx5090-9800x3d-swift-1m/README.md:101-105`: 再生ツールは既に動作中の設定済みサーバーと通信し、サーバーを起動・再起動・モデル選択しない旨の説明。
