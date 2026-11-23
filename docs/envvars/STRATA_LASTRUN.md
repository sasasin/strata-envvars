# `STRATA_LASTRUN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Linux の実エンジンサーバー起動時に、前回サーバーの異常終了を示すマーカーを調べ、該当すれば理由を標準出力へ表示します。現在の実行についてユーザー状態ディレクトリにマーカーを作り、サーバーが通常終了すると削除します。起動ランナーも同じ前回マーカーから通知文を読み、画面や monitor に渡します。`STRATA_LASTRUN=0` はこのマーカー処理と通知を無効にします。モデル計算や CLI の起動条件そのものは変更しません。実装は `terminal/serve/lastrun.py` と `terminal/serve/server.py`、ランチャー側は `terminal/strata_cli/launch/runner.py` です（`terminal/serve/lastrun.py:87-110`, `terminal/serve/server.py:8472-8497`, `terminal/strata_cli/launch/runner.py:3038-3053`）。

## 値と判定

Python の `os.environ.get("STRATA_LASTRUN") == "0"` で文字列全体を比較します。数値変換、trim、大文字小文字変換はありません。未設定は `None`、空文字は `""` なので、どちらも無効化せず処理を有効にします。`"00"`、`"false"`、`" 0"` も無効化しません。CLI 引数や別の環境変数による上書き・優先順位はありません。

| 実行条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux の実エンジンサーバー (`--engine strata`) または Linux 起動ランナー | マーカー確認・通知を行う | 空文字、`1`、`00`、`false`、` 0` | 完全一致する `0` |
| Linux 以外、または実エンジン以外のサーバー | マーカー処理を行わない | 該当なし | 該当なし |

判定箇所はサーバーの `begin()` とランチャーの `say_last_run()` です（`terminal/serve/lastrun.py:87-92`, `terminal/serve/lastrun.py:31-39`, `terminal/strata_cli/launch/runner.py:3038-3047`）。

## 有効になる条件

- サーバー側では `sys.platform.startswith("linux")` であることと、引数に `--engine strata` または `--engine=strata` があることが必要です。`--engine mock` など実エンジン以外ではマーカーを作りません（`terminal/serve/lastrun.py:31-39`, `terminal/serve/lastrun.py:87-92`, `terminal/serve/server.py:8489`）。
- ランチャー側の前回通知も Linux でのみ読み、`start=True` で既存 serving 状態の再利用がなかった場合に `say_last_run()` を呼びます（`terminal/strata_cli/launch/runner.py:3038-3049`, `terminal/strata_cli/launch/runner.py:3151-3156`）。
- マーカーはプロファイルごとに分かれます。`STRATA_RUNTIME_PROFILE` がサーバーに渡されていない場合は `serve` が名前に使われます。ファイル名は `last-run-<profile>.json` で、プロファイル中の英数字・`-_.` 以外は `_` に置換し、80 文字までにします。保存先は `paths.state_base()` で、POSIX では `$XDG_STATE_HOME/strata`（未設定または空なら `~/.local/state/strata`）です（`terminal/serve/server.py:8489`, `terminal/serve/lastrun.py:42-47`, `terminal/strata_control/paths.py:13-21`）。
- 同一プロファイルの前回サーバーがまだ動作中と判定された場合、新しいマーカーに置き換えず、通知もしません（`terminal/serve/lastrun.py:58-64`, `terminal/serve/lastrun.py:93-103`）。

## 実行時の詳細

`begin()` はサーバーの `main()` で `_main()` に入る前に呼ばれます。前回マーカーを読み取れない、または JSON として不正なら前回情報なしとして続行し、現行サーバーの PID・プロセス開始 token・開始時刻・profile を一時ファイルへ書いて `os.replace()` します。通常の終了経路では `finally` から `end()` が呼ばれ、自分の PID のマーカーだけを削除します。強制終了などで `finally` が実行されずマーカーが残れば、次回起動時に前回終了を判定します（`terminal/serve/server.py:8489-8497`, `terminal/serve/lastrun.py:93-108`, `terminal/serve/lastrun.py:113-122`）。

