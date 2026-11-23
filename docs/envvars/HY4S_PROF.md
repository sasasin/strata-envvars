# `HY4S_PROF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`HY4S_PROF` は Hy4-Flash SYCL 実装の共有 `sycl::queue` に profiling property を付ける開発・計測向け設定である。値が `1` で始まると、in-order queue に `sycl::property::queue::enable_profiling()` を追加する。それ以外では profiling property を付けない。この変数自身は計測結果を出力せず、通常の推論処理や生成内容を直接分岐させない（`engine/src/hy4flash/sycl/sy_common.h:154-176`）。

`--prof2` は別の CLI スイッチで、区間マーカー event を記録して queue event の profiling 情報を読む。したがって結果ログを出すには `--prof2` も必要であり、`HY4S_PROF` だけでは `[prof2 ...]` ログは出ない（`engine/src/hy4flash/sycl/sy_main.cpp:177-178,283-294,370-371`、`engine/src/hy4flash/sycl/sy_graph.h:423-459,461-474`）。

## 値と判定

`Q()` が初期化する共有 queue の property を決める際、`std::getenv("HY4S_PROF")` の戻り値が null でないこと、および先頭文字 `pf[0]` が `'1'` であることだけを検査する。文字列全体の比較、数値変換、空白除去、大小文字変換はない（`engine/src/hy4flash/sycl/sy_common.h:157-164`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL `Q()` queue の初回生成時 | profiling property なし | `1`, `10`, `1anything` など、先頭が ASCII `1` | 空文字、`0`, `true`, `True`, ` 1` など、先頭が `1` でない値 |

`HY4S_PROF` の判定が有効なら `HY4S_DISCARD` は評価されず、queue に `discard_events()` を付ける分岐には進まない。有効でない場合は `HY4S_DISCARD` が設定され、かつ先頭文字が `1` のときだけ discard property が選ばれる（`engine/src/hy4flash/sycl/sy_common.h:158-164`）。

## 有効になる条件

- `engine/src/hy4flash/sycl/` の SYCL 実装がビルドされ、そのプロセスで共有 `Q()` が初期化されること。HY4S_PROF の参照はこの SYCL 共通ヘッダーに限られる（`engine/src/hy4flash/sycl/sy_common.h:1-14,154-176`）。
- 通常実行では `Q()` を最初に必要としたときに queue property が決まる。`--version`、`--info` など `Q()` に触れる前に戻る経路では queue 設定は行われない（`engine/src/hy4flash/sycl/sy_main.cpp:117-124,255-260`）。
- サーバーモードも同じ共有 queue を使う経路だが、`ServeOpts` に `--prof2` の値を渡す処理はなく、`HY4S_PROF` が有効というだけでサーバーから区間計測ログが出るとはコード上確認できない（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`、`engine/src/hy4flash/sycl/sy_serve.h:262`）。
- `--prof2` のときだけ Runner が区間マーカー event を積み、`pflush()` が `command_start` の profiling 情報を取得する。HY4S_PROF はこの CLI スイッチを代替しない（`engine/src/hy4flash/sycl/sy_main.cpp:177-178,283-294`、`engine/src/hy4flash/sycl/sy_graph.h:436-459`）。
- CPU SYCL device を選ぶ `HY4S_CPU_DEVICE=1` の経路でも `make_props()` が同じ queue property を返す。GPU device 選択経路も同様で、どちらも HY4S_PROF 自体に追加条件はない（`engine/src/hy4flash/sycl/sy_common.h:158-174`）。

## 実行時の詳細

`Q()` の関数内 `static sycl::queue q` を初期化するラムダの中で、`make_props()` が `HY4S_PROF` を読み込む。初回 `Q()` 呼び出し時に一度だけ評価され、その後は同じ queue を返すため、初期化後にプロセス環境を変えてもこの queue の設定は変わらない（`engine/src/hy4flash/sycl/sy_common.h:154-176`）。

`Q()` は SYCL の kernel launch、メモリ確保・コピーなどに共有され、queue は in-order で作成される。`HY4S_PROF` が有効な場合はその queue に profiling property も加わる。区間計測を要求する `--prof2` 経路では、`Runner::PS` が同 queue に marker task を enqueue し、`pflush()` が完了待ちの後に event の開始時刻を読み、`[prof2 ...]` として stderr に集計値を出す（`engine/src/hy4flash/sycl/sy_common.h:3,158-179,264-284`、`engine/src/hy4flash/sycl/sy_graph.h:436-459,461-474`）。

## ログと測定値

`HY4S_PROF` を読む箇所に専用ログや無効値警告はない。`--prof2` が有効な場合は prefill/decode 後に stderr へ `[prof2 prefill]` または `[prof2 decode]`、区間別 `ms` と `TOTAL` を出力する（`engine/src/hy4flash/sycl/sy_graph.h:461-474`、呼び出し元 `engine/src/hy4flash/sycl/sy_main.cpp:370-371,579-580`）。

SYCL queue の生成や event profiling 情報取得が失敗した場合の具体的な動作は SYCL runtime に依存するため、ここでは断定しない。通常実行の main 経路には `sycl::exception` を `SYCL exception: %s` と stderr に出して終了コード `4` で返す catch がある（`engine/src/hy4flash/sycl/sy_main.cpp:612-615`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_common.h:154-176` — 共有 queue の初回生成、環境変数判定、profiling / discard property、static cache。
- `engine/src/hy4flash/sycl/sy_main.cpp:117-124,177-178,215-248,283-294,370-371,579-580,612-615` — 早期終了、`--prof2` CLI、Runner への設定、計測呼び出し、例外経路。
- `engine/src/hy4flash/sycl/sy_graph.h:423-474` — 区間計測 event の enqueue、profiling 情報の取得、stderr 出力。
- `engine/src/hy4flash/sycl/sy_common.h:264-284` — kernel / memory helper が共有 queue `Q()` を使用。
