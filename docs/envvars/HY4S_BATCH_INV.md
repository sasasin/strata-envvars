# `HY4S_BATCH_INV`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Intel Arc 向け Hy4-Flash SYCL 実装で、MLA attention の batch-invariant 分割を有効にするかを決める。設定が有効になると、`g_mla_batch_invariant` が 1 になり、`mla_choose_splits()` は batch 行数 `a.M` が 16 以下のとき分割数計算の基準を `a.M` ではなく 1 行として扱う。これにより attention のキー分割が 1 token 実行に沿うようにするコードである。コメントは speculative verify の各行で同じ FP32 加算順を保つ目的を示すが、この環境変数だけで出力の一致や性能を保証するものではない（`engine/src/hy4flash/sycl/sy_spec.h:15-19`、`engine/src/hy4flash/sycl/sy_mla.cpp:1652-1680`）。

直接の読み取りは SYCL Hy4-Flash の `spec_set_batch_invariant()` と `--wincheck` 経路に限られる。CUDA/HIP の Hy4-Flash 実装や通常の Strata サーバー共通設定では読まれない。SYCL engine は CMake の `STRATA_ENABLE_SYCL` が既定 OFF の独立した実験的 backend である（`engine/CMakeLists.txt:23-32`）。

## 値と判定

`spec_set_batch_invariant()` は `std::getenv()` で値を取得し、値が存在し、かつ先頭文字が `'0'` の場合だけ 0、それ以外は 1 を設定する。文字列全体を parse せず、空白除去、数値変換、大小文字変換、末尾検査も行わない（`engine/src/hy4flash/sycl/sy_spec.h:16-19`）。

| 条件 | unset | batch-invariant が無効 | batch-invariant が有効 |
|---|---|---|---|
| `spec_set_batch_invariant()` が呼ばれる経路 | 1（有効） | 先頭が `0` の任意の文字列。例: `0`、`00`、`0anything` | 空文字、`1`、`true`、`false`、`no`、` 0`、`2`（値が存在し、先頭が `0` 以外） |
| `--wincheck` の事前条件 | setter を呼んで 1 にする | 値が存在し先頭が `0` なら setter を呼ばず、初期値 0 のまま | それ以外は setter を呼んで 1 にする |

通常の speculative decode とサーバー経路では、unset は有効扱いになる。`--wincheck` も unset を有効扱いにする。CLI の `--draft` や `--wincheck` は機能を実行する条件であり、環境変数と同じ設定値として優先順位を競うものではない。条件が成立した後、値の先頭が `0` なら環境変数が無効化方向に働く。

## 有効になる条件

- `STRATA_ENABLE_SYCL=ON` で構成する Intel SYCL backend の Hy4-Flash コードが対象。ほかの backend ではこの読み取りコードはない（`engine/CMakeLists.txt:23-32`）。
- server では `--draft` が `off` 以外で、モデルに DFly2 drafter tensors があり、`--chunk >= 8` で、さらに `DFly2::init()` が成功して `use_spec` が true になる必要がある。この場合、サーバーのモデル初期化後に setter が呼ばれる。`--draft dfly2` で drafter 不在、chunk 不足、初期化失敗なら環境変数による無効化以前にエラー終了する。`auto` では DFly2 初期化に失敗しても speculative decode を使わない経路へ進む（`engine/src/hy4flash/sycl/sy_serve.h:248-278,303-308`）。
- 単発 CLI では `--draft dfly2` かつ `--gen > 0` のとき speculative decode 経路に入り、prefill 後に setter を呼ぶ。`--draft auto` はこの CLI 経路では `spec_mode` を作らない（`engine/src/hy4flash/sycl/sy_main.cpp:250-280,379-386`）。
- 診断 CLI では `--wincheck N` の `N > 0` かつ先行する detcheck 分岐に入らない場合に、環境変数を確認する。設定値が先頭 `0` なら batch-invariant を有効化せず、そうでなければ有効化する。`--wincheck` の比較対象 window は `min(N, 8)` 行（`engine/src/hy4flash/sycl/sy_main.cpp:459-464`）。
- batch 行数が 16 を超える MLA 呼び出しでは、フラグが 1 でも `mla_choose_splits()` の基準は `a.M` のままで、この分岐による 1 行基準への変更は起きない（`engine/src/hy4flash/sycl/sy_mla.cpp:1654-1656`）。

## 実行時の詳細

サーバーではモデル・expert の初期化後、`use_spec` が真のときだけ `spec_set_batch_invariant()` を一度呼び出す。通常のリクエストループ内に環境変数の再読込はない。CLI speculative decode は prefill 後、decode に入る直前に一度読む。`--wincheck` は診断処理に入った時点で値を確認し、必要なら setter 内でもう一度 `getenv()` する。いずれも処理開始後のプロセス環境変更を追跡する実装ではない（`engine/src/hy4flash/sycl/sy_serve.h:303-308`、`engine/src/hy4flash/sycl/sy_main.cpp:379-386,459-464`）。

設定結果はプロセス内の `g_mla_batch_invariant` に保持される。MLA の split 計算はこの値と `a.M <= 16` を見て `base` を選び、後続の `TK`、tile 数、`S`、workspace サイズなどを決める（`engine/src/hy4flash/sycl/sy_mla.cpp:1652-1687`）。CLI の `--wincheck` は stdout に `wincheck p0=... M=... batch_invariant=...` を出す。通常の server / speculative decode には、この変数の値だけを示すログや専用エラー出力は見当たらない。`--wincheck` の後続比較結果は差分行の出力と最終判定で観測できるが、これは診断処理の結果であり通常生成時のログではない（`engine/src/hy4flash/sycl/sy_main.cpp:502-515`）。

## ログと測定値

`docs/DETAILS.md` と `docs/INTEL_ARC.md` には本変数固有の性能測定値がなく、この文書では速度・出力一致の測定結果を記載しない。ログ文言は `--wincheck` の `batch_invariant=%d` 表示のみで、通常経路は環境変数に関する理由ログや警告を出さない（`engine/src/hy4flash/sycl/sy_main.cpp:502`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_spec.h:15-19` — 読み取りと先頭文字判定。
- `engine/src/hy4flash/sycl/sy_serve.h:248-278,303-308` — server で speculative decode が有効になる条件と setter の呼び出し時期。
- `engine/src/hy4flash/sycl/sy_main.cpp:170-189,250-280,379-386,459-515` — CLI / 診断経路、値確認、観測出力。
- `engine/src/hy4flash/sycl/sy_mla.cpp:1652-1687` — フラグが MLA split 計算へ与える影響。
- `engine/CMakeLists.txt:23-32` — SYCL backend の独立性と実験的 build 条件。
