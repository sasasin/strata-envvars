# `STRATA_BATCH_TRACE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の Python サーバー `serve/server.py` が engine との制御通信と batch 経路の状態遷移を stderr に診断出力するためのスイッチです。engine の batch 動作や生成処理の選択を変更する環境変数ではありません。

## 値と判定

モジュール読み込み時に `bool(os.environ.get("STRATA_BATCH_TRACE"))` で判定します。文字列全体の parse や数値変換はありません。

| 環境の値 | 判定 | 説明 |
|---|---|---|
| 未設定 | 無効 | `os.environ.get` の既定値 `None` は false。 |
| 空文字 (`STRATA_BATCH_TRACE=`) | 無効 | 空文字列は false。 |
| 空でない任意の文字列 | 有効 | `0`、`false`、空白だけの値を含め、空文字列以外は true。 |

有効・無効の結果は `_BTRACE` に一度保存されます。プロセス起動後に環境を書き換えても再評価されません。CLI 引数や設定値による上書きは実装されていません（`serve/server.py:873-878`）。

## 有効になる条件

`serve.server` モジュールが読み込まれた Python サーバープロセスで有効です。CUDA/HIP などの backend やモデル状態を調べる分岐はありません。実際に診断行が出るのは `btrace()` が呼ばれる経路に限られます。`StrataEngine._send()` から送信する制御文字列のほか、制御行の読み取り、および batch 生成処理中の状態遷移が対象です（`serve/server.py:1512-1519,1551-1555,1891-1899,1921-1923,2198-2207`）。

## 実行時の詳細

有効な場合、`btrace()` は標準エラーへ `[batch-trace]`、スレッド ID の下4桁相当（`threading.get_ident() % 10000`）、呼び出し側が渡した引数を空白区切りで出力し、flush します。送信側は文字列の先頭最大60文字を `send>` とともに記録します。受信側は `PP ` と `INFO` で始まる行を除外し、それ以外の制御行について mode と前後空白を除いた先頭最大60文字を記録します（`serve/server.py:876-878,1512-1517,1551-1555`）。

batch 処理内では制御権を得たときの `ctl acquired`、slot から solo path に戻るときの `back to the solo path`、生成処理の `finally` における phase・slot・holding の値も記録します（`serve/server.py:1891-1899,1921-1923,2198-2207`）。出力文字列はこれらの呼び出し側で作られ、ログの出力自体は `_BTRACE` の条件と `print()` による stderr 出力だけです。読み取り箇所は `serve/server.py:873` のみで、確認できた `btrace()` の定義は同ファイルの876行、呼び出しは5箇所（1513, 1555, 1922, 2202, 2207行）です。

## 根拠

- `serve/server.py:873-878` — 環境値の取得、真偽値化、module-level cache、および stderr の出力形式。
- `serve/server.py:1512-1519` — engine への送信時の trace と送信処理。
- `serve/server.py:1521-1555` — 制御行を読む loop 内での trace 条件。`PP ` / `INFO` 行は記録しません。
- `serve/server.py:1891-1899,1921-1923,2198-2207` — batch 生成経路の説明と状態遷移 trace。

`000_envvers.md` には候補名として掲載されています。Strata ソース内の完全一致検索では上記のサーバー実装だけに現れ、C++ engine 側がこの環境変数を読む実装は確認できませんでした。
