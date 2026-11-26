# `STRATA_HIP_WMMA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP の QSA prompt attention で、int8 K/V の注意計算を RDNA3/RDNA4 の matrix-core WMMA kernel に切り替える要求値。decode attention 全般を切り替えるものではない。HIP 用 `qsa_prompt_attn_batch` が利用条件を満たしたときだけ `launch_wmma` を呼び、通常の prompt 経路の attention 出力を作る。CUDA ビルドではこの分岐が `__HIPCC__` の内側にあり、この変数で CUDA tensor-core 経路は切り替わらない（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2509-2518`）。

値 `1` は有効な GPU で強制要求、`auto` は gfx12 の呼び出しごとの閾値判定、未設定相当は gfx12 Linux の既定動作を使う。WMMA と従来 kernel は加算順が異なり、出力の最下位 bit は一致しない（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2236-2249`）。

## 値と判定

`hip_wmma_mode_env()` は初回呼び出し時に `std::getenv` の結果を関数内 `static` に保存する。文字列全体の比較ではなく、空でない値の先頭文字が `'1'` なら強制モード、文字列全体が小文字の `auto` と一致すれば自動モード、それ以外は off。数値 parse や trim、大文字小文字変換はしない（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2242-2250`）。

| 条件 | unset / 空文字 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| HIP kernel | mode `-1`。gfx12 Linux では既定 ON、gfx12 Windows と gfx11 では OFF。ただし後述する起動時アーキテクチャ既定値が unset を `1` にする場合がある | 先頭文字が `1` の値（`1`, `10`, `1anything`）は強制。gfx12 のみ完全一致 `auto` は自動選択 | `0`, `0anything`, `true`, `false`, `AUTO`, ` auto` などは off |
| SYCL 側に残る HIP 条件付き実装 | unset / 空文字は要求なし | 先頭文字が `1` の値 | `auto` を含み、先頭文字が `1` でない値は要求なし（`engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1922-1927`） |

明示的な空文字は mode 判定では unset と同じだが、アーキテクチャ既定値適用時には「環境変数が設定済み」として保持されるため、自動的に `1` へ置き換わらない。既定値適用側は値の内容ではなく `getenv(...) != nullptr` を見ている（`engine/src/core/arch_defaults.cpp:307-310,334-339,406-410`）。

`auto` は gfx12 以外では選択しない。gfx12 では `n_q >= STRATA_HIP_WMMA_MIN_Q` かつ `cap >= STRATA_HIP_WMMA_MIN_CAP` のときだけ選択し、既定閾値はそれぞれ 64 と 0。閾値は別々の関数内 `static` で初回評価され、設定値は `std::atoll` で変換される。文字列全体の妥当性・範囲を検証せず、末尾文字を検査せず、変換できない文字列は 0 になるため、例えば `12junk` は 12、`junk` は 0 として扱われる。負値も拒否されず、比較値として使われる（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2280-2285`）。

## 有効になる条件

- HIP build であること。CUDA build の同名カーネル実装では AMD 用 WMMA 分岐に入らない（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2509-2518`）。
- 現在の device が gfx11 WMMA 対応機種または gfx12 であること。device 情報の取得失敗、device index が 0–63 の範囲外、その他の GPU では利用しない（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2253-2262,2289-2292`）。
- `auto` の場合は gfx12 かつ両閾値を満たすこと。gfx11 は `auto` では使わず、明示 `1` が必要（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2280-2295`）。
- HIP の prompt staging ring にも影響する。通常の HIP `prefill.cpp` は `qsa_prompt_attn_matrix_cores_requested()` を使うため、gfx12 既定 ON や `auto` の選択も反映する。WMMA が要求され、`STRATA_PREFILL_RING` と内部 ring override が未指定なら、長い chunk で通常 96 slot の ring を選ぶ（`engine/src/prefill/prefill.cpp:843-850`; helper: `engine/src/kernels/cuda/qsa_prompt_attn.cu:2433-2448`）。一方、SYCL 側 `prefill.cpp` に残る HIP 条件付き分岐は環境変数を独自に一度読み、先頭文字が `1` の場合だけ同じ 96 slot 経路を選ぶ。したがって `auto` はこの直接判定を通らず、`STRATA_PREFILL_RING` の明示値または内部 override があればこの既定経路を通らない（`engine/sycl/src/prefill/prefill.cpp:291-300`）。
- K と V の両方が int8 (`k_q`, `v_q`, `k_scale`, `v_scale` が存在) し、Q4 K/V pool がなく、head dimension と head grouping がこの kernel のコンパイル形状に一致し、`cap > 0`、selection ids / steps / page table が存在すること。条件外では `false` を返し、呼び出し側が通常 attention を実行する（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2513-2517`; fallback: `engine/src/prefill/prefill.cpp:5556-5569`）。
- prompt の gated attention ではこの QSA 呼び出しを通らない（`engine/src/prefill/prefill.cpp:5556`）。
- gfx12 Linux は mode が unset のままでも既定 ON。gfx12 Windows は既定 OFF で `1` か `auto` が必要。gfx11 の離散 RDNA3 では通常起動時にアーキテクチャ既定値がこの変数を `1` にするが、`STRATA_GFX11_DEFAULTS=0`、`STRATA_GFX11_WMMA_DEFAULTS=0` または `STRATA_DEFAULTS=026` でその既定値適用を止められる。ユーザーが値を設定していれば（空文字を含む）上書きしない（`engine/include/strata/core/gfx11_extra.hpp:27-37,90-110`; 適用: `engine/src/core/arch_defaults.cpp:312-345`）。
- 統合 GPU の matrix-core prompt set は機種・OS 条件で起動時に `1` を設定する場合がある。`STRATA_IGPU_DEFAULTS=0` は無効化し、`STRATA_IGPU_PROMPT_SET=0` も set を無効化する。gfx1151 Windows は set が既定有効、gfx1103 Linux も既定有効。離散 GPU 混在時は「全ての可視 GPU が統合 GPU かつ同じ arch」という適用条件を満たさない（`engine/src/core/arch_defaults.cpp:124-138,172-180,193-200`; 判定・適用: `engine/src/program/generate.cpp:4291-4320`）。
- kernel の起動エラー後は `g_wmma_failed` が立ち、そのプロセスでは以後 WMMA を使わない。別の `qsa_prompt_attn_batch` 不成立と同様、prefill 呼び出し元が通常 attention に進む（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2286-2289,2366-2371`; `engine/src/prefill/prefill.cpp:5556-5569`）。

