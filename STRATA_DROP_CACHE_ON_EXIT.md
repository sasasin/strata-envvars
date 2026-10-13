# `STRATA_DROP_CACHE_ON_EXIT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

Strata の Python サーバーが停止するとき、エンジン終了後にモデルファイルのページキャッシュを返すよう OS に要求する opt-in 設定。サーバーが対象とする自分のモデルファイルだけに処理し、既定では実行しない。エンジンの通常の起動・推論処理を変更する変数ではない。

## 値と判定

`serve/cache_drop.py:14-16` で、環境変数の値から前後の空白を取り除き、小文字化した文字列を完全一致で判定する。

| 値 | 判定 |
|---|---|
| 未設定、空文字、空白だけ | 無効 |
| `1`、`true`、`yes`、`on`（大文字小文字は不問、前後の空白は除去） | Windows 以外で有効 |
| `0`、`false`、`no`、`off`、その他 | 無効 |
| 上記の有効値 | Windows (`os.name == "nt"`) では無効 |

`true` などは文字列全体で比較されるため、`1abc` や `yesplease` は有効にならない。Python サーバーが呼び出す `drop_after_exit` は通常 `env` 引数を渡さず、判定時の `os.environ` を参照する。import 時に値を固定する実装ではない。

## 有効になる条件

- サーバーの停止処理が `cache_drop.drop_after_exit(engine)` に到達すること。通常の起動中やリクエストごとには呼ばれない。
- `os.name != "nt"` であり、値が上表の有効値であること。
- エンジンプロセスがまだ動作中なら処理を中止する。停止処理で `engine.close()` がエンジンを終了させた後に呼ばれる。close が完了せずプロセスが残った場合にも、ページキャッシュ処理は行わない。
- 実行環境に `os.posix_fadvise` がなければ、対象ファイルへの助言は行われず処理件数は 0 になる。

## 実行時の詳細

サーバーは Ctrl+C または SIGTERM を Ctrl+C と同じ停止経路へ送り、HTTP サーバー、エンジンなどの close を試みた後で `drop_after_exit` を呼ぶ（`serve/server.py:6595-6622`）。close の処理は QUIT、terminate、kill の順でエンジン終了を試み、終了後は `proc` を `None` にする（`serve/server.py:1968-2003`）。`drop_after_exit` は `proc` が存在してなお実行中なら何もせず戻る（`serve/cache_drop.py:57-63`）。

対象パスは、エンジン起動引数の `--native`、`--pack`、`--mmproj`、`--model` に続く値。該当する引数がなければ `engine.model_path` を使う（`serve/cache_drop.py:64-68`。エンジンは起動引数とモデルパスを保持する: `serve/server.py:649-655`）。パスがファイルならそのファイル、ディレクトリなら配下の通常ファイルを再帰的に列挙し、存在しないパスやパス確認時の `OSError` は飛ばす（`serve/cache_drop.py:19-33`）。

各ファイルを読み取り専用で開き、ファイル全体を対象に `os.posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED)` を呼ぶ。助言呼び出しが `OSError` になったファイルは件数に加えず、正常に戻ったファイルを数える。これは OS へのキャッシュ破棄の助言であり、ページが実際に直ちに解放されたことを保証する確認処理ではない（`serve/cache_drop.py:36-54`）。有効値でエンジンが終了済みなら、最終的に `[strata] STRATA_DROP_CACHE_ON_EXIT: released the page cache of N model files` を出力する。サーバー側では予期しない例外も捕捉し、`[strata] could not release the model files' cache: ...` を出して終了を続ける（`serve/cache_drop.py:69`、`serve/server.py:6617-6622`）。

## 文書との照合

`docs/DETAILS.md:1837` は、モデルファイル読み込み後の OS キャッシュにより二度目の起動が速くなることを説明している。一方、今回確認した `docs/DETAILS.md` にはこの環境変数固有の説明は見当たらず、動作の根拠はサーバー実装と `serve/cache_drop.py` による。`src/core/expert_source.cpp:124-134` にも、Linux のモデル読み込み由来キャッシュについて起動時の案内文でこの設定を紹介する箇所があるが、実際の環境変数判定や解放処理は Python サーバー側にある。

## 根拠

- `serve/cache_drop.py:14-16` — 値と OS の判定
- `serve/cache_drop.py:19-54` — 対象ファイル列挙とページキャッシュへの助言
- `serve/cache_drop.py:57-70` — エンジン終了確認、対象パス決定、ログ
- `serve/server.py:649-655`, `1968-2003`, `6595-6622` — エンジン情報の保持、終了処理、サーバー停止時の呼び出し
- `src/core/expert_source.cpp:124-134` — 起動時案内文
- `docs/DETAILS.md:1837` — OS のページキャッシュに関する一般説明
