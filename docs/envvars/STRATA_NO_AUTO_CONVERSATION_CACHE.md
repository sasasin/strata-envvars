# `STRATA_NO_AUTO_CONVERSATION_CACHE`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（`2026-11-26` 時点）。

## 役割

この変数は、Strata のターミナルサーバーが大容量 RAM 向けに自動計算する会話キャッシュ予算を止める。値が文字列 `"1"` のとき、サーバーはエンジン起動引数へ自動の `--conversation-cache-mib N` を追加せず、エンジン自身の予算決定に任せる。会話キャッシュ自体を無効にする変数ではなく、エンジンの他の設定や明示されたキャッシュ引数も変更しない。読み取り箇所は `terminal/strata_control/conversation_cache_size.py` の `args_with_budget` である（`terminal/strata_control/conversation_cache_size.py:85-102`）。

## 値と判定

Python の `os.environ.get(...) == "1"` による文字列全体の完全一致で判定する。数値変換、空白除去、大文字小文字変換はしない。未設定では比較が偽となり自動計算を続ける。空文字、`0`、`true`、`TRUE`、` 1`、`1 `、`01` も一致せず、自動計算を止めない。ちょうど `1` のみ止める。無効文字列としてのエラーや警告はなく、`"1"` 以外は通常経路と同じ扱いになる（`terminal/strata_control/conversation_cache_size.py:88-89`）。

| 条件 | unset | 自動計算を止める値 | 自動計算を止めない値 |
| --- | --- | --- | --- |
| サーバーの引数生成でこの判定に到達 | エンジンの自動予算計算へ進む | `1` | 空文字、`0`、`true`、`TRUE`、` 1`、`1 ` など `1` 以外すべて |

## 有効になる条件

- 対象は `terminal/serve/server.py` の通常エンジン経路である。Hy4 と Inkling の設定は `engine_args` 冒頭で専用の引数生成関数へ戻るため、この予算処理には到達しない（`terminal/serve/server.py:3734-3744`）。
- エンジン実行ファイルのパスがあり、サーバーがそのファイル内に `--conversation-cache-mib` の文字列を確認できる必要がある。実行ファイルが読めない場合や文字列がない場合も自動計算しない（`terminal/serve/server.py:3860-3867`、`terminal/serve/server_parts/engines.py:931-945`）。
- 起動設定の `args` に `--conversation-cache-mib` が既にあれば、値が `0` を含め何であっても自動計算をしない。`--prompt-cache` または `--conversation-cache-slots` の最後の値が `strip()` 後に空文字または `0` の場合も同様である。これらの CLI 指定があると、環境変数が未設定または `1` 以外でも自動追加されない（`terminal/strata_control/conversation_cache_size.py:45-49,63-72,88-89`）。
- この変数が未設定または `1` 以外でも、RAM の総量・利用可能量が読めない／0 以下、計算した残量が正でない、または計算結果が 8192 MiB 以下ならサーバーは `--conversation-cache-mib` を追加せず、エンジンに任せる。予算計算は、利用可能 RAM からモデルファイルサイズ、4096 MiB の余裕、設定された `--conversation-cache-min-free-mib`（未指定なら 2560 MiB）を差し引いた残量の 40%、PC RAM の 25%、131072 MiB のうち最小値を 256 MiB 単位で切り下げる。明示された床値を float に変換できない場合は 2560 MiB を使う（`terminal/strata_control/conversation_cache_size.py:24-42,75-82,90-102`）。

## 実行時の詳細

サーバーは `engine_args` の生成時に `conversation_cache_budget_args` を呼び、環境値を調べる。値をモジュール変数や関数内 `static` に保存するコードはなく、引数生成のたびに現在の Python `os.environ` を参照する。実際のエンジン起動時には `engine_args` の戻り値が `StrataEngine` に渡され、子プロセスは `[exe, "--serve", *args]` として起動する。したがって `"1"` はサーバーが追加の予算引数を作ることを抑え、エンジンが自身の既定ルールで決める経路に戻す（`terminal/serve/server.py:3834-3836,3860-3867,8965-8966,877-879`）。

自動予算の計算値が得られ、呼び出し側が告知を有効にしている場合は、サーバーは標準出力へ `[strata] conversation cache: ...` の行を出してから引数を追加する。`announce=False` の引数評価ではこの行を出さない。環境値が `"1"` の場合、既存のキャッシュ CLI 指定がある場合、実行ファイルが未対応の場合、または計算値が閾値を超えない場合は、この追加予算ログは出ない（`terminal/serve/server.py:3860-3867`、`terminal/strata_control/conversation_cache_size.py:88-102`）。

この変数によってサーバーが変えるのは起動引数の自動追加だけである。キャッシュの実使用量、会話の保持・退避や生成 token への影響は、この読み取り箇所からは決まらず、エンジン側の処理であるため本書では断定しない。

## 根拠

- `terminal/strata_control/conversation_cache_size.py:85-102` — 環境値判定、自動予算計算、引数追加と告知。
- `terminal/strata_control/conversation_cache_size.py:45-82` — CLI 既指定の判定、RAM・モデルサイズの取得。
- `terminal/serve/server.py:3734-3744,3834-3836,3860-3867` — 対象経路、専用エンジン経路の早期 return、対応実行ファイルの確認と予算関数呼び出し。
- `terminal/serve/server_parts/engines.py:931-945` — 実行ファイルのオプション文字列確認。
- `terminal/serve/server.py:877-879,8965-8966` — サーバーが生成引数をエンジン子プロセスへ渡す箇所。
