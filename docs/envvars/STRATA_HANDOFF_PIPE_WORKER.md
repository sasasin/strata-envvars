# `STRATA_HANDOFF_PIPE_WORKER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

レイヤー分割した prefill で次 stage の chunk を起動する方法を選ぶ。値が有効なら stage ごとに遅延生成する `HandWorker` の専用 thread に job を投入し、無効なら chunk ごとに `std::async(std::launch::async, ...)` を使う。どちらも `next_->run_impl(...)` を実行し、次 stage の処理結果を future で待つ。これは `STRATA_HANDOFF_PIPE` が有効にする分割 hand-off の thread 戦略を切り替えるもので、piece 数や chunk の分割方法そのものは変更しない（`engine/src/prefill/prefill.cpp:921-928, 7812-7834`）。

## 値と判定

`handoff_pipe_worker()` 内の関数ローカル `static const bool` を初期化するときに `std::getenv` で取得し、設定値があれば `std::atoi(e) != 0`、未設定なら `true` とする。`atoi` は整数として読める先頭部分で判定されるため、数値全体・文字列一致・大小文字は検査しない。明示的な空文字、数値で始まらない文字列、`0` や `0anything` は `atoi` が 0 を返して無効。`1`、`-1`、`+2`、`1suffix` は非 0 となり有効（`engine/src/prefill/prefill.cpp:925-927`）。

| 条件 | unset | 設定時に有効 | 設定時に無効 |
|---|---|---|---|
| `STRATA_HANDOFF_PIPE` により hand-off pieces が用意されている | worker 有効（既定） | `atoi` の結果が非 0（例: `1`, `-1`, `1suffix`） | `atoi` の結果が 0（例: 空文字, `0`, `0anything`, `true`） |
| hand-off pieces が 0 | この変数の判定に到達せず、chunk ごとの `std::async` | 同左 | 同左 |

## 有効になる条件

- `engine/src/prefill/prefill.cpp` が組み込まれる GPU prefill 経路であること。同ファイルは `strata_prefill` ライブラリのソースで、CUDA/HIP GPU engine の CMake 構成に属する（`engine/cmake/strata_gpu_engine.cmake:478-485`）。
- 次 stage を持つレイヤー分割であること。次 stage がなければ hand-off job は投入されない（`engine/src/prefill/prefill.cpp:7748, 7821`）。
- `STRATA_HANDOFF_PIPE` が 2 以上として解釈され、初期化で pieces とイベントが設定されること。unset / `0` / `1` / 0 以下では `hand_pieces` が 0 のままで、worker 変数は実質的に使われず `std::async` 経路になる。`STRATA_HANDOFF_PIPE` の値は `atoi` され、2 以上は最大 16 に制限される（`engine/src/prefill/prefill.cpp:899-913, 2488-2502`）。
- この切替に別の CLI 引数や他の環境変数による上書きはない。`--prefill-pipe` / `STRATA_PREFILL_PIPE` は chunk 計画に関わる別設定であり、worker の分岐条件には使われていない（`engine/src/prefill/prefill.cpp:3615-3625, 3683-3687, 7821-7831`）。

## 実行時の詳細

`handoff_pipe_worker()` は次 stage へ chunk を渡した後に呼ばれる。pieces が 0 より大きいときだけ `&&` の右辺が評価され、そこで初回に環境値を読み込んで static cache する。したがって通常は最初の該当 hand-off 時に値が固定され、その後の環境変更は同一プロセスでは反映されない。pieces が 0 の間は右辺が短絡され、worker 設定の static 値自体はまだ初期化されない（`engine/src/prefill/prefill.cpp:925-927, 7821`）。

有効時は stage の `Impl` に `HandWorker` を必要時に一つ作り、thread に `strata-hand` という名前を付けて CPU pinning を行う。投入された `packaged_task` は `next_->run_impl(...)` の bool 結果を future に返し、thread 終了時に `cudaGetLastError()` を呼ぶ。無効時は各 chunk ごとに `std::async` で同じ `run_impl` を起動し、呼び出し thread に CPU pinning を行う（`engine/src/prefill/prefill.cpp:929-968, 7821-7832`）。worker は prefill の `release()` 時に reset され、待機 thread を join する（`engine/src/prefill/prefill.cpp:1832-1838`）。

この変数は piece ごとのデータ転送を有効化しない。piece 数が正なら、別途 hand-off 側で chunk の完了 event と各 piece の download event を記録し、次 stage の upload を event 待ちにする（`engine/src/prefill/prefill.cpp:7771-7785, 4427-4448`）。

## ログと測定値

この変数の読み取り値や worker 選択を知らせる専用ログはない。hand-off の event 作成失敗は `prefill: the layer split's hand-off events (STRATA_HANDOFF_PIPE)`、piece upload 失敗は `prefill: the layer split's hand-off upload failed (STRATA_HANDOFF_PIPE): ...` として返される。投入した次 stage の失敗は future の `get()` を通じて `next_err_` に伝播する（`engine/src/prefill/prefill.cpp:2493-2501, 4445-4448, 7797-7801, 9592-9607`）。これらは hand-off 自体のエラー経路であり、worker 設定固有の警告ではない。測定値は記載しない。

## 根拠

- 候補名の実読取りと値判定、pieces による短絡条件: `engine/src/prefill/prefill.cpp:899-928`
- GPU prefill ライブラリへの組み込み: `engine/cmake/strata_gpu_engine.cmake:478-485`
- hand-off pieces と event 初期化: `engine/src/prefill/prefill.cpp:2488-2502`
- persistent worker の実装と破棄: `engine/src/prefill/prefill.cpp:929-968, 1832-1838`
- worker / `std::async` の選択、future への結果伝達: `engine/src/prefill/prefill.cpp:7812-7834`
- hand-off event / upload と失敗経路: `engine/src/prefill/prefill.cpp:4427-4448, 7771-7801`
