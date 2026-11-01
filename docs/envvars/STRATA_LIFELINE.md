# `STRATA_LIFELINE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

serve プロセスが起動した子プロセスを、serve が異常終了した場合に終了させる仕組みを選びます。Linux で `STRATA_LIFELINE=watcher` を指定すると、既定の `PR_SET_PDEATHSIG` 経路を避けて watcher 経路を使います。Windows ではこの値にかかわらず job object 経路です。

serve は `serve/lifeline.py` を import し、engine などの起動を `lifeline.popen()` に渡します。画像 encoder と MCP 子プロセスも同じ関数を呼びます（`serve/server.py:84,94-100`; `serve/images.py:234-237`; `serve/mcp.py:37,108-110`）。

## 値と判定

モジュール読み込み時に `os.environ.get()` で取得し、空値を `""` に置き換えた後、前後空白を除去して小文字化します。数値変換や真偽値 parse はしません。方式選択で特別扱いするのは正規化後の文字列が `watcher` と完全一致する場合だけです（`serve/lifeline.py:33-35,215-221`）。

| 環境値 | Linux（`prctl` 利用可能） | Windows | その他の OS / Linux で `prctl` 利用不可 |
|---|---|---|---|
| 未設定、空文字、空白だけ | `pdeathsig` | `job` | `watcher` |
| 前後空白・大文字小文字を除いて `watcher` | `watcher` | `job` | `watcher` |
| 上記以外の値（例: `1`, `true`, `0`, `off`） | `pdeathsig` | `job` | `watcher` |

空文字や空白だけの値は未設定と同じ既定経路です。`WATCHER` や ` watcher ` は `watcher` として扱われます。Windows では値を読み取りますが方式判定が先に `job` を返すため、設定値は方式に影響しません（`serve/lifeline.py:34-44,215-221`）。

## 有効になる条件

- 値を読むのは `serve.lifeline` の import 時です。`MODE` はモジュール変数として保持され、CLI 引数や設定ファイルとの優先順位はありません。実行中に環境を変更しても再評価されません（`serve/lifeline.py:33-35`）。
- Linux の既定 `pdeathsig` 経路には、Linux 判定に加えて `ctypes.CDLL(None)` と `prctl` 属性の取得が成功して `_libc` が非 `None` であることが必要です。失敗した場合は watcher 経路になります（`serve/lifeline.py:34-44,215-221`）。
- `watcher` が方式を変えるのは Linux で `prctl` が利用可能な場合だけです。Windows は job object、その他の OS は watcher を選びます（`serve/lifeline.py:215-221,283-298`）。
- `popen()` は方式を選んだ後に子を起動します。engine / vision role は POSIX で独立した process group にも設定されますが、MCP 起動側は `start_new_session=True` を渡します。これらは lifeline 方式の選択とは別の処理です（`serve/lifeline.py:262-270,283-298`; `serve/mcp.py:103-110`）。

## 実行時の詳細

Linux の `pdeathsig` 経路では、専用の長寿命 anchor thread 上で子を起動し、`preexec_fn` から `prctl(PR_SET_PDEATHSIG, SIGKILL, ...)` を設定します。fork と設定の間に親 PID が変わっていれば、その子自身に `SIGKILL` を送ります。`prctl` の戻り値はこのコードでは検査しません（`serve/lifeline.py:49-70,85-93,289-292`）。

watcher 経路では子を起動後、子の PID と開始時刻 token を監視する別プロセスを起動します。親との pipe が閉じると、watcher は token が同じ子に `SIGTERM` を送り、最大 10 秒待って同じプロセスが残っていれば `SIGKILL` を試みます。通常の子終了時は reaper が watcher に終了 byte を送って監視を解除します（`serve/lifeline.py:98-146,152-179,181-210,294-304`）。

この名前に関するログ出力や警告はありません。watcher の起動が `OSError` で失敗した場合 `_watch()` は何も記録せず戻り、その子に watcher は登録されません。また token が空、または watcher が終了時に同じ PID・開始時刻の子と確認できない場合は子へ終了シグナルを送りません（`serve/lifeline.py:181-192,132-145`）。親子の起動自体に失敗した場合は通常の `Popen` 例外となり、serve server のラッパーは Windows の特定エラーを説明付き `OSError` に変換し、それ以外は再送出します（`serve/lifeline.py:289-298`; `serve/server.py:94-106`）。

通常の停止要求を graceful shutdown に渡す signal handler は別途インストールされ、`STRATA_LIFELINE` による分岐はありません（`serve/server.py:9059-9066`; `serve/lifeline.py:315-358`）。

## 根拠

- 環境値の読み取り・正規化: `serve/lifeline.py:33-35`
- Linux の `prctl` 利用可否と方式選択: `serve/lifeline.py:34-44,215-221`
- anchor、`PDEATHSIG`、方式ごとの子起動: `serve/lifeline.py:49-93,262-304`
- watcher の終了検知・解放: `serve/lifeline.py:98-210`
- server、画像 encoder、MCP からの利用: `serve/server.py:84,94-100`; `serve/images.py:234-237`; `serve/mcp.py:37,108-110`
- サーバー強制終了時の OS 別方式の説明: `docs/CLOSING.md:36`
