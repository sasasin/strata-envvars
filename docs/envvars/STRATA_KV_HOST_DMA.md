# `STRATA_KV_HOST_DMA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

KV streaming 中の prompt prefill で、新しい K/V セルを pinned RAM 上の host copy へ反映する方法を切り替える。通常経路では append kernel が staging pool と host copy の両方へ書き、DMA 経路では kernel の host copy 書き込みを止め、append 後に staging pool から host copy へコピーする。後続の reader が使う K/V の値は同じになる設計である。対象は `Prefill::run_impl` と layer-major prompt の `Prefill::lm_run` にある QSA append 経路で、token decode や verify の読み取り箇所はない（`engine/src/prefill/prefill.cpp:4214-4219,5265-5307,8435-8439,9377-9412`、`engine/include/strata/core/kv_host_dma.hpp:1-13`）。

## 値と判定

どの経路も文字列全体や数値として parse せず、先頭 1 文字だけを判定する。空白、大文字小文字、後続文字を検証しない。たとえば `1anything` は先頭が `1` として扱われる。

| ビルド／経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA（通常の `engine/src/prefill/prefill.cpp`） | ON | 先頭が `1`（`1`, `1yes`） | 先頭が `0`（`0`, `0anything`）は OFF。その他（空文字、`true`、`2`、空白始まりなど）は既定値 ON |
| HIP（同ファイルの `STRATA_USE_HIP` 分岐） | OFF | 先頭が `1`（`1`, `1yes`） | それ以外はすべて OFF（空文字、`0`, `true`, `2` を含む） |
| SYCL prefill の `STRATA_USE_HIP` build | OFF | 先頭が `1` | それ以外はすべて OFF |
| SYCL prefill の `STRATA_USE_HIP` なし | 常に OFF | なし。環境を読み取らない | すべて OFF |

CUDA の既定値と `1`/`0` 以外の fallback は `kv_host_dma_on(env, true)` が決める。HIP と SYCL-HIP 分岐は `e && e[0] == '1'` で直接判定するため、共通 helper と異なりその他の文字列を既定値へ戻さない（`engine/include/strata/core/kv_host_dma.hpp:18-24`、`engine/src/prefill/prefill.cpp:5271-5275,9377-9381`、`engine/sycl/src/prefill/prefill.cpp:3601-3605`）。

## 有効になる条件

- session の QSA state が `kv_mode == 1`（streamed）であること。通常は CLI の `--kv-resident` が KV streaming を選ぶ。`kv_mode` が 1 でない場合、変数が ON でも切替は使われない（`engine/src/program/generate.cpp:1235,3907`、`engine/include/strata/core/layer.hpp:234-243`、`engine/src/prefill/prefill.cpp:5250-5251,9369-9370`）。
- CUDA/HIP の共通経路では staging pool が存在することも必要で、`kv_host_dma_use` は `on && staged && stage_present` の場合だけ true を返す。条件を満たさなければ append kernel に host copy を渡す従来経路になる（`engine/include/strata/core/kv_host_dma.hpp:26-27`、`engine/src/prefill/prefill.cpp:5276-5277,9382-9383`）。SYCL の同分岐は `staged` と build 時の switch を使い、staging pool がない場合には DMA 経路へ入らない（`engine/sycl/src/prefill/prefill.cpp:3580-3582,3601-3607`）。
- `st.kv_hybrid`（K8V4 hybrid）ではこの変数による経路変更はない。hybrid 分岐は `host_w` と `host_by_dma` を使わず、host 側の各 half を `kv_append` に渡して直接ミラーする（`engine/src/prefill/prefill.cpp:5277-5290,9383-9396`、`engine/sycl/src/prefill/prefill.cpp:3607-3620`）。
- 通常の CUDA prefill build は既定 ON、HIP build は既定 OFF。SYCL prefill では `STRATA_USE_HIP` が定義された build のみ環境値を読み、それ以外は `constexpr false` で固定される（`engine/src/prefill/prefill.cpp:5271-5275,9377-9381`、`engine/sycl/src/prefill/prefill.cpp:3601-3605`）。
- CLI 引数や別の環境変数が `STRATA_KV_HOST_DMA` の値を上書きする処理は、この変数の読み取り経路にはない。CLI の `--kv-resident` は切替値ではなく、DMA 経路が成立する streaming state を選ぶ条件である（`engine/src/prefill/prefill.cpp:5250-5251,5276-5277`）。

