# `STRATA_HIP_WMMA`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。対象は Strata 所有ソース。外部 HIP ランタイムや GPU ドライバーの動作は含めない。

## 役割

HIP ビルドで、prompt prefill の QSA attention に行列コア WMMA カーネルを opt-in します。対象は int8 KV の QSA attention で、従来の FP32 系カーネルと浮動小数点の加算順が異なるため、結果は bitwise 一致しません。対象の attention 呼び出しがカーネルの形状・pool 条件を満たさない場合は、この環境変数が有効でも通常の QSA decode attention に戻ります。

## 値と判定

値全体の parse はせず、`getenv()` が返す文字列の先頭 1 文字だけを `'1'` と比較します。設定は attention 判定と prefill ring 判定でそれぞれ関数内 `static` にキャッシュされます。

| 値 | WMMA attention / ring の opt-in 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定済みだが先頭文字は `'1'` ではない） |
| 先頭文字が `1`（`1`, `10`, `1anything` など） | 有効候補 |
| その他（`0`, `true`, ` 1` など） | 無効 |

大文字小文字や後続文字は見ません。各キャッシュが初めて評価された後にプロセス環境を変更しても、その判定は更新されません。なお、起動時のヒント表示は別途 `getenv(...) == nullptr` で設定有無だけを検査するため、空文字や `0` でもヒントを抑止します。

## 有効になる条件

- HIP コンパイラーで WMMA カーネルを含むビルドであること。カーネルは gfx1200/gfx1201 と、gfx1100–gfx1103/gfx1150/gfx1151 のコンパイルターゲット向けに定義されています。それ以外のターゲットでは本変数によるカーネル実行はできません。
- 実行 GPU が認識対象の gfx11 WMMA アーキテクチャ、または `gfx12` で始まるアーキテクチャであること。HIP device/property 取得に失敗した場合や device index が内部配列の範囲外の場合は無効扱いになります。
- `qsa_prompt_attn_batch()` が呼ばれ、int8 K/V とその scale があり、Q4 pool がなく、head dimension と head/head-KV 数がカーネルの固定形状に一致し、capacity・selection IDs・steps・page table が有効であること。
- prompt attention が `STRATA_PROMPT_ATTN_OLD` によって旧経路へ強制されていないこと。旧経路が選ばれると WMMA 判定関数は呼ばれません。

通常の CUDA ビルドでは HIP 専用分岐に入らず、この変数で CUDA tensor-core カーネルを切り替えることはありません。gfx906 HIP 互換ビルドは WMMA 対象 GPU ではないため、実行時のアーキテクチャ判定で fallback します。

## 実行時の詳細

HIP attention 実装（通常の CUDA/HIP ソースと SYCL tree 内の HIP 対応コピー）は `hip_wmma_usable()` で環境値を初回に評価し、対象 GPU かをデバイスごとにキャッシュします。環境値が有効候補で、アーキテクチャ判定も通った場合、`qsa_prompt_attn_batch()` は WMMA kernel を起動します。起動が対象外または形状条件未達なら `false` を返し、prefill caller は `qsa_decode_attn_batch()` の分割呼び出しに進みます。WMMA kernel の launch error は stderr に `qsa_prompt_attn_batch (wmma): ...` を出して `exit(1)` します。

アーキテクチャ判定を最初に行う際、最初の調査対象 GPU について stderr に `strata: STRATA_HIP_WMMA: the prompt attention on matrix cores on (<arch>)` または `... unavailable (<arch>)` を一度出します。`generate` 起動時には gfx12 GPU かつ `--kv int8` で変数が未設定の場合、`STRATA_HIP_WMMA=1` の設定を案内するヒントを stderr に出します。このヒントは機能を有効にせず、値が何であれ設定済みなら出ません。

同じ変数は HIP prefill の expert staging ring にも影響します。`STRATA_PREFILL_RING` が未設定で、CLI 等からの `g_ring_override` が正でない場合、変数の先頭文字が `1` なら、prompt 長 `T` が `stream_all_min()` 以上のとき ring を 96 slots にします。それより短ければ `STAGE` slots です。この特例が適用されない場合は、既定 ring や byte budget 等の通常計算に進みます。従って `STRATA_PREFILL_RING` の明示指定（値が `0` の場合も含む）や正の ring override はこの 96-slot 特例を抑止します。ring 判定にも独立した static cache があります。

## 文書との照合・測定値

`docs/AMD_HIP.md` はこのスイッチを「gfx12 only」と説明していますが、現行 HEAD のカーネル定義と `gfx_arch_is_gfx11_wmma()` は gfx1100–gfx1103 および gfx1150/gfx1151 も対象にしています。したがって docs の gfx12 限定の記述は現行ソース全体を反映していません。同文書が記す R9700/gfx1201 の測定（engine 0.1.40、IQ3_S、`--kv int8`、431072 context 設定、4,210/8,830 token prompt の3 trial等）では prompt throughput の向上と decode throughput の小幅低下が報告されています。これは文書記載の gfx1201 環境に限る報告であり、本調査で再測定した値ではありません。また、同 docs は bitwise でないこと、約50 token 以降で greedy text が異なり得ることを記しています。

## 根拠

- `src/kernels/cuda/qsa_prompt_attn.cu:1130-1150,1402-1425,1485-1493`: HIP WMMA のコンパイル対象、環境値判定、GPU arch 判定、int8 pool 等の起動条件とログ。
- `include/strata/kernels/gfx_arch.hpp:15-30`: gfx11 の対応名は完全な arch 名（suffix `:` は許容）で照合し、gfx12 は gfx1200/gfx1201 を表す helper。
- `src/prefill/prefill.cpp:2917-2929`: prompt attention が失敗または旧経路指定の際に decode attention へ fallback。
- `src/program/generate.cpp:4750-4758`: gfx12 / `--kv int8` 時の未設定判定とヒント文。
- `src/prefill/prefill.cpp:292-314` および `sycl/src/prefill/prefill.cpp:197-226`: HIP prefill ring の 96-slot 特例と `STRATA_PREFILL_RING`、CLI override、prompt 長の関係。
- `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1646-1655,1917-1940,2014-2022`: SYCL tree の HIP 対応 attention 実装にも同等の環境判定と条件がある。
- `docs/AMD_HIP.md:337-351`: gfx12 の説明、非 bitwise の注意、記載された R9700 測定条件。
