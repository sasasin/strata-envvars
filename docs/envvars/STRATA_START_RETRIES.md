# `STRATA_START_RETRIES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の Python サーバーが engine を起動したとき、GPU runtime の一時的な初期化失敗と判定した早期終了を再試行する回数です。既定値は 3 回で、初回起動を含め最大 4 回の起動を行います。これは一般の起動失敗すべてや、engine の実行中に起きたクラッシュを再試行する設定ではありません。読み取りと再試行は `serve/server.py` の `StrataEngine` にあり、engine 本体や one-shot CLI の環境変数ではありません（`serve/server.py:658-663,1017-1019,1126-1141`）。

## 値と判定

`serve/server.py` の import 時に `os.environ.get("STRATA_START_RETRIES", "3") or 0` を `int()` に渡し、結果を 0 以上に clamp します（`serve/server.py:663`）。

| 環境値 | 判定 |
| --- | --- |
| 未設定 | 既定文字列 `"3"` を整数化し、3 回再試行 |
| 空文字 | `or 0` により整数 0。再試行なし |
| 整数として読める値 | `int()` の結果を使う。負数は 0 に clamp。正数 N は最大 N 回再試行 |
| 整数にできない文字列 | `ValueError` が import 時に発生し、サーバーモジュールの読み込みに失敗する。fallback はない |

Python の `int()` による変換なので、小数表記（例 `1.5`）は受け付けず、符号付き整数や前後の空白は整数化されます。上限は設定されていません。`START_RETRIES` はモジュール定数であり、実行中に環境を変更しても再読込されません。CLI 引数、設定ファイル、別の環境変数による上書きはありません（`serve/server.py:663`）。

## 有効になる条件

値の変換自体は `serve.server` の import 時に行われるため、同モジュールを使う `--engine mock` や lazy 起動でも無効な文字列なら import が失敗します。一方、実際の再試行処理は `StrataEngine` が engine を spawn した後に限られ、OS/backend/build macro による分岐はありません。初回起動が `lazy=True` なら constructor は engine を spawn せず戻るため、その段階では再試行は起きません。後で起動する際は通常の constructor 経路に入ります（`serve/server.py:1017-1018,1043-1045`）。

再試行は次の条件をすべて満たす場合に限られます。

- engine が `READY` を報告せずに終了した。READY 待ち timeout の場合は再試行しない（`serve/server.py:1085-1100,1111-1127`）。
- その起動の経過時間が 30 秒以内で、ログファイルが指定されている（`serve/server.py:666-677`）。
- ログに `hsa_exception`、`HSA_STATUS_ERROR`、`hsaKmt` のいずれかがある場合、engine 自身の `[strata]` 行以外は `terminate called`、`what()`、または上記 runtime マーカーを含む行だけである。マーカーがない場合は、engine 自身の行が一つもなく、終了コードが 1 でなく、signal/NTSTATUS でのシステムクラッシュでもないこと（`serve/server.py:678-687`）。ログは起動位置から最大 64 KiB だけ読みます（`serve/server.py:673-680`）。

これはコメントが ROCm の queue teardown 競合を主な例として挙げるものの、実装上は ROCm 専用ではありません。ログ条件に一致する起動なら他 backend でも同じ判定を通ります（`serve/server.py:658-663,666-687`）。

## 実行時の詳細

初回起動からの試行番号 `_attempt` は 0 で始まります。再試行可能な失敗では待ち時間を `2 * 2**_attempt` 秒（2、4、8 秒…）とし、次の engine start を再帰的に呼び出します。したがって N 回の再試行を使い切る場合、最後の失敗までの待ち時間合計は `2 + 4 + ... + 2**N` 秒です（`serve/server.py:1126-1141`）。

runtime のエラー文字列がログで確認できた場合、サーバー標準出力に `[strata] the engine stopped while the GPU runtime was starting ...: starting it again in ... s (try X of Y)` を出します。ログが無言の終了の場合は「it may be a GPU runtime that was not ready yet」として再試行を通知します（`serve/server.py:1130-1139`）。再試行条件を満たさない、または回数を使い切った場合は `EngineDied` を送出し、READY 前終了または READY timeout の説明、ログ位置、終了情報とログ末尾を付けます（`serve/server.py:1143-1153`）。

engine が運転中に落ちて server の `restart()` が呼ばれる場合には、別途 `tries=3` の再起動ループと固定 `RESTART_RETRY_S` 待ちがあります。各 `__init__` の起動が上記の一時的失敗条件に合えば `STRATA_START_RETRIES` の再試行も働きますが、この環境変数は `restart()` の `tries` 自体を変更しません（`serve/server.py:1335-1362`）。

## 根拠

- 候補一覧には名前があります（`docs/envvars/000_envvers.md:1529`）。Strata 所有ソースでの実参照は `serve/server.py:663` の環境読み取りのみで、その値を使う箇所は同ファイルの `1126-1141` です。コメント内の記載は `658-662` です。
- 適用される失敗判定とログ条件: `serve/server.py:644-687`。
- spawn と READY 待ち、最終的な失敗経路: `serve/server.py:1043-1089,1111-1153`。
- 通常の再起動 retry ループとの関係: `serve/server.py:1335-1362`。
- `docs/DETAILS.md` の設定キー一覧（`457-489`）にはこの変数の説明はありません。