## 実行時の詳細

各経路の関数内 `static` で初回評価時に一度だけ `getenv` する。CUDA/HIP main prefill と layer-major prefill はそれぞれ別の `static` 変数を持ち、どちらも最初に実行された QSA append の時点で cache する。SYCL prefill も同じく `run_impl` 内で cache する。したがって、該当する経路の初回評価後にプロセス内で環境を書き換えても反映されない。SYCL の `STRATA_USE_HIP` なし build は環境を読み取らない（`engine/src/prefill/prefill.cpp:5271-5275,9377-9381`、`engine/sycl/src/prefill/prefill.cpp:3601-3606`）。

有効な DMA 経路では通常の K/V append（FP16/INT8/Q4 など）が `host_w == nullptr` と staging pool を受け取り、続いて `kv_unstage_to_host` が当該 chunk の `[p0 / page_size, ceil((p0 + T) / page_size))` block を host copy へコピーする。コピーは同じ stream/queue に積まれる。無効時は `&st.host` を append に渡し、DMA copy を追加しない（`engine/src/prefill/prefill.cpp:5276-5306,9382-9412`、`engine/sycl/src/prefill/prefill.cpp:3606-3636`、`engine/include/strata/kernels/kv_stream.hpp:122-126`）。

Strata の `docs/SETTINGS.md` は NVIDIA/AMD/Intel Arc 向け、`docs/TROUBLESHOOTING.md` は NVIDIA 既定 ON・AMD/Intel Arc 既定 OFF と説明している。一方、現行 SYCL prefill source は `STRATA_USE_HIP` がないと環境値にかかわらず OFF であり、Intel Arc の通常の SYCL 経路に当てはめた記述とは一致しない（`docs/SETTINGS.md:412`、`docs/TROUBLESHOOTING.md:325-327`、`engine/sycl/src/prefill/prefill.cpp:3601-3606`）。

## ログと測定値

値の読み取りや DMA 経路選択だけを知らせる専用ログはない。CUDA の unstage copy が失敗した場合は `engine/src/kernels/cuda/kv_stream.cu:361-368` から `check("unstage")` に進み、stderr に `kv_stream: unstage: <CUDA error text>` を出して `exit(1)` する（同 `:15-20`）。SYCL の copy で例外が発生した場合は `engine/sycl/src/kernels/cuda/kv_stream.dp.cpp:460-480` の catch が例外文と file/line を stderr に出し、`exit(1)` する。

ソースコメントには RTX 5090 での約 `0.24 GB/s`、prompt token あたり `50 us` という旧経路の値があるが、モデル・量子化・OS・測定回数などの条件が示されていないため、比較可能な測定値としては記載しない（`engine/include/strata/core/kv_host_dma.hpp:9-13`）。

## 根拠

- 直接の環境読み取り全件（CUDA/HIP main prefill 2 箇所、SYCL prefill 1 箇所）: `engine/src/prefill/prefill.cpp:5271-5276,9377-9382`、`engine/sycl/src/prefill/prefill.cpp:3601-3607`。
- 値の共通判定と streaming/staging 条件: `engine/include/strata/core/kv_host_dma.hpp:18-27`。
- append と host DMA copy の分岐: `engine/src/prefill/prefill.cpp:5276-5306,9382-9412`、`engine/sycl/src/prefill/prefill.cpp:3606-3636`。
- staging state と形式: `engine/include/strata/core/layer.hpp:234-243`。
- copy 実装と失敗経路: `engine/src/kernels/cuda/kv_stream.cu:361-368`、`engine/sycl/src/kernels/cuda/kv_stream.dp.cpp:460-480`。
