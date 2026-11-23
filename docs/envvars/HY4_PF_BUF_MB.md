# `HY4_PF_BUF_MB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`strata-hy4` の hybrid prefill streaming が確保する expert scratch buffer の容量上限を MiB 単位で指定する。設定値は `cap_limit` として使われ、CPU-tier expert を GPU に転送する際の scratch buffer 分割サイズと、adaptive vcache から VRAM を回収する目標量の計算に関係する。実際に確保される容量そのものを指定する値ではなく、空き VRAM 等により小さくなる場合がある。読み取りは `Runner::pf_init()` 内の 1 箇所だけである（`engine/src/hy4flash/run/hy4_graph.hip.h:545-596`）。

この経路は `strata-hy4` の CUDA または HIP ビルドに含まれる。CMake の `STRATA_BUILD_HY4` は既定 OFF で、CUDA/HIP のいずれかを要求する。共通の HY4 GPU ソースは CUDA ビルドでは CUDA 言語、そうでなければ HIP 言語としてコンパイルされる（`engine/CMakeLists.txt:846-890`）。

## 値と判定

値の有無は `getenv("HY4_PF_BUF_MB")` で判定し、設定されていれば `atoi()` の結果を `std::max(64, ...)` で最低 64 にし、`size_t` に変換して `<< 20` する。したがって単位換算は 1 MiB = 1,048,576 bytes で、最大値の clamp や文字列全体の検証はない。`atoi` は先頭の空白と符号を扱い、数値として読める先頭部分の後ろは判定されない。数値として読めない文字列は 0 として扱われる。`atoi` で `int` の範囲を超える値の動作はコードで検査されていない（`engine/src/hy4flash/run/hy4_graph.hip.h:587`）。

| 条件 | 未設定 | 設定時の有効値の例 | 下限に丸められる値の例 |
|---|---|---|---|
| `pf_init()` が呼ばれる場合 | GPU 総 VRAM `tot` に応じて 96 / 160 / 256 / 384 MiB（下表） | `64` → 64 MiB、`128` → 128 MiB、`128junk` → 128 MiB | 空文字、`0`、`-1`、`63`、`true`、`0anything` → 64 MiB |

未設定時の既定値は `hipMemGetInfo()` が返す総 VRAM で分かれる。明示的な空文字は「未設定」ではなく、`atoi("") == 0` を経て 64 MiB になる（`engine/src/hy4flash/run/hy4_graph.hip.h:579-587`）。

| GPU 総 VRAM | `HY4_PF_BUF_MB` 未設定時の `cap_limit` |
|---|---:|
| 20 GiB 以上 | 384 MiB |
| 14 GiB 以上 20 GiB 未満 | 256 MiB |
| 9 GiB 以上 14 GiB 未満 | 160 MiB |
| 9 GiB 未満 | 96 MiB |

## 有効になる条件

- `strata-hy4` を CUDA または HIP 対応でビルドし、CPU RAM 上の expert を使う hybrid 配置になる必要がある。`Runner` は `g.cpu_mask` が空でない場合に CPU expert を初期化して `hyb = true` にする（`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583`）。
- `HY4_PF_STREAM` が未設定、または `atoi()` が 0 以外である場合に限り `pf_init()` が呼ばれる。`HY4_PF_STREAM=0`、空文字、数値で始まらない値などでは streaming 初期化を行わず、この変数も読まれない（`engine/src/hy4flash/run/hy4_graph.hip.h:1706-1708`）。
- CPU expert body が見つからず `maxb == 0` の場合、`pf_init()` は環境変数を読む前に戻る（`engine/src/hy4flash/run/hy4_graph.hip.h:545-562`）。
- `HY4_PF_BOUNCE` はバッファ上限の値を変えないが、ホスト arena を直接 pin するか bounce ring を使うかを変え、1-buffer 分岐に入れる条件に影響する。Windows では arena pin 試行がなく、bounce ring 経路になる。非 Windows では RAM headroom、`HY4_PF_BOUNCE`、`hipHostRegister()` の成否により arena pin の可否が決まる（`engine/src/hy4flash/run/hy4_graph.hip.h:563-578`）。
- `HY4_PF_MIN_T` と `HY4_PF_GATHER_MAX_T` は streaming が有効になった後の chunk サイズ別の適用経路に影響する。初期値はそれぞれ 128 と 4096 token で、`HY4_PF_MIN_T` 以上で `pf_active()`、bounce buffer がある場合はさらに `HY4_PF_GATHER_MAX_T` 未満で active-expert gather を使う（`engine/src/hy4flash/run/hy4_graph.hip.h:371-406,639-646`）。
- 空き VRAM が `margin + tables_est + 2 * cap_limit` に足りず adaptive vcache の slot が複数ある場合、Strata は `vcache_release_vram(want_fr)` を呼び、空きが目標に届くまで末尾 slab を解放する。回収量は目標に届くとは限らず、解放時は `[vcache] released ...` を stderr に出す（`engine/src/hy4flash/run/hy4_graph.hip.h:588-596,1021-1056`）。

