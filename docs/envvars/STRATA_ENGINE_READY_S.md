# `STRATA_ENGINE_READY_S`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`serve/server.py` が Strata engine の起動後に `READY` 行を受け取るまで待つ時間を秒単位で指定します。既定値は 900 秒です。期限までに engine が `READY` を報告しない場合、サーバーはその engine プロセスを終了させ、起動失敗として扱います。この値は Python サーバーの設定であり、engine 実行ファイルが読む設定ではありません。

## 値と判定

サーバーのモジュール読み込み時に `_timeout_env("STRATA_ENGINE_READY_S", 900.0)` が一度実行されます。共通 helper は `os.environ.get(name, default)` の結果を `float()` に渡します。

| 環境変数の状態 | 結果 |
|---|---|
| 未設定 | `900.0` 秒 |
| 空文字、または `float()` が `ValueError` を出す文字列 | `900.0` 秒に fallback |
| `float()` で変換でき、値が 0 以下 | `None` となり、READY 待ちに期限を設けない |
| `float()` で変換でき、値が正 | その秒数を待ち時間として使う |

整数だけでなく小数や、`float()` が受け付ける表記も変換されます。文字列全体を `float()` で変換するため、数値の後ろに任意の文字を付けた値は無効です。無効な文字列への警告ログはありません。正の値に上限 clamp はありません。`NaN` や無限大も Python の `float()` が変換できますが、有限値であることを検証するコードはありません。その場合の deadline/queue timeout の挙動は通常の有限秒数とは異なり得ます。

根拠: `serve/server.py:295-300,330`。

## 有効になる条件

この値を使うのは Python の `serve/server.py` の engine 起動処理です。CLI 引数や設定ファイルによる上書きは、この値の読み取り・設定箇所にはありません。サーバーのプロセス開始後に環境変数を書き換えても、既に設定されたモジュール定数 `ENGINE_READY_S` は再評価されません。

画像 encoder の READY 待ちには別の `STRATA_VISION_READY_S` と `VISION_READY_S` が使われます。この変数はそちらの timeout を変更しません。

## 実行時の詳細

`StrataEngine` は engine を `popen()` で起動した後、専用スレッドで stdout の行を queue に送り、起動処理側でその queue を読みます。開始時に `time.monotonic() + ENGINE_READY_S` の deadline を作り、残り時間を `ready_q.get(timeout=left)` に渡します。`ENGINE_READY_S` が `None` の場合は deadline と queue timeout を使わず、行が届くまで待ちます。`INFO ` 行は `self.info` に取り込み、`READY` で始まる行を受け取ると最大 context と stop 対応を記録して起動待ちを終えます。

期限切れの場合は `timed_out` とし、engine に `kill()` を試みます。その後、終了を最大 5 秒待ち、ログ末尾などを含む `EngineDied` を送出します。timeout は transient start failure の自動再試行条件から除外されています。報告される理由は `the engine did not report READY within <秒数> s` です。期限前に engine が終了した場合は別の理由 `the engine exited before it was ready` になります。engine が timeout 前に `READY` を返せば、通常どおり起動処理が続きます。

根拠: `serve/server.py:1023-1028,1034-1059,1060-1102`。

## 根拠

- `serve/server.py:287-292` — READY 行を待つ読み取りの背景と、関連 timeout 変数の説明。
- `serve/server.py:295-300,328-330` — 共通の環境変数変換と既定値。
- `serve/server.py:1023-1059` — engine 起動、deadline、READY/INFO 行の処理。
- `serve/server.py:1060-1102` — timeout 時の kill、再試行条件、失敗理由。

`docs/DETAILS.md` にこの変数の追加説明や測定値は見つかりませんでした。性能やモデル出力への影響を示す測定値は確認していません。
