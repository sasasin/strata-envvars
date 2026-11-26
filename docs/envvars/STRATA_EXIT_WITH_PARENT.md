# `STRATA_EXIT_WITH_PARENT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

親プロセスが終了したときに App Host、Control CLI、または準備ツールを停止させるためのプロセス間引き継ぎ値。モデル計算や GPU backend は制御しない。App Host は値が厳密に `1` の場合に親を監視し、消失後は通常の `shutdown()` に入る。Python Control は `1` で直接の親を監視し、準備ツールは `1` または PID を監視対象にする。`setup.run()` は準備ツールの子プロセスに setup 自身の PID を設定して渡す（`app/host/server/index.mjs:2594-2603`、`terminal/strata.py:38-42`、`terminal/strata_control/parentwatch.py:15-23`、`terminal/tools/exit_with_parent.py:12-25`、`terminal/setup.py:1131-1150`）。

## 値と判定

読み取り側ごとに規則が異なる。共通の boolean parser は使われていない。

| 読み取り側 | 未設定・空文字 | 有効になる値 | 無効値・境界の扱い |
|---|---|---|---|
| App Host | 監視しない | 文字列全体が厳密に `1` | `0`、`true`、` 1`、`1 `、空文字などは無効。trim・数値変換なし。大文字小文字の問題はない（`app/host/server/index.mjs:2596`）。 |
| Control CLI (`parentwatch.exit_with_parent`) | 監視しない | 前後空白を `strip()` した結果が `1` | `0`、PID、`true`、空文字などは無効。値全体で比較する（`terminal/strata_control/parentwatch.py:15-23`）。 |
| `tools/exit_with_parent.py`、`tools/mtp_fetch.py` | 監視しない | `strip()` 後が `1`、または `isdigit()` が真で `int()` に変換できる PID 文字列 | `true`、`+123`、`-123` などは無効。`1` は PID 1 ではなく直接の親を意味する。変換後 PID が `1` 以下または自身の PID なら監視しない。PID の上限 clamp はない（`terminal/tools/exit_with_parent.py:15-24`、`terminal/tools/mtp_fetch.py:247-255`）。 |
| `setup.run()` の子向け環境 | 未設定なら setup 自身の PID を設定 | `strip()` 後が数字のみで `1` 以外なら既存値を保持 | `1`、空文字、数字以外は setup 自身の PID に置換。`0` は保持されるが、上記ツール watcher は PID `0` を監視しない（`terminal/setup.py:1142-1149`、`terminal/tools/exit_with_parent.py:16-24`）。 |

Python 側は `strip()` するため前後空白を許すが、App Host は厳密一致で空白を許さない。Python の PID watcher は正の PID を数値変換し、文字列の全体を `isdigit()` で検査する。CLI 引数による上書きや別環境変数との優先順位はなく、各読み取り箇所は環境値だけを判定する。

## 有効になる条件

- App Host の watcher は、Node プロセス起動時に `process.env.STRATA_EXIT_WITH_PARENT === '1'` の場合に限り設定される。デスクトップ shell は Host 起動コマンドに `1` を明示設定する（`app/desktop/src-tauri/src/main.rs:522-540`、`app/host/server/index.mjs:2594-2603`）。
- `controlEnvironment()` は通常、親環境の複製を返すため、入力環境にこの変数があれば非 acquire 呼び出しでもその値を保持する。`acquire: true` のときは必ず `1` を設定し、同時に `STRATA_NO_ACQUIRE` を削除する。これを使う更新確認・更新・drafting fetch・pictures fetch の呼び出しで明示的に設定される（`app/host/server/control-runtime.mjs:88-107,140-146,284-300,402-405,424-429`）。
- Python Control 側では `strata.py` の起動直後に watcher 関数が呼ばれる。監視対象が直接の親なので、親が Host でなく別プロセスの場合も、その親の終了が条件になる。import や watcher 起動時の例外は握りつぶされ、CLI コマンド自体はこの理由で失敗しない（`terminal/strata.py:35-45`）。
- 準備ツールは watcher 関数を呼ぶ必要がある。`iq_pack.py` は処理本体の前、`mtp_fetch.py` は `verify` 以外の処理の前に呼ぶ。環境変数があっても関数を呼ばないツールには watcher は追加されない（`terminal/tools/iq_pack.py:612-620`、`terminal/tools/mtp_fetch.py:526-535`）。
- Windows では Python watcher が `OpenProcess(SYNCHRONIZE)` に失敗すると監視を開始しない。Python の非 Windows 実装は親 PID の変化を監視し、準備ツールは加えて対象 PID の生存を確認する（`terminal/strata_control/parentwatch.py:21-34`、`terminal/tools/exit_with_parent.py:25-44`、`terminal/tools/mtp_fetch.py:256-275`）。
- 親 PID が `1` 以下、または準備ツールで指定 PID が自身の PID と同じなら監視しない。App Host にはこの PID 条件はなく、現在の `process.ppid` を監視対象にする（`terminal/strata_control/parentwatch.py:21-23`、`terminal/tools/exit_with_parent.py:23-24`、`terminal/tools/mtp_fetch.py:254-255`、`app/host/server/index.mjs:2596-2602`）。

