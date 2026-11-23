# `STRATA_GR_V70`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。`git status --short --branch` は `## main...origin/main` で、未コミット変更はない。

## 役割

hyper-connection（gated residual）のマルチトークン読みを token-split 版へ差し替える opt-in。既定の読みは 1 warp が 1 行をウィンドウ全トークン分まとめて担当するが、この読みでは 1 warp が 1 個の (row, token) を担当する（`engine/src/kernels/cuda/fused_gr.cu:1617-1625`）。down / up projection は既定カーネルと同じ演算を同じ順序で行う（`fused_gr.cu:1622-1626`）。

効くのは `fused_gr_read_multi`（1〜8 token のウィンドウ）だけで、単一トークン用の `fused_gr_read` は値にかかわらず既定カーネルのまま（`fused_gr.cu:4526-4554`）。読み取りと分岐は `gr_v70_wanted` / `gr_v70_on` / `launch_v70`、差し替えは `launch_multi` の中（`fused_gr.cu:1734-1747`, `1749-1774`, `1797-1806`）。

## 値と判定

`std::getenv("STRATA_GR_V70")` の戻り値に `std::atoi` を適用し、0 以外なら要求ありとする（`fused_gr.cu:1738`）。設定の有無だけでは決まらず、空文字も無効。大文字小文字・単位・範囲は見ず、数値の後ろの文字は無視する。

| 設定値 | `atoi` | 判定 |
|---|---|---|
| 未設定 | — | 無効（`v != nullptr` が false） |
| `""` | 0 | 無効 |
| `0` / `00` / `0x1` / `true` / `false` / `abc` | 0 | 無効 |
| `1` / `2` / `-1` / `+1` | 0 以外 | 有効（要求あり） |
| ` 1` / `1abc` | 1 | 有効（先頭の空白は読み飛ばされ、後続文字は無視される） |

コンパイル時の形状が合わない場合、`getenv` 自体が実行されない。

| 条件 | 名前の読み取り | 値の意味 |
|---|---|---|
| CUDA ビルド（`__HIPCC__` 未定義）かつ `kV70Shape` | `gr_v70_wanted` の初回呼び出しで 1 回 | 上表どおり |
| CUDA ビルドで `kV70Shape` が false | 読み取らない（`fused_gr.cu:1735-1737` の早期 return） | 常に無効 |
| HIP ビルド（`fused_gr.cu:1616`, `1804-1806`） | 該当コードがコンパイルされない | 常に無効 |
| SYCL ビルド（`fused_gr.dp.cpp`） | 同じ名前の読み取りがない | 常に無効 |

`kV70Shape` は `LR == 320 && HC == 4 && (D / 8) % 32 == 0 && N % V70_UC == 0`（`fused_gr.cu:1632`）。同梱の Flash-Next 形状（`N=2560`, `HC=4`, `D=10240`, `LR=320`）では true（`fused_gr.cu:43-46`）。

## 有効になる条件

値が 0 以外でも、次をすべて満たさないと token-split 読みは動かない。

- デバイスの compute capability が 7.0（Volta）ちょうどであること。`cur_dev_volta()` が per-device に結果を cache する（`fused_gr.cu:1404-1419`, `1739`）。
- そのカードの検査結果 `g_v70_ok[dev]` が 1 でないこと。0（未検査）か 2（bitwise 一致）なら有効、1（不一致）なら無効（`fused_gr.cu:1732`, `1746`）。
- 形状条件を満たす CUDA ビルドであること（前節）。device 側コードは sm_70 向けにだけ中身を持ち、他の arch では空（`fused_gr.cu:1633-1637`）。
- 呼び出しが `fused_gr_read_multi` → `launch_multi` の経路に到達すること。次の経路では既定読みのまま: Q8 重み（`q8_down`/`q8_up` が非 null、`STRATA_HC_Q8`）`fused_gr.cu:4284-4292`、`rdna_gr_enabled()`（`STRATA_GR_RDNA`）`fused_gr.cu:4293-4301`、v3 split 読み（`STRATA_GR_V3=1`、または 12.0 カードの既定）`fused_gr.cu:4302-4396`、gfx906 の `STRATA_GR_SPLIT=1` `fused_gr.cu:4397-4419`。
- `q8w`（`s_down != nullptr`、`STRATA_HC_REQ8`）でなく、`m.a[0].q8_mixed == nullptr`（`STRATA_QFUSE` の q8_1 出力が不要）であること（`fused_gr.cu:1780`, `1799`）。
- トークン数が 1〜8 であること（`fused_gr.cu:1757-1773`）。9 以上は 8 以下に分割されて呼ばれる（`fused_gr.cu:4470-4482`）。

