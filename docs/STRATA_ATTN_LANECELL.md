# `STRATA_ATTN_LANECELL`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA attention の batch 版 `qsa_decode_attn_batch` における、スコア計算（score phase）の thread 割り当てを変えます。

- 無効（既定のコード）: 1 block（`THREADS = 256` = 8 warp）が `CHUNK = 64` cell の chunk を warp ごとに分担します。lane が 256 次元（`HD`）のうち 8 次元分の部分和を持ち、head ごとに `warp_sum`（xor 16, 8, 4, 2, 1 の 5 回 shuffle）で縮約します。cell あたり 12 head × 5 回の shuffle 交換が必要です（`src/kernels/cuda/qsa_decode_attn.cu:200-238`）。
- 有効（`LANE_CELL = true` の template instantiation）: thread `t` が cell `t % 64` について、head `(t / 64) * 3` .. `+2` の 3 本（`HPT = G * CHUNK / THREADS = 12 * 64 / 256 = 3`）を単独で計算します。32 個の 8 次元部分和を自分の local に持ち、`warp_sum` が lane 0 で実行されるのと同じ順（`o = 16 .. 1`）で butterfly を閉じるため、shuffle 縮約が不要になります（`src/kernels/cuda/qsa_decode_attn.cu:165-198`）。

スコア以降（chunk max、exp-sum、value 蓄積、merge kernel）は両経路で同じコードです（`src/kernels/cuda/qsa_decode_attn.cu:239-280`）。実装注釈は「bit-identical scores」（同じ operand、同じ加算順）と説明します（`src/kernels/cuda/qsa_decode_attn.cu:166-169`）。

読み取り箇所は batch 関数だけです。単一 query 用の `qsa_decode_attn_step`（`src/core/layer.cpp:1138` から呼ばれる）には lane-cell 分岐がなく、この変数の影響を受けません。

`qsa_decode_attn_batch` が呼ばれる経路:

- verify window（decode）: `src/core/verify.cpp:1376`（`n_q = 1` の行ごと経路）、`src/core/verify.cpp:1391`（batch 経路）
- MTP drafter: `src/core/mtp.cpp:825`
- prompt: tensor-core の `qsa_prompt_attn_batch` が geometry 不一致で false を返すか `STRATA_PROMPT_ATTN_OLD` が設定されたとき、decode kernel への fallback（`src/prefill/prefill.cpp:2843-2851`）

## 値と判定

文字列全体を parse しません。`std::getenv` の結果が non-null で、かつ先頭文字 `v[0] == '1'` のときだけ有効です（`src/kernels/cuda/qsa_decode_attn.cu:638`、`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:601`）。

| 状態 | 判定 |
|---|---|
| unset | CUDA / SYCL / gfx1151 以外の AMD: 無効。HIP ビルド + gfx1151: `apply_arch_defaults` が `"1"` を設定するため有効 |
| 空文字 | 無効（`v[0]` は `\0`）。gfx1151 では「ユーザーが設定した」状態として保持され、既定値で上書きされない |
| `1`, `10`, `1anything` | 有効 |
| `0`, `true`, `TRUE`, ` 1`, `2` など先頭文字が `1` でないもの | 無効 |

大文字小文字、空白、後続文字、数値としての妥当性は検査されません。

判定結果は `qsa_decode_attn_batch` 内の `static const bool` に保存されます。プロセス内で最初の呼び出し以降は再評価されません（`thread_local` ではないので全スレッドで共有）。読み取りは geometry 校验（`src/kernels/cuda/qsa_decode_attn.cu:621-625`）を通った後の初回呼び出しです。

## 既定値と優先順位

- `src/core/arch_defaults.cpp:49` の gfx1151（Strix Halo）テーブルに `{"STRATA_ATTN_LANECELL", "1"}` があります。
- `apply_arch_defaults`（`src/core/arch_defaults.cpp:61-71`）は `getenv(name) != nullptr` の名前を一切上書きしません（コメント "the user's setting wins, whatever it is"）。未設定のときだけ Linux では `setenv(name, "1", 0)`、Windows では `_putenv_s` で `"1"` を入れます。
- このテーブルを呼ぶのは `#if defined(STRATA_USE_HIP)` の下の block だけです（`src/program/generate.cpp:2152-2159`）。CUDA ビルドは GPU 0 の `gcnArchName` が gfx1151 でもこの関数を呼びません（`src/core/arch_defaults.cpp:19-20` のコメントも同じことを述べています）。SYCL ビルドは `STRATA_USE_HIP` を定義しないため、`sycl/CMakeLists.txt` に定義がなく、`sycl/src/program/generate.cpp:1970-1977` の guard は効きません。
- したがって「既定 ON」は HIP ビルド + gfx1151 の場合に限られます。`STRATA_GFX1151_DEFAULTS=0`（先頭文字 `0`）ならテーブル全体が空になり、この変数は未設定のままなら無効です（`src/core/arch_defaults.cpp:33-34`）。
- 設定された名前は起動時 stderr の一行ログに `STRATA_` を除いた形（`ATTN_LANECELL`）で列挙されます（`src/core/arch_defaults.cpp:74-79`）。

