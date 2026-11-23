# `STRATA_KFD_QUIET_EXIT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Linux HIP エンジンの対応 iGPU 経路で、`SIGTERM`・`SIGINT`・`SIGHUP` を受けたとき、実行中の要求を停止し、GPU の待ちを解放して device の処理完了を最大 3 秒待ってから終了する signal handler を有効にする。device が時間内に drain できた場合にだけ arena の登録範囲を解除し、最後は受け取った signal の既定動作で終了する。通常の値判定は既定で有効であり、この変数の値が先頭 `'0'` の場合にこの処理を無効化する。値の選択は生成内容や計算カーネルを変更しない。`Fix::Exit` の環境変数名は `fix_env()` が返し、`env_on()` が共通スイッチを含めて読む（`engine/include/strata/core/kfd_quiet.hpp:47-68`）。

## 値と判定

`env_on(Fix::Exit)` は `std::getenv("STRATA_KFD_QUIET")` と `std::getenv(fix_env(Fix::Exit))` の両方を `switch_on()` に渡す。どちらか一方でも、設定値の**先頭文字**が `'0'` なら無効。unset、空文字、先頭が `'0'` 以外の文字列はそのスイッチを無効化しない。数値・真偽値としての parse、文字列全体の比較、大文字小文字の正規化はない（同:47-65）。

| 条件 | unset | 設定時に有効になる値（例） | 設定時に無効になる値（例） |
|---|---|---|---|
| 対応経路での `STRATA_KFD_QUIET_EXIT`。共通スイッチ `STRATA_KFD_QUIET` も同じ規則 | 対象変数 unset は有効。共通スイッチも unset なら既定で有効 | `1`、`true`、`false`、空文字、` 0`、`0anything` 以外の任意文字列（先頭が `'0'` 以外） | `0`、`00`、`0anything`。共通スイッチがこの値でも対象変数の設定にかかわらず無効 |

空文字は `getenv` が非 null の文字列を返しますが、`v[0] == '0'` ではないため有効側です。先頭に空白がある ` 0` も有効側、`0anything` は後続を parse せず無効側です。無効値の警告や fallback ログはありません（同:47-51, 65）。

## 有効になる条件

- エンジンが `STRATA_USE_HIP` でビルドされ、実行 OS が Linux であること。この条件内に EXIT の判定・handler 実装があります（`engine/src/program/generate.cpp:390-397, 4332-4361`）。
- 起動時に GPU の device properties を取得でき、先頭 device が integrated で、可視 GPU がすべて integrated かつ同じ architecture と判定されること（同:4282-4296）。さらに `igpu_kfd_settle_default()` が true であること。同関数は `igpu_arena_no_thp_default()` を使い、Linux の integrated `gfx1103`・`gfx1150`・`gfx1151`・`gfx1152`・`gfx1153` を受け付けます（`engine/src/core/arch_defaults.cpp:152-160`）。コメントの列挙より、この実装上の判定を根拠としています。
- `STRATA_KFD_QUIET` と `STRATA_KFD_QUIET_EXIT` のどちらも先頭が `'0'` でないこと。共通スイッチは EXIT を含む各 fix をまとめて無効化します（`engine/include/strata/core/kfd_quiet.hpp:47-68`）。
- `SIGTERM`・`SIGINT`・`SIGHUP` の個別 handler 登録には `pipe2()` の成功が必要です。また、その signal に既存 handler がなく、既定動作であること。`SA_SIGINFO` の既存 action または `SIG_IGN` 等の既定以外の action は置き換えません（`engine/src/program/generate.cpp:449-470`）。
- 他の CLI 引数による EXIT 判定の上書きはありません。`STRATA_TRACE` はこの処理を有効化せず、診断行の出力だけを制御します（同:4353-4359, 439-441）。

## 実行時の詳細

`class_flag` を GPU 初期化時に立てた後、エンジン初期化中に `on(Fix::Exit)` を評価します。`env_on()` 自体は `getenv` の結果を static cache しませんが、本番コードの EXIT 判定呼び出しはこの初期化箇所です。したがって handler 登録後にプロセス環境を変更しても再評価されず、signal handler 内で環境変数を読み直すこともありません（`engine/src/program/generate.cpp:4332-4359`; `engine/include/strata/core/kfd_quiet.hpp:65-68`）。

有効なら専用 thread と pipe を作り、既定動作の signal に handler を登録します。最初の signal は handler から pipe に signal 番号を送り、専用 thread が teardown を実行します。要求の STOP flag が存在する間はそれを立て、verify の GPU 待ちを解放し、残り時間内に device を同期します。release と drain が共有する上限は 3 秒で、device 同期が成功した場合だけ arena 登録範囲を解除します。その後、元の signal を既定動作で再送出します。2 回目の signal は teardown を待たずに既定動作へ戻します（`engine/src/program/generate.cpp:403-446`; `engine/include/strata/core/kfd_quiet.hpp:261-295`）。release helper は待ちの解放関数が未登録なら成功を返します（`engine/include/strata/core/progress.hpp:45-51`）。

`pipe2()` に失敗すると `install()` はそこで戻り、thread と signal handler は設定されません。呼び出し側は戻り値を確認しないため、この失敗自体を通知する分岐はありません（`engine/src/program/generate.cpp:4353-4358, 449-452`）。

## ログと測定値

`STRATA_TRACE` が設定されている場合（空文字を含め、値の内容は問わず `getenv(...) != nullptr`）、初期化時に `strata trace: kfd quiet: stop on SIGTERM / SIGINT / SIGHUP drains the GPU first (at most 3 s)` を stderr に出します。これは `install()` 呼び出し後に出るため、`pipe2()` 失敗時も表示され得て、handler 登録成功を保証するログではありません（`engine/src/program/generate.cpp:4353-4359, 449-452`）。

teardown 後も `STRATA_TRACE` が設定されていれば、stderr に `strata trace: kfd quiet: signal %d: waits released %s, device drained %s, %d arena ranges unregistered, %.0f ms` を出し、状態を `yes` / `no` で示します（同:439-441）。この変数自体について、条件つきの測定値を裏付ける Strata 資料は確認できません。

## 根拠

- `engine/include/strata/core/kfd_quiet.hpp:47-68` — 共通・個別スイッチの判定、`Fix::Exit` から環境名への動的な解決、環境読み取り。
- `engine/src/program/generate.cpp:4282-4296, 4332-4361` — GPU 条件、Linux HIP guard、起動時判定と EXIT handler の有効化。
- `engine/src/core/arch_defaults.cpp:152-160` — 実際の architecture 条件。
- `engine/src/program/generate.cpp:390-472` — signal handler、pipe/thread、teardown、ログと終了方法。
- `engine/include/strata/core/kfd_quiet.hpp:261-295` — 3 秒の共有上限、drain 成功時だけの unregister、signal 再処理規則。
- `engine/include/strata/core/progress.hpp:45-51` — verify 待ち解放 helper。