## 実行時の詳細

App Host はモジュール初期化時に値を一度判定する。有効なら、その時点の `process.ppid` を保存し、1 秒ごとの interval で親を確認する。親 PID が変化した場合、または `process.kill(parent, 0)` が `ESRCH` を返した場合に `shutdown()` を呼ぶ。shutdown は task timer と task queue を閉じ、HTTP server を閉じ、チャット保存を drain し、共有・native・agent 機能を停止して終了する。変数は実行中に再読されない（`app/host/server/index.mjs:2578-2603`）。

Python watcher は関数呼び出し時に環境値と親 PID を読み、daemon thread を起動する。Control の標準間隔は 1.5 秒。準備ツールも既定の poll 間隔 1.5 秒で、`tools/exit_with_parent.py` は Windows で同期ハンドルの終了を待ち、他 OS では直接の親変更を確認するほか、指定 PID の生存も調べる。`mtp_fetch.py` も同じ OS 分岐を持つ。開始後に環境を変更しても watcher の対象は変わらない（`terminal/strata_control/parentwatch.py:15-44`、`terminal/tools/exit_with_parent.py:12-54`、`terminal/tools/mtp_fetch.py:240-282`）。

親が終わると Python watcher は stderr への通知を試みた後 `os._exit(1)` で即時終了するため、通常の Python cleanup や出力 flush は行われない。`setup.run()` は子環境を複製・調整し、`subprocess.run(..., env=env)` で渡す。`check=True` で子が非ゼロ終了すると setup は `command failed (exit N): <コマンド名>` として失敗を報告する（`terminal/tools/exit_with_parent.py:36-54`、`terminal/tools/mtp_fetch.py:277-282`、`terminal/setup.py:1150-1156`）。

## ログと測定値

- App Host の親消失分岐には専用ログ出力がなく、`shutdown()` に進む（`app/host/server/index.mjs:2594-2603`）。
- Control watcher は `the program that started this one has ended: stopping` を stderr に書こうとし、準備ツール watcher は `the process that started this step has ended: stopping` を stderr に書こうとする。MTP fetch は `the process that started this download has ended: stopping` を stderr に flush してから終了する（`terminal/strata_control/parentwatch.py:36-43`、`terminal/tools/exit_with_parent.py:46-53`、`terminal/tools/mtp_fetch.py:277-282`）。
- Control と `exit_with_parent.py` は stderr 書き込み失敗を無視する。Host による終了にもこの値専用の文言はない。
- 性能・精度の測定値は該当しない。

## 根拠

- デスクトップから App Host への値設定: `app/desktop/src-tauri/src/main.rs:522-540`
- App Host の判定、監視、shutdown: `app/host/server/index.mjs:2578-2603`
- Control 子プロセス環境の組み立てと acquire 呼び出し: `app/host/server/control-runtime.mjs:88-107,140-146,284-300,402-405,424-429`
- Control CLI 起動時の watcher: `terminal/strata.py:35-45`、`terminal/strata_control/parentwatch.py:15-45`
- setup による子向け値の調整と終了報告: `terminal/setup.py:1131-1156`
- 準備ツール watcher と呼び出し箇所: `terminal/tools/exit_with_parent.py:12-54`、`terminal/tools/iq_pack.py:612-620`、`terminal/tools/mtp_fetch.py:240-282,526-535`
