# `INK_SYCL_CPU_THREADS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL Inkling backend の hybrid expert 処理で使う常駐 CPU worker pool の thread 数を上書きする。通常は `std::thread::hardware_concurrency()` から算出する値を使い、設定値が 1〜64 なら `n_workers` をその値にする。これはモデルの host-USM 配置 expert を処理する CPU worker 数の指定であり、SYCL 全体の thread 数や GPU kernel 数の指定ではない。直接読む場所は `InkSyHybridEngine::init()`（`engine/src/inkling2/sycl/ink_sy_hybrid.h:488-542`）。

この pool が使われるのは hybrid MoE 経路の `M <= 2` のときで、host expert の CPU 計算を GPU の VRAM expert 計算と並行して進める（同 `ink_sy_hybrid.h:619-645, 655-733`）。`M >= 3` では host expert を CPU pool で計算せず、GPU の staging buffer に順次または double-buffer で読み込む（同 `ink_sy_hybrid.h:637-639, 743-851`）。この変数で変わるのは worker 数であり、ソース上、expert の配置や計算式をこの値で切り替える処理はない。

## 値と判定

値が設定されている場合に `std::atoi(env_t)` で変換し、変換結果が `1 <= v <= 64` のときだけ採用する。文字列全体の妥当性検査はなく、先頭から整数として読める部分だけが変換対象になる。したがって、例えば `4tail` は 4 として採用され、` 4` や `+4` も 4 として採用される。`true`、`false`、空文字、整数として読めない文字列は変換結果が 0 となるため採用されない。`0`、負数、`65` も範囲外なので採用されず、いずれも既定値に戻る。大文字小文字の比較は行わない。`atoi` の整数範囲を超える入力の結果はこのコードでは定義していないため、値として扱えるとは断定できない（`engine/src/inkling2/sycl/ink_sy_hybrid.h:524-529`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| hybrid pool の初期化まで進む場合 | `hw > 4` なら `min(16, hw / 2)`、それ以外は 2（`hw` は hardware concurrency） | 1〜64。例: `1`, `16`, `64`, `4tail` | 空文字、`0`, `-1`, `65`, `true`, `abc`。既定値を維持 |
| hybrid が無効、host expert が 0 件、または `slot_stride == 0` の場合 | worker pool を初期化しない | 該当なし | この変数は読み取られないか、読み取りより前に初期化を抜ける |

## 有効になる条件

- `STRATA_ENABLE_SYCL` で SYCL backend がビルドに含まれ、実行時に SYCL Inkling backend が使われること。SYCL backend の追加は `engine/src/inkling2/CMakeLists.txt:206-208`、SYCL plugin と `INKLING_ENABLE_SYCL` の設定は `engine/src/inkling2/sycl/CMakeLists.txt:7-8, 43-45` にある。
- `InkSyHybridEngine::init()` に到達し、`INK_SYCL_NO_HYBRID` によって無効化されていないこと。`INK_SYCL_NO_HYBRID` は未設定なら有効、設定値の先頭文字が `'1'` なら hybrid を無効化する。無効時は `INK_SYCL_CPU_THREADS` の読み取り箇所より前に戻る（`engine/src/inkling2/sycl/ink_sy_hybrid.h:488-495`）。
- モデルに host 配置 expert が 1 件以上あること。モデル loader は VRAM 予算に収まらない expert を host 側に割り当てて `n_host_experts` に数える（`.strata` loader: `engine/src/inkling2/sycl/ink_sy_common.h:772-785, 837-885`; model-file loader: 同 `ink_sy_common.h:1197-1222`）。全 expert が VRAM に入ると `init()` は worker pool 初期化前に戻る（`engine/src/inkling2/sycl/ink_sy_hybrid.h:492-495`）。
- `slot_stride` が 0 でないこと。0 の場合は worker pool 初期化前に戻る（`engine/src/inkling2/sycl/ink_sy_hybrid.h:497-499`）。
- 値が設定されていても、上記のいずれかを満たさない場合は無視される。`--vram-experts-gb` は loader の VRAM 予算を変え、その結果として host expert の有無に間接的に影響し得る（`.strata` loader: `engine/src/inkling2/sycl/ink_sy_common.h:779-781`; model-file loader: 同 `ink_sy_common.h:1203-1217`）。
- CLI の `--parallel` は runner の batch / slot 上限に使われるが、この環境変数を上書きする CPU worker 数の CLI option は確認できない（`engine/src/inkling2/sycl/ink_sycl_backend.cpp:72-74, 100`; standalone runner: `engine/src/inkling2/sycl/ink_sy_main.cpp:198-203`）。
- pool が初期化されても、CPU pool が実際に cold host expert を処理するのは hybrid MoE の `M <= 2` 経路である。`M >= 3` の prefill / large batch は GPU staging 経路を使うため、この設定値の worker 数はその処理には使われない（`engine/src/inkling2/sycl/ink_sy_hybrid.h:637-639, 699-733, 743-851`）。

