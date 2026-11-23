# `HY4_DRAFT_ISOLATE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この環境変数は、Hy4-Flash の CUDA/HIP 実装にある DFly2 drafter が対象モデルの KV cache を直接使わず、対象層ごとの private copy に書き込むデバッグ用切替です。DFly2 対象層は 25、29、33、37、41 です。変数の値そのものは読まず、存在すると `isolate` が true になります（`engine/src/hy4flash/run/hy4_dfly2.hip.h:189,410-416`）。

有効時、各 drafter 呼び出しで対象層の cache 全体を `shadow[d]` に device-to-device コピーし、その層の KV 書き込み先をコピー側に切り替えます。通常側の `r.kcache[L]` はこの書き込み先として使われません（`engine/src/hy4flash/run/hy4_dfly2.hip.h:741-762,969-989`）。

## 値と判定

`DFly2` のメンバー初期化子が `getenv("HY4_DRAFT_ISOLATE") != nullptr` を評価します。文字列比較や数値変換はありません。したがって空文字も含め、環境変数が設定されていれば true です（`engine/src/hy4flash/run/hy4_dfly2.hip.h:410-416`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP の DFly2 実装 | `false` | `1`、`0`、`true`、`false`、空文字、その他任意の値 | なし（環境変数が存在する限り true） |

大文字小文字、空白、数値としての妥当性、値の境界は判定されません。空文字・`0`・`false` も「未設定」ではありません。別の値への fallback や CLI による上書きはありません。

## 有効になる条件

- `engine/src/hy4flash/run/hy4_dfly2.hip.h` は CUDA または HIP の `strata-hy4` ビルドに含まれます。統合 CMake では `STRATA_BUILD_HY4` に加えて CUDA または HIP が必要です（`engine/CMakeLists.txt:846-851,884-891`）。この変数を読む実装は Metal/SYCL 側にはありません。
- 実行経路で DFly2 が初期化されている必要があります。サーバーでは `--draft off` 以外で、`r.Tc >= 8` のとき初期化を試み、モデルに DFly2 tensor がない、または初期化に失敗すれば drafter なしで続行します（`engine/src/hy4flash/run/hy4_serve.hip.h:319-339`）。通常の CLI 実行では `--draft dfly2` の場合に初期化します（`engine/src/hy4flash/run/hy4_main.hip.cpp:363,406,700-715`）。
- 初期化成功後も、各 draft 呼び出しで `K` が 1 以上かつ上限以下であること、KV 容量の確保が可能なこと、sparse cache slot と capture row が有効なことが必要です。条件を満たさない呼び出しは `can_draft` が false を返し、呼び出し側の plain decode 経路へ進みます（`engine/src/hy4flash/run/hy4_dfly2.hip.h:578-586`; `engine/src/hy4flash/run/hy4_spec.hip.h:269-282`）。
- graph capture/replay は `!isolate` を条件にしているため、この環境変数が設定されているとその DFly2 呼び出しでは graph 経路を使わず、private copy を行う通常経路に進みます（`engine/src/hy4flash/run/hy4_dfly2.hip.h:600-602,855-857`）。

## 実行時の詳細

環境変数は `DFly2` オブジェクトのメンバー初期化時に一度読みます。サーバーは `Runner::init` の後に `DFly2 df(r)` を作り、その後 DFly2 を初期化します。オフライン CLI も `Runner::init` の後に `DFly2 df(r)` を作ります（`engine/src/hy4flash/run/hy4_serve.hip.h:315-331`; `engine/src/hy4flash/run/hy4_main.hip.cpp:703-715`）。同一オブジェクトの使用中に環境を変更しても値は再評価されません。プロセス内で別の `DFly2` オブジェクトを新たに作れば、その生成時点の環境が評価されます。

draft 時には `shadow[d]` が未確保なら cache サイズ分を `hipMalloc` し、以後の呼び出しでは同じ領域を再利用します。ただし各呼び出しで `r.kcache[L]` から全 cache サイズを非同期 device-to-device コピーしてから `dcache` を `shadow[d]` に向けます。後続の `mla_write_kv` にその `dcache` が渡されます（`engine/src/hy4flash/run/hy4_dfly2.hip.h:748-762,975-989`）。

## ログと測定値

変数が有効になったことを示す専用ログはありません。shadow 領域の確保や cache コピーなど `HCK` 対象の GPU 呼び出しが失敗すると、stderr に `HIP error %d (%s) at %s:%d\n` を出して終了コード 3 で終了します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34`; 呼び出し箇所は `engine/src/hy4flash/run/hy4_dfly2.hip.h:751-753,978-980`）。

この変数について条件付きの測定値は確認できませんでした。

## 根拠

- `engine/src/hy4flash/run/hy4_dfly2.hip.h:189,410-416` — 対象 cache 層と環境変数の存在判定。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:578-586,600-602,741-762,846-857,969-989` — draft 可否、graph 経路の条件、private cache copy と書き込み先。
- `engine/src/hy4flash/run/hy4_serve.hip.h:315-339` — サーバーでの DFly2 構築・有効化条件。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:363,406,700-715` — CLI の draft 指定と DFly2 構築。
- `engine/CMakeLists.txt:846-851,884-891` — CUDA/HIP ビルド条件。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34` — GPU 呼び出し失敗時の stderr と終了処理。
