# `STRATA_OOMD_ROOM`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

サーバーがエンジンを起動する直前に、モデルファイルを含むファイルキャッシュを解放する `oomd_pacer.make_room()` を無効化する。厳密に `"0"` を指定したときだけ、この事前処理を止める。無効化しても、エンジン起動や別処理の `STRATA_OOMD_PACER` によるメモリ圧力調整はこの変数では止めない。呼び出しは `terminal/serve/server.py:823-836`、判定は `terminal/serve/oomd_pacer.py:380-396`。

## 値と判定

`make_room()` が呼ばれるたび、引数 `environ` が省略されているためサーバープロセスの `os.environ` から取得し、値全体を文字列 `"0"` と比較する。数値変換や真偽値変換はしない。未設定・空文字・`"1"`・`"true"`・`"false"`・`"00"`・`"0anything"`・`" 0"` はいずれもこの判定では無効化値ではなく、処理を続ける。大文字小文字の違いも一致しない。`terminal/serve/oomd_pacer.py:380-393`。

| 実行経路 | unset | キャッシュ解放を止める値 | 止めない値 |
|---|---|---|---|
| Linux / その他の OS、サーバーのエンジン起動前 | 処理を続ける | 完全一致の `0` | 空文字、`1`、`true`、`false`、`00`、`0anything`、空白付き ` 0` など |

この値判定の既定は「無効化しない」だが、実際にキャッシュ解放するかは OS、実行環境、メモリとモデルファイルの状態、および `os.posix_fadvise` の利用可能性にも依存する。CLI 引数や他の設定値によって `STRATA_OOMD_ROOM` の判定値を上書きする処理はない。`terminal/serve/oomd_pacer.py:391-424`。

## 有効になる条件

値が `"0"` 以外でも、次の条件を満たさなければキャッシュ解放は行わない。

- サーバーがエンジンを起動する経路を通ること。`make_room(args)` は `Popen` の前に呼ばれる。`terminal/serve/server.py:823-836`
- `sys.platform` が Linux で、`os.POSIX_FADV_DONTNEED` が存在すること。前者はデスクトップ経路の適用判定に使われ、後者が無ければ `make_room()` は理由 `turned off` で終了する。`terminal/serve/oomd_pacer.py:95-100, 134, 391-392`
- 通常のデスクトップ経路では、プロセスが `user@UID.service` の cgroup 配下にあり、その `memory.pressure` を読め、`systemd-oomd` が active で、対象 manager の `ManagedOOMMemoryPressure` が `kill` であること。満たさなければ `applicable()` は適用先を返さず、コンテナ経路でもなければ何もしない。`terminal/serve/oomd_pacer.py:53-65, 68-78, 95-115, 391-396`
- `applicable()` が適用先を返さない場合でも、Linux のコンテナと判定されればコンテナ経路を使う。この経路は `/proc/meminfo` の `Cached` を見て処理する。コード上、この分岐自体には `systemd-oomd` の active 判定はない。`terminal/serve/oomd_pacer.py:353-358, 393-406`
- 選んだキャッシュ量が 1 GiB 以上で、エンジン引数から得た既存ファイルの合計サイズが正であり、空きメモリが十分でないこと。通常経路では cgroup の `file` cache が 1 GiB 以上かを確認し、空きメモリがファイル合計の 0.8 倍以上なら何もしない。コンテナ経路では `/proc/meminfo` の `Cached` が 1 GiB 以上かを確認し、空きメモリがファイル合計の 1.1 倍以上なら何もしない。対象ファイルは絶対パスの引数にあるファイルとフォルダー内のファイルなどで、走査上限は 200,000 件。`terminal/serve/oomd_pacer.py:124-128, 265-293, 397-419`

通常経路でもコンテナ経路でも、条件が不足するときは `make_room()` は 0 を返し、例外も握りつぶして起動失敗にしない。`terminal/serve/oomd_pacer.py:386-396, 407-441`。

関連する別変数として、`STRATA_OOMD_DEBUG=1` は `make_room()` の理由ログを有効にし、`STRATA_OOMD_PACER=0` は通常デスクトップ経路の `applicable()` を無効にする。`STRATA_OOMD_TRIM=0` は起動後のペーサーによるファイルキャッシュ整理対象を空にする。これらは `STRATA_OOMD_ROOM` の値比較とは別の判定である。`terminal/serve/oomd_pacer.py:95-100, 380-394, 384, 589-591`。

## 実行時の詳細

`make_room(args)` は各エンジン起動の `Popen` 前に同期的に実行される。環境変数を関数内やモジュール内にキャッシュしていないため、プロセス環境が起動間に変更されれば次の呼び出しで再評価される。モデル引数から対象ファイルを列挙し、通常経路では manager cgroup の `memory.stat` の `file`、コンテナ経路では `/proc/meminfo` の `Cached` と `/proc/meminfo` の `MemFree` を使って必要性を判定する。`terminal/serve/server.py:823-836`; `terminal/serve/oomd_pacer.py:380-424`。

必要と判断したファイルについて、Strata は `os.open(..., O_RDONLY)` 後に `os.posix_fadvise(fd, 0, 0, _DONTNEED)` を呼ぶ。失敗したファイルは数えずに進み、処理全体の例外も捕捉して起動を続ける。PLE テーブルを保持する設定・モデルでは該当 shard を対象から除外する。少なくとも 256 MiB 解放したと算出された場合にだけ成功ログを出す。`terminal/serve/oomd_pacer.py:296-318, 328-339, 420-441`。

環境変数は親サーバープロセス側の `os.environ` から読まれる。子エンジンへ渡す環境 `env` は `Popen` に渡されるが、`make_room()` には渡されない。`terminal/serve/server.py:823-829`; `terminal/serve/oomd_pacer.py:380-393`。

## ログと測定値

`STRATA_OOMD_DEBUG` が完全一致で `"1"` の場合に限り、何もしなかった理由などを stdout に `[strata] memory guard (debug): make_room: ...` の形で出す。`STRATA_OOMD_ROOM=0` の場合の本文は `turned off`。デバッグが無効なら理由ログは出ない。`terminal/serve/oomd_pacer.py:384-392`。

算出された解放量が 256 MiB 以上なら、`[strata] memory guard: freed <量> of memory that still held copies of this model's files from an earlier start, so that loading does not run short of memory and this desktop (systemd-oomd) does not end it`（通常経路）、または末尾が `a memory guard of this computer (such as systemd-oomd) does not end the container`（コンテナ経路）のログを stdout に出す。それ未満では成功ログは出ない。`terminal/serve/oomd_pacer.py:127, 433-438`。

## 根拠

- `terminal/serve/oomd_pacer.py:380-393` — 環境変数の読み取り、厳密な `"0"` 判定、適用処理への分岐。
- `terminal/serve/server.py:823-836` — エンジンの各起動前後での呼び出し順。
- `terminal/serve/oomd_pacer.py:95-115, 353-358, 391-419` — Linux、systemd-oomd、コンテナ、キャッシュ量・空きメモリによる適用条件。
- `terminal/serve/oomd_pacer.py:265-293, 296-318, 328-339, 420-441` — 対象ファイル、PLE shard の除外、キャッシュ解放と失敗時の扱い。
- `terminal/serve/oomd_pacer.py:124-128, 384-392, 433-438` — 閾値、デバッグ理由ログ、成功ログ。