## 実行時の詳細

`HY4_PF_BUF_MB` は `Runner` 初期化中の `pf_init()` で読み、その値を `cap_limit` に保持する。リクエストごとの再読込や環境変数の cache 更新はないため、初期化後のプロセス環境変更は反映されない。CLI 引数による同じ値の上書きはこの読み取り経路にはない（`engine/src/hy4flash/run/hy4_graph.hip.h:545-647,1706-1708`）。

`cap_limit` はまず `want_fr = margin + tables_est + 2 * cap_limit` の計算に入り、必要なら adaptive vcache の VRAM 回収目標に使われる。続く実容量 `cap` は次の分岐で決まる。

- 非 bounce の arena pin が使え、空き VRAM が最大 layer の expert body 合計 `maxb` 以上、かつ総 VRAM が 48 GiB 以上なら、1 buffer として `cap = maxb` を使う。この経路では `cap_limit` が `cap` の上限にはならない。
- それ以外は 2 buffer とし、各 buffer は `min(cap_limit, floor_to_4_KiB(avail / 2))`。従って空き VRAM が少なければ指定値より小さくなる。`avail` は `margin + tables_est` を空きから差し引いた値である（`engine/src/hy4flash/run/hy4_graph.hip.h:581-596`）。
- `cap` が 64 MiB 未満なら scratch buffer を確保せず、`pf_init()` は streaming を無効のまま戻る。bounce ring の pinned host allocation に失敗した場合は容量を半分ずつ下げて試し、64 MiB 以上で確保できなければ同様に戻る（`engine/src/hy4flash/run/hy4_graph.hip.h:597-621`）。

成功すると各 buffer 用 GPU scratch を確保し、`pf_stream = true` にして expert groups を作る。prefill chunk では `T >= pf_min_T` のとき streaming が active となり、GPU scratch を使って CPU-tier expert を転送・計算する。chunk が gather 範囲なら必要な active expert だけを集め、そうでなければ layer groups を pipeline する。group の分割にも `pf_cap` が使われる（`engine/src/hy4flash/run/hy4_graph.hip.h:405-406,416-481,601-646,2473-2586,3399-3444`）。

## ログと測定値

初期化成功時は stderr に `[hybrid] prefill streaming on (...)` として buffer 数・容量・group 数・pass あたり転送量・適用 token 閾値を出す（`engine/src/hy4flash/run/hy4_graph.hip.h:539-542`）。空き VRAM が不足する場合は `[hybrid] prefill streaming disabled: no room for a scratch buffer ...`、bounce ring を確保できない場合は `[hybrid] prefill streaming disabled: cannot allocate ... pinned bounce ring (WDDM/commit limit)` を出す（同 `:597-619`）。CPU expert body がない場合や `HY4_PF_STREAM` により `pf_init()` が呼ばれない場合、この変数に関するログはない。

測定値は該当する Strata 資料に見つからないため記載しない。GPU runtime の確保等が `HCK` で失敗した場合、Strata は `HIP error %d (%s) at %s:%d` を stderr に出して終了コード 3 で終了する（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34`）。

## 根拠

- `engine/src/hy4flash/run/hy4_graph.hip.h:545-647` — 値の読み取り、既定値、上限・容量計算、割当、streaming 初期化。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583,1706-1708` — hybrid 状態と初期化呼び出しの条件。
- `engine/src/hy4flash/run/hy4_graph.hip.h:405-406,416-481,2473-2586,3399-3444` — chunk の適用条件と expert streaming/gather の処理。
- `engine/src/hy4flash/run/hy4_graph.hip.h:1021-1056` — adaptive vcache の VRAM 回収とログ。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34` — GPU runtime エラー時の Strata 側終了経路。
- `engine/CMakeLists.txt:846-890` — HY4 target の build 条件と CUDA/HIP ソース設定。