## 実行時の詳細

HIP の `generate` 初期化は GPU の arch を調べ、各 engine switch を初めて読む前に `apply_arch_defaults` を呼ぶ。未設定の対象変数だけを OS に応じて `setenv(..., 0)` または `_putenv_s` で設定し、ユーザー値を保つ。アーキテクチャの既定表は gfx11 離散カードの matrix-core set や一部 iGPU に `STRATA_HIP_WMMA=1` を含む（`engine/src/program/generate.cpp:4287-4320`; `engine/src/core/arch_defaults.cpp:218-224,302-345,406-420`; `engine/include/strata/core/gfx11_extra.hpp:90-110`; `engine/src/core/arch_defaults.cpp:172-215`）。

カーネル側の mode は最初の WMMA 利用判定時に一度 cache されるため、その後プロセス環境を変更しても反映されない。device arch も device ごとに cache される。gfx12 で `auto` が選ばれた場合、query 数と `cap` を呼び出しごとに閾値と比較するが、閾値自体は初回に cache する（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2242-2250,2254-2276,2280-2285`）。

適用対象の attention batch が `qsa_prompt_attn_batch` に入り、全条件を満たすと WMMA kernel を launch する。非対応条件では `false` を返し、prefill の呼び出し側が `qsa_decode_attn_batch` を batch 単位で実行する。WMMA launch error の場合は stderr に `qsa_prompt_attn_batch (wmma): <HIP error>; the FP32 prompt attention runs from here on` を出し、後続呼び出しを FP32 prompt attention に戻す（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2513-2517,2366-2371`; `engine/src/prefill/prefill.cpp:5556-5569`）。

SYCL のソースにも同名を読むコードがあるが、WMMA 実装ブロックは `#if defined(__HIPCC__)` で囲まれている。通常 attention fallback は prompt prefill 側で行われる。また `engine/sycl/src/prefill/prefill.cpp` の `STRATA_USE_HIP` 条件下には上記の別の ring 判定がある（`engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1646-1649,1920-1927,2018-2026`; `engine/sycl/src/prefill/prefill.cpp:291-300,3873-3885`）。

## ログと測定値

HIP 実装は最初に arch を調べた際、条件に応じて stderr に `strata: STRATA_HIP_WMMA: the prompt attention on matrix cores on (<arch>)`、`... unavailable (<arch>)`、または Windows の既定 OFF 案内を出す。gfx12 Linux の既定 ON の案内では `STRATA_HIP_WMMA=0 turns it off` が付く。unset で OFF かつ arch が gfx11 の場合は、この関数からの案内は出ない（`engine/src/kernels/cuda/qsa_prompt_attn.cu:2262-2274`）。

既定値の適用で変数が設定された場合、gfx11 離散 GPU は `strata: gfx11 (RDNA3): ... matrix-core prompt & MoE switches on by default ...` の一覧に、iGPU は `strata: integrated GPU (<arch>): the matrix-core prompt set is on ...` の一覧に名前が出る。既に設定済みならその switch は一覧に含まれない（`engine/src/core/arch_defaults.cpp:334-345,406-420`）。性能値は記載しない。ここでは資料の値を再計測しておらず、今回の文書ではソース上の制御経路に限定した。

## 根拠

- `engine/src/kernels/cuda/qsa_prompt_attn.cu:2242-2295` — mode 判定、arch 判定、auto 閾値と実際の可用性。
- `engine/src/kernels/cuda/qsa_prompt_attn.cu:2366-2371,2513-2517` — launch 失敗時の状態変更と呼び出し条件。
- `engine/src/core/arch_defaults.cpp:218-224,302-345,406-420` — 起動時既定値設定、ユーザー値優先、診断ログ。
- `engine/include/strata/core/gfx11_extra.hpp:27-37,90-110` — gfx11 default の gate。
- `engine/src/program/generate.cpp:4287-4320` — HIP engine 初期化で GPU 条件を評価し既定値を適用する箇所。
- `engine/src/prefill/prefill.cpp:5556-5569` — prompt 経路と通常 attention fallback。
- `engine/src/prefill/prefill.cpp:843-850` と `engine/sycl/src/prefill/prefill.cpp:291-300` — matrix-core 要求に連動する prompt staging ring の別判定。
- `engine/sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1646-1649,1920-1927,2018-2026` — SYCL ソース内の HIP 条件付きミラー。
