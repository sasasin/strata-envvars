# `STRATA_DROP_CACHE_ON_EXIT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のサーバープロセスが engine を強制終了する特定の終了経路で、モデルファイルに対して `posix_fadvise(..., POSIX_FADV_DONTNEED)` を要求します。対象はモデルファイルのページキャッシュであり、ファイルの内容を書き換えたり削除したりする処理ではありません。通常の engine 終了時に毎回実行する設定ではありません。読み取りと処理は Python サーバーの `serve.cache_drop` にあり、engine 内部の設定ではありません（`terminal/serve/cache_drop.py:14-16,36-69`）。

## 値と判定

Python サーバーが `os.environ` から値を取得し、前後の空白を `strip()` で除き、`lower()` で小文字化した文字列全体を `"1"`、`"true"`、`"yes"`、`"on"` のいずれかと比較します。数値変換はしません。変数が未設定なら空文字列が使われ、明示的な空文字や空白だけの値も無効です。大文字小文字は区別せず、前後の空白は無視します。その他の文字列は無効です（`terminal/serve/cache_drop.py:14-16`）。

| 条件 | 未設定 | 有効になる値の例 | 無効になる値の例 |
| --- | --- | --- | --- |
| `os.name != "nt"` | 無効 | `1`, `TRUE`, ` yes `, `on` | 空文字、空白のみ、`0`, `0anything`, `2`, `true0`, `false`, `y` |
| `os.name == "nt"` | 無効 | なし | すべての値（設定値を比較する前に無効） |

CLI 引数や設定ファイルによる上書きはありません。`enabled()` を呼ぶたびにサーバープロセスの環境を参照し、値を static 変数などへ保存しません。したがって、判定時点の `os.environ` の値が使われます（`terminal/serve/cache_drop.py:14-16,57-60`）。

## 有効になる条件

- `strata serve` のサーバー終了処理で、engine の `close()` などを実行中に二度目の Ctrl+C が入り、その `KeyboardInterrupt` を捕捉した経路であること。最初の Ctrl+C は drain と終了処理を開始しますが、通常の `close()` が完了する場合、この変数による処理は呼ばれません（`terminal/serve/server.py:9234-9237,9258-9271`）。
- その捕捉箇所で `engine.proc` が存在し、サーバーが engine に `kill()` を要求していること。`drop_after_exit()` は有効値かつ engine のプロセスが終了済みの場合にだけ続行し、まだ実行中なら待機・再試行をせず `0` を返します（`terminal/serve/server.py:9264-9270`; `terminal/serve/cache_drop.py:57-63`）。
- Windows (`os.name == "nt"`) では無効です。POSIX 系 OS でも `os.posix_fadvise` がなければ対象ファイルへの助言は行わず、処理件数 `0` になります（`terminal/serve/cache_drop.py:14-16,36-40`）。
- CUDA/HIP/SYCL、GPU 世代、モデル形式による値判定の分岐はありません。対象ファイルのパスは engine の起動引数 `--native`、`--pack`、`--mmproj`、`--model` から選びます（`terminal/serve/cache_drop.py:64-68`）。

## 実行時の詳細

二度目の Ctrl+C を終了処理中に受けると、サーバーは engine に `kill()` を要求してから `drop_after_exit(engine)` を呼びます。変数が有効で engine が終了済みなら、起動時の引数から `--native`、`--pack`、`--mmproj`、`--model` の値をパスとして集めます。いずれも得られない場合は `engine.model_path` を使います。指定パスが通常ファイルならそのファイル、ディレクトリなら再帰的に列挙した通常ファイルが対象です。存在しないパスや列挙時の `OSError` は飛ばします（`terminal/serve/cache_drop.py:19-33,57-68`）。

各ファイルを読み取り専用で開き、ファイル全体（offset と length を `0`）に `POSIX_FADV_DONTNEED` を要求します。ファイルを開けない場合や助言 API が `OSError` を返す場合、そのファイルは成功件数に含めません。これはカーネルへの助言であり、実際にキャッシュから解放された量を Strata が確認する処理はありません（`terminal/serve/cache_drop.py:36-54`）。

この名前は `engine/src/core/expert_source.cpp:216` にもありますが、これは Linux の resident-memory 安全確認が失敗し、ファイルキャッシュとバッファの合計が 1 GiB 以上の場合にエラーへ付加される案内文の一部です。同箇所はこの環境変数を読まず、サーバー側の処理を起動しません（`engine/src/core/expert_source.cpp:208-217,4201-4216`）。

## ログと測定値

有効値で、engine が終了済みとして処理を進めた場合は、助言に成功したファイル数にかかわらず stdout に `[strata] STRATA_DROP_CACHE_ON_EXIT: released the page cache of {n} model files` を出します。設定が無効、Windows、または engine がまだ動いている場合はこのログを出しません。終了処理で helper が例外を送出した場合、サーバーは `[strata] could not release the model files' cache: {e}` を出して終了を続けます（`terminal/serve/cache_drop.py:57-69`; `terminal/serve/server.py:9264-9271`）。この変数による性能測定値はありません。

## 根拠

- `terminal/serve/cache_drop.py:14-16` — OS 条件、環境値の正規化と許可値。
- `terminal/serve/cache_drop.py:19-54` — モデルファイル列挙、ファイル単位の助言と件数。
- `terminal/serve/cache_drop.py:57-69` — engine 終了確認、対象パス選択、ログ。
- `terminal/serve/server.py:9234-9237,9258-9271` — Ctrl+C を受けたサーバーの終了処理と呼び出し条件。
- `terminal/serve/server.py:2879-2921` — 通常の engine `close()` が終了を待ち、終了後に process 参照を片付ける処理。
- `engine/src/core/expert_source.cpp:208-217,4201-4216` — Linux のメモリ安全確認エラーに付く案内文。環境変数の読み取り箇所ではない。
