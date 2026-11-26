# `STRATA_BLOCKING_CONSOLE`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（2026-11-26 時点）。作業ツリーは `## main...origin/main` で未コミット変更なし。

## 役割

サーバープロセスの `sys.stdout` / `sys.stderr` を、コンソール出力用の有界キュー（`NonBlockingOut`）に置き換えるかどうかを切り替える。`1` を設定すると置き換えをやめ、素のストリームへ直接書く従来のブロッキング出力に戻る。テスト用のスイッチであり、通常の起動ではキュー経由（非ブロッキング）が既定。

読み取りは `terminal/serve/server.py:9177` の 1 箇所だけで、`main()` が `_main()` を呼ぶ直前に行う。`serve/nonblocking_out.py` の `decoupled_console()` が `NonBlockingOut` を `sys.stdout` / `sys.stderr` に取り付ける（`terminal/serve/nonblocking_out.py:105-123`）。`_main()` の引数、リクエスト処理、生成結果、終了コードはどちらの分岐でも同じ。

## 値と判定

`os.environ.get("STRATA_BLOCKING_CONSOLE") == "1"` の完全一致比較。前後の空白除去、小文字化、`atoi` のような数値変換はない（`terminal/serve/server.py:9177`）。

| 値 | 判定 | コンソール出力 |
|---|---|---|
| 未設定 | `None` で不一致 | 非ブロッキング（キュー経由） |
| `1` | 一致 | ブロッキング（素のストリーム） |
| 空文字 `""` | 不一致 | 非ブロッキング |
| `0`, `2`, `01`, `" 1"`, `"1 "`, `true`, `TRUE`, `yes`, `on` | 不一致 | 非ブロッキング |

build、OS、backend、GPU、モデル、サーバーモードによる判定差はない。条件分岐は上記 1 箇所だけで、他の環境変数との優先順位もない。

## 有効になる条件

- サーバーの `main()` を通る起動であること。`python terminal/serve/server.py`、`python -m serve.server`、`strata serve` のフォアグラウンド実行が該当する（`terminal/serve/server.py:10021-10022`、`terminal/strata_cli/cli.py:981`）。engine、setup、同梱ツールはこの名前を読まない。
- 値が有効でも、置き換え対象は「プロセス自身のストリーム」だけ。`sys.stdout` / `sys.stderr` がそれぞれ `sys.__stdout__` / `sys.__stderr__` と同一オブジェクトのときだけ `NonBlockingOut` を付ける（`terminal/serve/nonblocking_out.py:111-116`）。
- `strata serve --output jsonl` または `--quiet` では `contextlib.redirect_stdout()` が `sys.stdout` を差し替えるため、stdout はラップされない（`terminal/strata_cli/cli.py:909-912,939-945`）。JSONL イベントは差し替え前の stdout を保持して書かれるので、この変数の影響を受けない（`terminal/strata_cli/cli.py:878,901-902`）。この 2 モードでは stderr だけが対象になり得る。
- テストランナーや組込み先がストリームを差し替えている場合も、そのストリームは対象外。
- バックグラウンドのマネージドサーバーは `os.environ.copy()` で子を起動するため、起動時点の値が継承される（`terminal/strata_control/runtime.py:1056-1074`）。engine の環境も `dict(os.environ)` から作られるが、engine 側に読み取りはない（`terminal/serve/server.py:4110`）。

## 実行時の詳細

`main()` は活動リースの取得と `lastrun.begin()` の後に値を 1 回読み、`1` ならラップせず、それ以外なら `with decoupled_console():` の中で `_main()` を実行する（`terminal/serve/server.py:9175-9181`）。モジュール定数や `static` へのキャッシュはなく、起動後に `os.environ` を書き換えても反映されない。次回起動時に読み直す。

非ブロッキング側の実装（`terminal/serve/nonblocking_out.py:20-102`）:

- `write()` はテキストを `deque` に追加して即座に返る。実際の書き込みと `flush()` はデーモンスレッド `strata-console` が行う（`:31-32,69-87`）。
- キューは 1,048,576 文字（`1 << 20`）または 4,000 チャンクが上限。超えると最も古いチャンクを捨て、`dropped_chunks` / `dropped_bytes` を増やす（`:21,45-49`）。このカウンタを読む箇所はサーバー内になく、ログにも出ない。
- `flush()` は何もしない。`print(..., flush=True)` も出力完了を待たない（`:53-54`）。
- 実ストリームの `write` / `flush` が `OSError` / `ValueError` / `UnicodeError` を出しても握りつぶし、テキストは失われる（`:83-87`）。
- 終了時は最大 2.0 秒 `drain()` してから `_closing` を立て、元のストリームに戻す（`:89-102,119-123`）。close 後の `write()` は出力せずに文字数を返す（`:40-42`）。
- `encoding` や `buffer` などは実ストリームへ委譲される（`:65-66`）。`sys.stdout.buffer` 経由の書き込みはキューを通らないが、サーバー本体にその使用はない。
- プロトコル出力（engine のパイプ、HTTP 応答）はこのラッパーを通らない（`:10`）。

`1` の場合はラッパーを付けないため、コンソールが出力を受け取らずに停止すると、`print()` を呼んだスレッドがそのまま待つ。これがコメントに書かれた本来の動機（リクエストのターン、キャンセル、admission をコンソールが止めない）を無効化するテスト用の経路である（`terminal/serve/server.py:9164-9165`）。出力内容そのものは、コンソールが受け取り続ける限りどちらのモードでも同じで、キュー内でも順序は保たれる。

## ログと測定値

モードの選択、キューからのドロップ、ラッパーの有効化を通知するログ・警告はない。`dropped_chunks` / `dropped_bytes` はオブジェクト内に数えるだけで、どこにも出力されない（`terminal/serve/nonblocking_out.py:29-30,45-49`）。この変数に関する測定値は `docs/` に見つからない。`000_envvers.md` の候補（829 行目）と実装は一致する。

## 根拠

- `terminal/serve/server.py:9158-9188` — `main()` の docstring と `STRATA_BLOCKING_CONSOLE` の完全一致判定、`_main()` の 2 分岐。
- `terminal/serve/nonblocking_out.py:1-10,105-123` — 目的、対象ストリームの条件、終了時の drain と復元。
- `terminal/serve/nonblocking_out.py:20-102` — キューの上限、最古チャンクの破棄、書き込みスレッド、エラー握りつぶし、`flush`。
- `terminal/strata_cli/cli.py:877-912,939-951,981` — `strata serve` が同一プロセスで `main()` を呼ぶことと、JSONL/quiet 時の stdout 差し替え。
- `terminal/strata_control/runtime.py:1056-1074` — マネージドサーバーへの環境の継承。
- `terminal/serve/server.py:4110` — engine の子環境が `os.environ` のコピーであること。