## 有効になる条件

- `qsa_decode_attn_batch` が実際に呼ばれること。
- `STRATA_ATTN_PRE75`（PR #540 の kernel）より優先されます。lane-cell 分岐は `pre75_attn()` を経由せず `attn_chunk_kernel<M, true>` を launch します（`src/kernels/cuda/qsa_decode_attn.cu:652-657` と `608-613` の macro の適用順）。sm_70 以下や gfx103x でも、有効時は lane-cell kernel が選ばれます。
- gfx906 の opt-in query LDS swizzle と両立しません。コンパイル時 `static_assert(!QUERY_SWIZZLE || !LANE_CELL, "query swizzle is for warp scoring only")`（`src/kernels/cuda/qsa_decode_attn.cu:147`）、実行時 `use_query_swizzle = query_swizzle && !lane_cell && kv_mode == 1 && query_swizzle_gfx906_device()`（`src/kernels/cuda/qsa_decode_attn.cu:643`）。`STRATA_ATTN_LANECELL=1` にすると `STRATA_GFX906_ATTN_QUERY_SWIZZLE=1` は効かなくなります。
- launch 構成（grid `(n_chunks, n_head_kv, n_q)`、`THREADS = 256`）と KV フォーマット分岐（mode 0 = fp16、1 = int8、2 = Q4_0、3 = K8V4 hybrid）は両経路で同じです。SYCL では `reqd_sub_group_size(32)`（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:623-636`）。

## 実行時の詳細

- 有効時、thread は `float a[3][32]`（96 float）を local に確保します。SYCL 移植では DPCT1110 の警告コメントがこの register pressure を指摘しています（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:111-116`）。
- masked cell（`c >= n_here`、または page が resident でなく `srow[c] < 0`）は両経路で `-FLT_MAX`（`src/kernels/cuda/qsa_decode_attn.cu:172-174` と `202-204`）。
- この変数自身の有効化ログはありません。観測できる出力は、gfx1151 既定テーブルの起動時一覧（`src/core/arch_defaults.cpp:74-79`）と、`STRATA_GFX906_ATTN_QUERY_SWIZZLE_TRACE` の trace 行の `lane_cell=%d` フィールド（`src/kernels/cuda/qsa_decode_attn.cu:644-650`）だけです。

## 測定値

- 実装注釈（`src/kernels/cuda/qsa_decode_attn.cu:166-169`）は、この分岐が cell あたり 12 回の shuffle 縮約を省くことを設計意図として述べています。
- 追加コミット `8b30b1d5` のメッセージには、旧経路のスコア phase が gfx1151 で T=1 あたり layer 約 53 µs、window row ごとに +32 µs だったという記載があります（モデル・量子化・測定回数は示されていません）。これはコミットメッセージ中の主張であり、本調査で確認したものではありません。
- `docs/STRIX_HALO.md:85-88` は、この switch 単独の速度向上を記載していません。gfx1151 既定テーブル全体について「maintainers' box で byte-identical output（同じ token ids、4K / 32K / 64K、四つのモデル、kernel ごとの bitwise harness）、速度を変え、答えを変えない」と記載しています。この記載は CUDA や他の AMD アーキテクチャには適用されるとは書かれていません。

## 根拠

- `src/kernels/cuda/qsa_decode_attn.cu:20-24`（`HD`、`G`、`CHUNK`、`THREADS`、`WARPS`）
- `src/kernels/cuda/qsa_decode_attn.cu:117`（`template <int KV_MODE, bool LANE_CELL = false, ...>`）
- `src/kernels/cuda/qsa_decode_attn.cu:147`（swizzle と lane-cell の排他 `static_assert`）
- `src/kernels/cuda/qsa_decode_attn.cu:165-198`（lane-cell の score phase）
- `src/kernels/cuda/qsa_decode_attn.cu:200-238`（warp-scoring 側）
- `src/kernels/cuda/qsa_decode_attn.cu:638`（env 読み取りと `static const bool`）
- `src/kernels/cuda/qsa_decode_attn.cu:643`（gfx906 swizzle の `!lane_cell` 条件）
- `src/kernels/cuda/qsa_decode_attn.cu:652-657`（`attn_chunk_kernel<M, true>` の launch 分岐）
- `src/kernels/cuda/qsa_decode_attn.cu:716-756`（`qsa_decode_attn_step` に分岐がないこと）
- `src/core/arch_defaults.cpp:33-34`、`49`、`61-71`、`74-79`
- `src/program/generate.cpp:2152-2159`（`STRATA_USE_HIP` guard）
- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:110`、`179-215`、`601`、`639-643`
- `sycl/src/program/generate.cpp:1970-1977`
- `docs/STRIX_HALO.md:85-95`
