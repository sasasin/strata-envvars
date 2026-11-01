# `STRATA_DROP_CACHE_ON_EXIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

サーバーが engine を終了させた後、起動時に指定されたモデル関連ファイルについて `os.posix_fadvise(..., POSIX_FADV_DONTNEED)` で page cache の破棄を要求する opt-in です。アドバイス呼び出しが例外なく戻ったファイル数を `[strata] STRATA_DROP_CACHE_ON_EXIT: released the page cache of N model files` と標準出力に出します。このログは実際に cache が破棄されたことを検証していません。これはサーバー側の処理であり、engine の環境変数として読み込まれたり、通常の終了時に常に実行されたりするものではありません。

## 値と判定

値は `serve/cache_drop.py` の `enabled()` が呼ばれる時点で `os.environ` から取得されます。文字列の前後空白を除き、小文字化した結果を完全一致で判定します。

| 値 | 判定（Windows 以外） |
|---|---|
| 未設定 | 無効 |
| 空文字、空白のみ | 無効 |
| `1`, `true`, `yes`, `on`（大文字小文字不問、前後空白可） | 有効 |
| その他（例: `0`, `false`, `2`, `onward`） | 無効 |

Windows (`os.name == "nt"`) では値にかかわらず無効です。数値変換は行いません。CLI 引数や設定ファイルによる上書きは、この判定にはありません。関数は production 経路では引数 `env` を省略して `os.environ` を使い、値を static cache せず呼び出しごとに判定します。

## 有効になる条件

- `serve/server.py` の終了処理中に、engine の `close()` が KeyboardInterrupt（コード上のコメントでは二度目の Ctrl+C）を受ける。
- その時点で `engine.proc` が truthy である。server は engine process を `kill()` した後に helper を呼びます。
- `enabled()` が有効と判定する。Windows では有効化されません。
- `drop_after_exit()` の確認時に engine がまだ実行中でない。`proc` があり `proc.poll() is None` なら処理せず 0 を返します。kill 後に wait はしないため、poll が終了前を返す競合では cache 処理をせず、成功ログも出ません。

通常に `close()` が完了する終了経路では helper の呼び出しがありません。Linux の engine 側には、resident-memory 安全性チェック失敗時、`/proc/meminfo` の `Cached + Buffers` が 1 GiB 以上ならこの変数を案内する文言がありますが、engine はこの環境変数を読み取らず、その文言はキャッシュ解放処理を実行しません。

## 実行時の詳細

終了処理の close ループで `engine.close()` が KeyboardInterrupt を受けると、server は engine を kill し、`serve.cache_drop.drop_after_exit(engine)` を呼びます。helper は `engine.spawn` の引数列から `--native`, `--pack`, `--mmproj`, `--model` の直後の値をファイル／ディレクトリ候補として集めます。候補がなければ `engine.model_path` を使います。対象が通常ファイルならそのファイル、ディレクトリなら配下を再帰走査した通常ファイルを処理します。存在しないパス、アクセス時の `OSError`、開けないファイルは飛ばします。

各ファイルを読み取り専用で開き、利用可能な `os.posix_fadvise` に offset 0、length 0、`POSIX_FADV_DONTNEED`（属性がなければ値 4）を渡します。この API がなければ 0 を返します。アドバイス呼び出しの `OSError` は無視され、呼び出し成功数をログに出します。処理の例外は server 側で捕捉され、`[strata] could not release the model files' cache: ...` と出力されます。server の終了処理を止めないよう例外は再送出されません。

## 根拠

- `serve/cache_drop.py:14-16` — OS 条件、未設定時の空文字 fallback、strip/lower 後の許可値との完全一致。
- `serve/cache_drop.py:19-33,36-54` — モデルファイル列挙、posix_fadvise 呼び出し、ファイルごとの失敗処理。
- `serve/cache_drop.py:57-70` — engine 生存確認、spawn 引数からのパス抽出、fallback、ログ。
- `serve/server.py:9560-9574` — 終了時の close ループ、割り込み時の kill と helper 呼び出し、例外ログ。
- `serve/server.py:1017-1023` — `StrataEngine.spawn` の引数保持と `model_path` の設定。
- `serve/server.py:2628-2650` — engine の通常終了、terminate/kill 待ちを行う `close()`。この通常完了経路から cache helper は呼ばれません。
- `src/core/expert_source.cpp:195-205,3655-3678` — Linux のメモリ不足メッセージに出る案内文。ここでは変数を読む処理や cache 解放はありません。
- `setup.py:253` — リリース履歴の記載のみ。実行時判定の根拠にはしていません。