## 実行時の詳細

backend の初期化はモデルをロードした後に `runner_.init()` を呼び、その中で `hybrid.init(m)` を実行する（`engine/src/inkling2/sycl/ink_sycl_backend.cpp:95-101`; `engine/src/inkling2/sycl/ink_sy_runner.h:328-335`）。そこで hardware concurrency に基づく既定値を計算し、環境変数が設定されていれば `atoi` の結果を範囲検査して上書きする。その後 `n_workers` 個の `std::thread` を生成し、pool を active にする（`engine/src/inkling2/sycl/ink_sy_hybrid.h:524-542`）。この変数用の static cache はなく、`init()` のたびに読み直す。初期化後の環境変更は既存 pool の数を変えず、再初期化時にだけ再評価される。

`M <= 2` の MoE 実行では router の expert ID・weight と入力を pinned USM doorbell にコピーし、host expert ごとに CPU group を組む。pool は group を処理し、CPU 側の expert 出力に router weight を掛けた結果を共有領域に書く。GPU 側の VRAM expert 計算と並行して完了を待ち、CPU 出力を SYCL scatter kernel で MoE 出力領域に戻して reduce する（`engine/src/inkling2/sycl/ink_sy_hybrid.h:637-645, 655-733`; worker の計算: 同 `ink_sy_hybrid.h:416-453`）。値を変えてもこの経路を選ぶ条件や model / CLI 設定を変更しない。

## ログと測定値

正常に pool が有効化されると stderr に `[ink_sycl_hybrid] ACTIVE: cpu_pool=...` が出て、採用された worker 数が `cpu_pool` に表示される。続いて runner は `[ink_sycl] runner ready: ... hybrid=1 ...` を出す（`engine/src/inkling2/sycl/ink_sy_hybrid.h:536-541`; `engine/src/inkling2/sycl/ink_sy_runner.h:328-333`）。無効値を理由にした警告やエラーはこの判定箇所にはなく、無効値は既定値へ静かに戻る。hybrid が初期化されない場合は ACTIVE ログは出ず、runner ready の `hybrid` は 0 になる。

`std::thread` の生成失敗を `InkSyHybridEngine::init()` 内で捕捉する処理や、この変数専用の終了コードはない。`runner.init()` は `hybrid.init(m)` の後に ready ログを出して成功を返し、呼び出し元は runner 初期化が `false` を返した場合だけ `[ERROR] runner init: ...` を表示するため（`engine/src/inkling2/sycl/ink_sy_hybrid.h:530-542`; `engine/src/inkling2/sycl/ink_sy_runner.h:328-335`; `engine/src/inkling2/sycl/ink_sy_main.cpp:200-203`）、worker thread 生成失敗時の最終的なプロセス挙動はこの経路のソースだけからは断定できない。

この環境変数による性能差・推奨値の測定条件や結果は、対象 commit の確認範囲では見つからなかった。

## 根拠

- 読み取り・数値変換・worker 数の既定値・範囲・生成・ACTIVE ログ: `engine/src/inkling2/sycl/ink_sy_hybrid.h:488-542`
- hybrid の無効化と host expert 条件: `engine/src/inkling2/sycl/ink_sy_hybrid.h:491-499`
- host expert の VRAM / host 分類: `engine/src/inkling2/sycl/ink_sy_common.h:772-885, 1197-1222`
- runner 初期化と ready ログ: `engine/src/inkling2/sycl/ink_sy_runner.h:328-335`
- backend からの初期化・CLI parallel との関係: `engine/src/inkling2/sycl/ink_sycl_backend.cpp:65-101`
- CPU worker の計算と MoE dispatch: `engine/src/inkling2/sycl/ink_sy_hybrid.h:416-453, 619-733`
- large batch の GPU staging: `engine/src/inkling2/sycl/ink_sy_hybrid.h:743-851`
- SYCL build 条件: `engine/src/inkling2/CMakeLists.txt:206-208`; `engine/src/inkling2/sycl/CMakeLists.txt:7-8, 43-45`
