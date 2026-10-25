# `STRATA_LIFELINE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

サーバーが起動した子プロセスをサーバー終了時に終了させる仕組みを選びます。値が `watcher` の場合、Linux でも portable watcher 経路を強制します。これは Linux の `PR_SET_PDEATHSIG` 経路を切り替えるもので、子プロセスの通常の実行モードや Strata engine の計算設定を選ぶものではありません。

## 値と判定

モジュール読み込み時に `os.environ.get("STRATA_LIFELINE") or ""` の結果へ `.strip().lower()` を適用し、`MODE` に一度保存します。判定は正規化後の文字列と厳密に `watcher` を比較します。

| 環境値 | `MODE` | Linux で libc の `prctl` が利用可能な場合 |
|---|---|---|
| 未設定または空文字 | `""` | `pdeathsig` |
| 空白のみ | `""` | `pdeathsig` |
| `watcher`（大小文字不問、前後空白は除去） | `"watcher"` | `watcher` |
| その他（例: `1`, `true`, `watcher-x`） | その正規化文字列 | `pdeathsig` |

数値変換や真偽値判定はありません。Windows では `mechanism()` が先に `os.name == "nt"` を判定して `job` を返すため、この環境変数は機構選択に影響しません。Linux 以外、および Linux でも libc のロードまたは `prctl` 属性設定に失敗した場合は `watcher` になります。値の読み取り・正規化・`LINUX` の判定は Python モジュール import 時に一度だけ行われ、同一プロセスで後から環境を書き換えても `MODE` は更新されません。

## 有効になる条件

- 対象は `serve.lifeline` の `mechanism()` を経由して起動されるプロセスです。サーバーの `popen()` ラッパー、画像 encoder、MCP 子プロセスがこの経路を使います。
- Linux で libc の `prctl` が利用できる場合に限り、正規化後の値が `watcher` なら `pdeathsig` の代わりに watcher を使います。
- Windows では job object、他の POSIX 系 OS では watcher が選ばれます。これらの環境では `STRATA_LIFELINE` の値による差はありません。
- `watcher` 経路の起動に失敗しても、watcher の `Popen` で `OSError` が起きた場合は `_watch()` が戻るだけで、子プロセス起動そのものは失敗扱いになりません。

## 実行時の詳細

`popen()` は `mechanism()` の結果に応じて処理します。Linux の `pdeathsig` 経路では、長寿命の anchor thread から子プロセスを起動し、子側の `preexec_fn` が `PR_SET_PDEATHSIG` に `SIGKILL` を設定します。portable watcher 経路では子プロセスの PID と開始時刻を `ps` で取得し、親プロセスとの pipe が閉じると watcher が同じプロセスであることを確認して `SIGTERM`、必要なら最大約10秒後に `SIGKILL` を送ります。通常終了時には reaper が子を回収した後 watcher を release します。

この変数自体についてのログ出力はありません。watcher のプロセス起動に失敗した場合も明示的な警告は出しません。環境変数は起動する watcher に明示的に設定し直されず、通常の `subprocess.Popen` の環境継承に従います。

## 根拠

- `serve/lifeline.py:31-42` — 環境値の読み取り、正規化、Linux 判定と libc `prctl` のロード。
- `serve/lifeline.py:177-184` — OS・libc・`MODE` による機構選択。
- `serve/lifeline.py:83-91, 145-153, 156-173` — pdeathsig 設定、watcher 起動、release の処理。
- `serve/lifeline.py:235-269` — 機構選択結果に基づく子プロセス起動と追跡。
- `serve/server.py:88-99`, `serve/images.py:232-239`, `serve/mcp.py:95-109` — サーバー、画像 encoder、MCP 子プロセスから lifeline を使う呼び出し。
- `serve/test_lifeline.py:104-106` は `watcher` 値をテストで使う例だが、動作説明の根拠には本番実装を用いた。
