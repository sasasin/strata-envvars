# `STRATA_KPROF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。作業開始時の Strata checkout は `main` で、`git status --short --branch` は `## main...origin/main`（未コミット変更なし）だった。

## 役割

SYCL engine で、Strata が作成する SYCL queue に profiling property を付け、`strata::kprof::kp()` を通る kernel launch の `sycl::event` を記録して、prompt/decode の phase ごとに GPU 時刻を集計する診断用スイッチ。通常の計算カーネルや選択ロジックを別実装に切り替える設定ではないが、記録時に event を保持し、集計時に待機・読み出しを行う。主な実装は `engine/sycl/include/dpct/device.hpp` の `create_queue_impl()` と `engine/sycl/include/strata/kprof.hpp` の `enabled()` / `QP` / `flush_locked()`。

この読み取りは `engine/sycl/` 内だけにある。トップレベル CMake では SYCL engine は実験的な別 backend で、`STRATA_ENABLE_SYCL` の既定値は `OFF`（`engine/CMakeLists.txt:23-32`）。CUDA/HIP engine でこの変数を読む Strata 所有箇所は見つからなかった。

## 値と判定

queue 作成側と `kprof::enabled()` 側が、それぞれ `std::getenv("STRATA_KPROF")` を行い、値が非 null かつ `v[0] != '0'` なら有効とする（`engine/sycl/include/dpct/device.hpp:690-696`, `engine/sycl/include/strata/kprof.hpp:31-34`）。文字列全体の比較や数値変換はしない。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL queue 作成 / `kprof::enabled()` | 無効 | 先頭文字が `0` 以外の値。例: `1`, `true`, `false`, ` 1`, `-1` | 空文字、`0`, `0anything`, `00`（いずれも先頭文字が `0` または空文字） |

大文字小文字、空白、後続文字の妥当性は検査しない。したがって `false` も有効で、`0anything` は無効。queue 作成側の `kprof_on` と `enabled()` は別々の関数内 static 値であり、それぞれ初回評価時に読み取った結果を保持する。既定値はどちらも無効（同上）。

## 有効になる条件

- SYCL engine の実行経路を使う必要がある。トップレベル構成では `STRATA_ENABLE_SYCL=ON` で CUDA/HIP を同時に有効化できず、SYCL は既定で無効（`engine/CMakeLists.txt:23-32`）。
- 計測対象は `strata::kprof::kp()` で包まれた `parallel_for` / `submit` / `single_task` の launch。event の記録は queue の状態が `executing` のときだけで、graph recording 中は `record()` が戻る（`engine/sycl/include/strata/kprof.hpp:81-86,230-254`）。
- decode window は通常 graph 経路で記録されるため、`STRATA_VERIFY_EAGER` が設定され、window body が queue 上で直接実行される経路が per-kernel event 記録の条件。`capture()` はこの変数が設定されていると graph recording を省く（`engine/sycl/src/core/verify.cpp:2098-2107`）。`STRATA_VERIFY_EAGER` 自体は値の内容でなく設定有無で判定される。
- prompt は `Prefill::run_impl()` の prompt phase と `window_end("prompt")` を通る（`engine/sycl/src/prefill/prefill.cpp:2692-2698,5729-5731`）。decode は verifier の phase と成功経路末尾の `window_end("decode")` を通る（`engine/sycl/src/core/verify.cpp:2384-2389,2906-2919`）。他の実行経路や未完了の処理は、これらの flush 地点に到達しないことがある。
- `DPCT_PROFILING_ENABLED` がない translation unit では、変数が無効でも queue 作成コードが profiling property を付ける場合がある。ただし `kprof::enabled()` が偽なら、この環境変数による per-kernel event 記録・phase flush は有効にならない（`engine/sycl/include/dpct/device.hpp:691-704`, `engine/sycl/include/strata/kprof.hpp:31-34,230-254`）。
- この環境変数を上書きする CLI 引数や設定ファイルの読み取りは確認できなかった。

## 実行時の詳細

queue 初期化では `init_queues()` が in-order queue と out-of-order queue を `create_queue_impl()` 経由で作成する。`STRATA_KPROF` が有効なら、同関数が translation unit の `DPCT_PROFILING_ENABLED` にかかわらず queue に `enable_profiling()` property を加える（`engine/sycl/include/dpct/device.hpp:676-704`）。

`kprof::enabled()` が真のとき、`QP` の launch wrapper は通常どおり queue に処理を投入し、返った event と起動元の file/function/line を `record()` に渡す。queue が graph recording 状態なら記録は行わない（`engine/sycl/include/strata/kprof.hpp:81-86,230-257`）。収集対象は `kp()` を通る launch に限られ、全ての SYCL / 外部ライブラリ処理を計測するものではない。

`phase("prompt")` / `phase("decode")` は phase 切替時に前の記録を flush する。正常な prompt/decode の終端では `window_end()` がそれぞれの名前で flush する。flush は event を wait し、kernel の start/end timestamp を読み、呼び出し場所ごとに集計して記録をクリアする。取得時の例外は空の `catch (...)` で無視される（`engine/sycl/include/strata/kprof.hpp:142-213`）。プロセス終了時の `State` destructor も残った記録を flush してレポートを出す（同 `:215-221`）。

読み取り結果は初回評価後 static cache され、実行中に環境値を変更しても queue 作成判断や `enabled()` の結果は更新されない。CLI、リクエストごとの再読込、子プロセスへの転送は実装されていない（`engine/sycl/include/dpct/device.hpp:691`, `engine/sycl/include/strata/kprof.hpp:31-34`）。

## ログと測定値

`STRATA_KPROF_EVERY` が正の整数として `std::atoll` で読まれた場合、その phase の flush 回数が指定値の倍数になるたびに、集計表を stderr に出力して flush する。未設定時は `0` で定期出力しない。空文字や整数として変換できない先頭文字は `atoll` により `0` となり、負値も `> 0` を満たさない。数値の後ろの文字列は `atoll` が読む範囲で切り捨てられる（`engine/sycl/include/strata/kprof.hpp:183-187`）。

プロセス終了時は集計が存在すれば同じレポート形式を stderr に出力する。行の形式は `kprof %s: %lld flushes, %lld kernels; kernel sum %.3f ms/flush, queue span %.3f ms/flush, gap %.3f ms/flush`、続く site 行は `%-58s %8.3f ms/flush %5.1f%%  n=%.1f/flush  avg %.1f us`（`engine/sycl/include/strata/kprof.hpp:118-139,215-221`）。site 表示の行数は `STRATA_KPROF_TOP` で指定し、未設定は 45、設定時は `std::atoi` の結果を使う。測定結果や比較値を記載した Strata 資料は確認できなかった。

## 根拠

- 環境変数の全直接読み取り: `engine/sycl/include/dpct/device.hpp:691`, `engine/sycl/include/strata/kprof.hpp:32`。その他の `STRATA_KPROF` 参照はコメントのみ。
- queue 作成と profiling property: `engine/sycl/include/dpct/device.hpp:676-704`。
- event 記録・phase 集計・出力: `engine/sycl/include/strata/kprof.hpp:31-34,81-86,118-139,142-221,230-257`。
- SYCL build 条件と decode/prompt の経路: `engine/CMakeLists.txt:23-32`, `engine/sycl/src/core/verify.cpp:2098-2107,2384-2389,2906-2919`, `engine/sycl/src/prefill/prefill.cpp:2692-2698,5729-5731`。
