# `FNX_PF_RING_SM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata-split` の prompt prefill で、各 layer の attention / FFN chunk sum に使う方式を選ぶ。未設定または 0 なら copy-engine ring 側（`ring_async` または `pf_ring`）、非 0 なら GPU-thread ring の `ring_sum` を使う。通常の `strata` engine の設定ではなく、`STRATA_BUILD_SPLIT` が有効な場合に追加される sFNX engine 用である。`FNX_PF_RING_SM` の直接読み取りは `Engine::prefill_alloc` 内の一箇所である（`engine/src/split/src/prefill.cu:854-856,967-975`）。

## 値と判定

`env_int` は環境変数全体を base 10 の `long long` として parse する。先頭は `+`、`-` または数字でなければならず、後続は数字のみ、末尾まで消費され、`long long` の範囲内である必要がある。空白、空文字、末尾の文字、範囲外の値は無効で、`<名前>: '<値>' is not a whole number` の例外になる。parse 後は `!= 0` のみを判定し、範囲制限はない（`engine/src/split/src/env.hpp:15-21,33-40`; 読み取り箇所 `engine/src/split/src/prefill.cu:967`）。

| 条件 | unset | 有効になる値（例） | 無効・OFF になる値（例） |
|---|---|---|---|
| split engine の prefill buffer 初期化 | 既定値 `0` で OFF | `1`, `-1`, `+2` など、parse できる任意の非 0 整数 | `0`, `-0` は parse 成功して OFF。`true`, `0anything`, 空文字、前後の空白、整数範囲外は無効値として例外 |

## 有効になる条件

- `STRATA_BUILD_SPLIT=ON` で sFNX engine がビルドされ、Engine の prompt prefill buffer 初期化まで到達する必要がある。split は opt-in で、2–4 枚用の CUDA/HIP target として定義されている（`engine/CMakeLists.txt:922-927`; `engine/src/split/CMakeLists.txt:1-5,116-146`）。
- 影響するのは prompt prefill の chunk sums だけで、decode の ring 設定 `FNX_RING_F32` を切り替えるものではない（`engine/src/split/src/prefill.cu:340-347,967-975`; `engine/src/split/src/engine.cu:978-980,1032`）。
- 非 0 のとき `p->overlap` は `false` になるため、`FNX_PF_OVERLAP` が非 0 でも copy-engine ring の overlap は使わない。NVIDIA では `hcs` も `false` になり、`FNX_PF_HCSPLIT` が非 0 でも HCSPLIT は有効にならない（`engine/src/split/src/prefill.cu:1064-1094`）。
- HIP で RCCL が設定されていても、この分岐では `pf_ring` ではなく `ring_sum` が呼ばれるため、chunk sum は RCCL 分岐を通らない（`engine/src/split/src/prefill.cu:1014-1020,1693-1699,1762-1769`; RCCL 呼び出しは `engine/src/split/src/prefill.cu:723-740`）。
- `FNX_PF_ROWS` など CLI 引数との優先順位・上書きはなく、この変数は環境から直接読み取られる（`engine/src/split/src/prefill.cu:967`; 関連する初期化条件 `1064-1094`）。

## 実行時の詳細

`Engine` の構築中に `prefill_alloc()` が呼ばれ、カードごとの `Pf` を作る際に値を読み込む。`static` cache はなく、この初期化時の値がその `Pf` の `ring_sm` に保持されるため、同じ Engine の実行中に環境を変えても再読込されない（`engine/src/split/src/engine.cu:317-318`; `engine/src/split/src/prefill.cu:854-867,967`）。通常の sfnx 起動では Engine を作ってから server を開始する（`engine/src/split/tools/sfnx.cpp:1122-1139`）。

非 0 の場合、既存の ring 設定を基に prompt 用 ring を設定し直し、fp16 sum、`pf_c_` 行容量の ring buffers を `hpalloc` で確保する。その後 attention sum は `ring_sum(..., p.bo_a, ...)`、FFN sum は `ring_sum(..., p.bo_f, ..., m)` に渡される。0 / unset の場合はこれらの呼び出しを通らず、overlap が有効なら `ring_async`、無効なら `pf_ring` を使う（`engine/src/split/src/prefill.cu:967-975,1693-1699,1762-1769`）。`ring_sum` は chunk サイズと ring 設定に応じて GPU kernel を選ぶ（`engine/src/split/src/kernels.cu:1582-1614`）。

## ログと測定値

この変数自体の ON/OFF を示す成功ログは実装にない。整数でない値などを指定すると helper が例外を投げ、sfnx の Engine 構築失敗経路では stdout に `ERR <例外文言>`、stderr に `sfnx: failed: <例外文言>` を出し、終了コード 1 で終了する（`engine/src/split/src/env.hpp:33-40`; `engine/src/split/tools/sfnx.cpp:1097-1103,1122-1135`）。

`docs/SPLIT_ENGINE.md:89-90` は copy-engine ring と `FNX_PF_RING_SM=1` の GPU-thread ring で末尾 bit の算術が異なり、同資料の suite では 61 件中 39 件の回答が一致したと記している。これは資料に記載された結果であり、本調査で測定・再実行した値ではない。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-40` — 整数 parse と無効値例外。
- `engine/src/split/src/prefill.cu:854-867,967-975` — 読み取り時期、値判定、prompt ring buffer の設定。
- `engine/src/split/src/prefill.cu:1064-1094,1693-1699,1762-1769` — overlap / HCSPLIT の条件と chunk sum 呼び出し。
- `engine/src/split/src/kernels.cu:1582-1614` — `ring_sum` の分岐と kernel dispatch。
- `engine/src/split/tools/sfnx.cpp:1097-1103,1122-1135` — 初期化エラーの観測方法。
- `engine/src/split/CMakeLists.txt:1-5,116-146`; `engine/CMakeLists.txt:922-927` — split engine の build 条件。