前回マーカーの PID が正の整数で、現在のプロセス開始 token と保存 token が一致すれば、そのサーバーはまだ動作中とみなします。そうでなければ終了済みとして扱います。終了済みのマーカーに数値の `started` があれば、ユーザージャーナルにその時刻の5秒前以降の `systemd-oomd killed` 行があるかを `journalctl --user ... --since @<秒>` で最大5秒待って調べます。一致すれば OOMD 用の文、読めない・timeout・該当行なしなら一般的な異常終了文を選びます（`terminal/serve/lastrun.py:50-84`）。

環境変数は `begin()` とランチャーの `say_last_run()` が呼ばれるたびに読み、プロセス間で値を cache しません。実行中に値を変更した場合、すでに開始済みの `begin()` の分岐は変わりませんが、その後のランチャー呼び出しでは新しい値を評価します。ランチャーが前回文を読み取ってもマーカーを変更せず、サーバー側は独立して同じマーカーを確認します（`terminal/serve/lastrun.py:87-108`, `terminal/strata_cli/launch/runner.py:3038-3053`）。

## ログと測定値

前回マーカーがあり、そのプロセスが終了済みなら、サーバーは次のいずれかを標準出力に `flush=True` で出します。

- ジャーナルで `systemd-oomd killed` を確認した場合: `[strata] Last time, this computer's memory guard (systemd-oomd) ended Strata: it stops a program when memory has been under strain for 20 seconds, and loading a large model can do that. Strata now frees memory before the load and pauses it for a few seconds when memory gets tight. If it happens again: close other programs (a web browser uses a lot of memory) and start again, or start Strata from a text console or over ssh, which the memory guard does not watch.`
- それ以外: `[strata] Last time, Strata did not end normally (the window was closed hard, the power went off, or the computer ran out of memory). Your files are fine and this start goes on as usual. If it stops again while loading, close other programs and start again.`

ランチャー側は `[strata] ` を除いた同じ文を `level="warn"` の `note` として通知し、`Result.last_run` 経由で monitor に渡します（`terminal/serve/lastrun.py:23-28`, `terminal/serve/lastrun.py:101-104`, `terminal/strata_cli/launch/runner.py:3046-3053`, `terminal/strata_cli/launch/runner.py:3183-3187`, `terminal/strata_cli/launch/app.py:660-668`）。マーカー読み書き、ジャーナル確認、通知準備の例外は握りつぶされ、起動を失敗させません（`terminal/serve/lastrun.py:67-74`, `terminal/serve/lastrun.py:87-110`, `terminal/strata_cli/launch/runner.py:3042-3049`）。性能測定値は該当しません。

## 根拠

- 候補名の全参照は `terminal/serve/lastrun.py:91`、`terminal/strata_cli/launch/runner.py:3044`、テスト専用の設定例 `terminal/serve/test_lastrun.py:112`。実行時の挙動の根拠にはテストではなく前二者を使った。候補一覧への掲載は `docs/envvars/000_envvers.md:1331`。
- サーバーでの対象判定、マーカーの読み書き、通常終了時の削除: `terminal/serve/server.py:8472-8497`, `terminal/serve/lastrun.py:87-122`。
- 前回終了の判定、ジャーナル照会、表示文: `terminal/serve/lastrun.py:23-28`, `terminal/serve/lastrun.py:50-84`, `terminal/serve/lastrun.py:101-107`。
- ランチャー側の通知と monitor への受け渡し: `terminal/strata_cli/launch/runner.py:3038-3053`, `terminal/strata_cli/launch/runner.py:3151-3187`, `terminal/strata_cli/launch/app.py:660-668`。
- 状態ディレクトリ: `terminal/serve/lastrun.py:42-47`, `terminal/strata_control/paths.py:13-21`。
