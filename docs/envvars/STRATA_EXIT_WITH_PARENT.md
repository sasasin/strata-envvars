# STRATA_EXIT_WITH_PARENT

調査対象: Strata main の HEAD 73d4f4196c25a65e02f6b9ef25d354826ce55105（2026-11-23 時点）。

## 役割

親プロセスが終了したとき、App Host や長時間動く Control / 準備ツールを終了させるための内部引き継ぎ値。モデル計算や GPU backend の設定ではない。App Host は値が文字列 1 のとき親を監視し、親がなくなると通常の shutdown() を呼ぶ。Python 側の Control / ツールは 1 または PID を受け取り、親の終了を検出すると終了コード 1 で自身を止める。デスクトップ起動処理、Control の取得処理、準備ツール起動処理が子へ値を渡す（app/desktop/src-tauri/src/main.rs:522-540、app/host/server/control-runtime.mjs:88-107,140-146、terminal/setup.py:1131-1150）。

## 値と判定

読み取り側ごとに判定規則が異なり、共通の数値変換はない。

| 読み取り箇所 | 未設定 | 有効になる値 | 無効になる値・扱い |
|---|---|---|---|
| App Host (app/host/server/index.mjs) | 監視しない | 値が厳密に文字列 1 | 空文字、0、true、前後に空白のある 1 などは監視しない。trim や数値変換なし (app/host/server/index.mjs:2590-2597)。 |
| Control CLI (terminal/strata_control/parentwatch.py) | 監視しない | 前後空白を除いて 1 | 空文字、0、PID 数値、true などは監視しない。値全体が 1 と一致する必要がある (terminal/strata_control/parentwatch.py:15-23)。 |
| tools/exit_with_parent.py と tools/mtp_fetch.py | 監視しない | 前後空白を除いた 1、または isdigit() が真の文字列で表した PID | true、+123、-123、空文字などは監視しない。1 は実親 PID として扱い、他の数値文字列は int() で PID にする (terminal/tools/exit_with_parent.py:12-25、terminal/tools/mtp_fetch.py:240-256)。 |
| 準備子プロセスへ渡す値 (setup.run) | setup 自身の PID を設定して渡す | 既存値が空白除去後に数字のみで 1 以外なら、その値を保持 | 1、未設定、空文字、数字以外は setup 自身の PID に置換する。0 は setup では保持されるが、子側は PID 0 のため監視しない (terminal/setup.py:1141-1150、terminal/tools/exit_with_parent.py:16-25)。 |

PID を受け付ける Python 実装は、変換後の PID が 1 以下または自身の PIDなら監視しない。parentwatch.py も実親 PID が 1 以下なら監視しない。PID の上限 clamp はない (terminal/strata_control/parentwatch.py:19-23、terminal/tools/exit_with_parent.py:16-25、terminal/tools/mtp_fetch.py:247-256)。

## 有効になる条件

- App Host の親監視は、起動時の process.env.STRATA_EXIT_WITH_PARENT === '1' の場合だけ有効。デスクトップ shell は Node 起動コマンドに 1 を設定する (app/desktop/src-tauri/src/main.rs:522-540)。
- controlEnvironment() は acquire: true の呼び出しだけ STRATA_EXIT_WITH_PARENT=1 を設定する。該当するのは update check/update、drafting fetch、pictures fetch などの取得経路。通常の Control 呼び出しは同関数から値を新規設定しない (app/host/server/control-runtime.mjs:88-107,140-146,277-305,401-429)。
- setup.run() は値を子へ渡すが、子が監視関数を呼ぶ場合だけ効果がある。iq_pack.py と mtp_fetch.py は処理本体の前に監視関数を呼ぶ (terminal/tools/iq_pack.py:612-616、terminal/tools/mtp_fetch.py:526-535)。
- Control の strata.py は起動時に parentwatch.exit_with_parent() を呼ぶ。import / 呼び出し時の例外は握りつぶされ、コマンド起動を失敗させない (terminal/strata.py:35-45)。
- Host がこの値なしで起動すると親を監視しない。Python watcher は親 PID が 1 以下、Windows で対象プロセスを開けない場合などに監視を開始しない (app/host/server/index.mjs:2588-2597、terminal/strata_control/parentwatch.py:21-34、terminal/tools/exit_with_parent.py:23-35)。

## 実行時の詳細

Node の App Host はモジュール初期化時に値を一度判定し、有効なら 1 秒ごとに親の状態を確認する。親 PID が変わるか process.kill(parent, 0) が ESRCH を返すと shutdown() を呼ぶ。通常の signal 停止と同じ経路でサーバーを閉じ、進行中の保存を drain し、共有・native・agent 機能を停止して終了する。値の実行中再読み込みはない (app/host/server/index.mjs:2572-2597)。

Python watcher は関数呼び出し時に値を読み、その時点で監視スレッドを作る。開始済み watcher はプロセス起動後の環境変更を再読しない。parentwatch.py は Windows で親プロセスの同期ハンドルを開いて終了を待ち、他 OS では getppid() の変化を調べる。tools/exit_with_parent.py と mtp_fetch.py は Windows では PID の同期ハンドル、他 OS では直接の親 PID の変化または指定 PID の生存確認を使う。Python watcher は通常 1.5 秒間隔で確認し、対象終了時に stderr への通知を試みて os._exit(1) する。強制終了のため出力バッファは flush されない (terminal/strata_control/parentwatch.py:15-45、terminal/tools/exit_with_parent.py:12-54、terminal/tools/mtp_fetch.py:240-282)。

setup.run() は env 引数または現在の環境を複製して値を整え、subprocess.run(..., env=env) で子へ渡す。既存の数字 PID (1 以外) は呼び出し元が指定した値として保持され、それ以外は setup 自身の PID に置換する。check=True で子の非ゼロ終了が返ると command failed (exit N): ... を表示して失敗扱いにする (terminal/setup.py:1131-1157)。

## ログと測定値

- Node Host の親消失時は shutdown() に進むが、この分岐固有のログ文字列はない (app/host/server/index.mjs:2574-2597)。
- Control watcher は終了時に the program that started this one has ended: stopping を stderr に書こうとする。準備ツール watcher は the process that started this step has ended: stopping、MTP fetch watcher は the process that started this download has ended: stopping を stderr に出して終了コード 1 になる (terminal/strata_control/parentwatch.py:36-44、terminal/tools/exit_with_parent.py:46-54、terminal/tools/mtp_fetch.py:277-282)。
- setup.run() の check=True 経路では子の非ゼロ終了を command failed (exit N): <コマンド名> として報告する (terminal/setup.py:1153-1156)。
- 性能・精度の測定値は該当しない。

## 根拠

- Host 起動時の環境設定: app/desktop/src-tauri/src/main.rs:522-540
- Host 自身の判定と shutdown: app/host/server/index.mjs:2572-2597
- Control 子プロセスの環境と取得呼び出し: app/host/server/control-runtime.mjs:88-107,140-146,277-305,401-429
- CLI 起動時 watcher: terminal/strata.py:35-45、terminal/strata_control/parentwatch.py:15-45
- setup による子向け PID の引き継ぎ: terminal/setup.py:1131-1157
- 準備ツール / MTP watcher: terminal/tools/exit_with_parent.py:12-54、terminal/tools/iq_pack.py:612-616、terminal/tools/mtp_fetch.py:240-282,526-535