`docs/SETTINGS.md:97` は「NVIDIA and AMD」とするが、実装は `#if !defined(__HIPCC__)` 内のみで、さらに sm_70 を要求する。

## 実行時の詳細

読み取りは `gr_v70_wanted` 内の `static const bool env` で、プロセス内の初回呼び出し時に一度だけ評価される（`fused_gr.cu:1738`）。以後の環境変数変更は反映されない。Volta 判定は per-device に cache され、`gr_v70_on()` は毎回 `cudaGetDevice` でカードを引き直すため、複数カードではカードごとに判定できる（`fused_gr.cu:1742-1747`）。

検査は `fused_gr_check()` で、`Verifier::init` からカードごとに一度呼ばれる（`engine/sycl/src/core/verify.cpp:637`, `fused_gr.cu:4740`）。検査が走るのは `fused_gr_selftest` に `v70` 引数が渡り、かつ `gr_v70_wanted()` が true のとき（`fused_gr.cu:4569`, `4789`）。`STRATA_HC_SPLIT=0` で読みが plain 固定の場合も、変種の検査は省いたまま token-split 読みだけを検査する（`fused_gr.cu:4773-4785`）。

self-test は 1〜8 トークン、pending write あり・なしの各条件で、plain / split / staged の既定読みと token-split 読みを bitwise 比較する（`fused_gr.cu:4684-4707`）。全条件一致なら `g_v70_ok[dev] = 2`、1 つでも違えば 1 で、そのカードでは既定読みに戻る（`fused_gr.cu:4710-4713`）。検査自体が実行できない場合（メモリ不足・セットアップ失敗）も 1 になる（`fused_gr.cu:4595-4598`）。

有効時の起動は down が `LR + (w_inject があれば HC)` ブロック × `32 * T` スレッド、up が `N / 2` ブロック × `32 * 2 * T` スレッド（`fused_gr.cu:1749-1753`）。成功すると既定カーネル群を起動せずに戻り、dispatch 統計の variant 30 として記録される（`fused_gr.cu:1799-1803`）。起動失敗時は呼び出し元が `fused_gr_read_multi: <cudaGetErrorString>` を stderr に出して `exit(1)` する（`fused_gr.cu:4423-4428`）。

## ログと測定値

検査が走った場合だけ、カードごとに次のどちらかを stderr へ出す（`fused_gr.cu:4763-4768`）。

- 一致: `strata hc: CUDA%d: STRATA_GR_V70=1: the token-split down and up reads (a warp per row and token); checked bit for bit against the default read at 1-%d tokens`
- 不一致: `strata hc: CUDA%d: STRATA_GR_V70=1 is off here: the token-split read differs from the default read: %s`

`%s` には最初の差分（`under the plain read: ...` など、`fused_gr.cu:4702-4706`）または `the check could not run (...)`（`fused_gr.cu:4712`）が入る。未設定・0・Volta 以外・形状不一致では、この変数由来のログは出ない。検査を呼ばない測定ツールでは `g_v70_ok` が 0 のままとなり、無検査で有効扱いになる（`fused_gr.cu:1746`）。

`docs/NVIDIA_V100.md:75` は「bitwise the default read; each card checks it at start-up against the default read at 1-8 tokens」と説明しており、コードと一致する。この変数を使った性能測定値は docs に見当たらないため、数値は記載しない。

## 根拠

- `engine/src/kernels/cuda/fused_gr.cu:1734-1747`（読み取り・Volta 判定・verdict）
- `engine/src/kernels/cuda/fused_gr.cu:1616-1637`, `1749-1774`（形状条件、device 側 guard、起動）
- `engine/src/kernels/cuda/fused_gr.cu:1797-1806`（差し替え条件と dispatch 統計）
- `engine/src/kernels/cuda/fused_gr.cu:4565-4573`, `4684-4713`, `4758-4768`（self-test とログ）
- `engine/src/kernels/cuda/fused_gr.cu:4284-4301`, `4423-4428`（先に return する経路、失敗時）
- `engine/src/kernels/cuda/fused_gr.cu:1404-1419`, `4526-4554`（Volta 判定の cache、単一トークン経路）
- `engine/sycl/src/core/verify.cpp:637`（`Verifier::init` からの per-card 検査）
