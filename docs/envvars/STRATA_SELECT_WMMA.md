# `STRATA_SELECT_WMMA`

調査対象: Strata main の HEAD d46f5f268f8ed797e83a5c63a69bffbd7a581cf6（2026-11-25 時点）。

## 役割

HIP 実装の QSA prompt block scorer を、通常の warp scorer から gfx12 (RDNA4) 用 WMMA scorer に切り替える。選択用スコアの合計順序が異なるため、top-k の選択結果も warp 版と異なる場合がある。QSA のスコア計算経路で使われ、生成や attention 全体を直接切り替える設定ではない。CUDA/NVIDIA と Metal ではこの変数を scorer が読まず、SYCL 版も WMMA scorer を実装していない。engine/src/kernels/cuda/qsa_select.cu:2309-2318,2365-2375、engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1705-1727,1729-1757。

AMD では手動指定に加え、Strata が対応アーキテクチャの起動時既定値として "1" を環境へ設定する場合がある。従って未設定なら常に off ではない。既定値の適用と、ユーザーが設定済みの値を保持する規則は engine/src/core/arch_defaults.cpp:302-310,360-390,406-420 にある。

## 値と判定

scorer 内では std::getenv の結果を関数内 static const bool に一度保存し、値が null でなく、空文字でなく、先頭文字が '0' でなければ有効とする。文字列全体の比較・数値変換・空白除去はしない。大文字小文字を問わず、最初の文字が '0' かどうかだけで判定する。engine/src/kernels/cuda/qsa_select.cu:2316-2319（SYCL 生成版にも同じ HIP 条件内の判定: engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1714-1717）。

| 実行条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| HIP scorer が読み取るとき | 明示既定値が注入されなければ off | 1, true, 先頭が空白の ` 1`（先頭が '0' でない） | 空文字、0, 01, 0anything |
| AMD 起動時既定値の対象機 | unset なら起動時に "1" が設定されるため on | ユーザーが設定した値は上書きされず、上記の先頭文字規則で判定 | 0 または空文字は「設定済み」として既定値注入を抑止し、scorer では off |
| CUDA / NVIDIA、Metal、通常の SYCL 経路 | scorer はこの変数を参照しない | 該当なし | 該当なし |

先頭が空白の文字列はこの変数単独の scorer 判定では有効だが、AMD 既定値処理は値を parse せず「環境に存在するか」だけで保持する。STRATA_SELECT_WMMA=false も scorer では有効（先頭が f）になる。engine/src/core/arch_defaults.cpp:307-310,377-379,407-410。

## 有効になる条件

- 実動作の読み取り箇所は __HIPCC__ 分岐にあり、AMD HIP ビルドが必要。CUDA ビルド側は CUDA tensor-core scorer の処理へ進み、この変数による分岐はない。engine/src/kernels/cuda/qsa_select.cu:2313-2320,2376-2380。
- WMMA scorer は GPU が gfx12 (gfx1200 または gfx1201) である場合に限り選択される。値が有効でも他の HIP GPU では関数が false を返し、呼び出し元が warp scorer に fallback する。engine/src/kernels/cuda/qsa_select.cu:2365-2375、アーキテクチャ判定 engine/include/strata/kernels/gfx_arch.hpp:36-42。
- QSA scorer の呼び出し元がこの経路を選ぶ必要がある。通常の prompt selection は qsa_block_scores_tc が false を返すと qsa_block_scores を呼ぶ。STRATA_SELECT_OLD が設定されていれば呼び出し元が直接 warp scorer に回す。engine/src/prefill/prefill.cpp:5377-5392,9445-9456。
- gfx12 の既定値は gfx12_value_changing_env が gfx12 で、STRATA_GFX12_DEFAULTS の先頭文字が 0 でなく、STRATA_DEFAULTS=026 でない場合に候補となる。変数が unset なら "1"、併せて STRATA_SELECT_ALT_MIN_TOKENS=28672 が設定され、短い context では warp scorer のままになる。対象 GPU 等は engine/include/strata/core/gfx12_extra.hpp:54-68、適用箇所は engine/src/core/arch_defaults.cpp:373-390。
- gfx11 discrete RDNA3 (gfx1100/1101/1102) では、既定値セットが有効なときに "1" が設定され得るが、この scorer 自体は gfx12 以外で WMMA を選ばず fallback する。セットは STRATA_GFX11_DEFAULTS=0 または STRATA_GFX11_WMMA_DEFAULTS=0 で無効化される。engine/include/strata/core/gfx11_extra.hpp:87-113、適用と fallback は engine/src/core/arch_defaults.cpp:334-345、engine/src/kernels/cuda/qsa_select.cu:2365-2366。
- integrated GPU の prompt set でもこの変数が既定設定され得る。全可視 GPU が同じ arch の integrated GPU であること、arch が gfx1103/gfx1150/gfx1151 であること、prompt set が有効であることが条件。gfx1103 Linux と gfx1151 Windows では set が既定 on、その他は STRATA_IGPU_PROMPT_SET=1 で有効化できる。STRATA_IGPU_DEFAULTS=0 または STRATA_IGPU_PROMPT_SET=0 は無効化する。ただしこれら gfx11 では WMMA QSA scorer 自体は fallback する。engine/src/program/generate.cpp:4287-4320、engine/src/core/arch_defaults.cpp:119-138,172-215,406-420。
- AMD 既定値処理は環境変数が既に存在すれば値を問わず保持する。従って CLI の設定より環境変数の有無がこの既定値適用に直接関わる。起動処理は engine の switch 読み取り前に apply_arch_defaults を呼ぶ。engine/include/strata/core/arch_defaults.hpp:157-162、engine/src/program/generate.cpp:4287-4320。

## 実行時の詳細

HIP の qsa_block_scores_tc 初回呼び出し時に STRATA_SELECT_WMMA を評価して static const bool に保存する。その後プロセス環境を変更してもこの scorer の値は更新されない。設定が有効で gfx12 なら、active_blocks と max_blocks から処理範囲を決めて WMMA kernel と tail kernel を起動し true を返す。そうでなければ false を返し、通常の呼び出し元では warp scorer が使われる。engine/src/kernels/cuda/qsa_select.cu:2316-2319,2365-2375、engine/src/prefill/prefill.cpp:5387-5392。

gfx12 既定値適用時は setenv(..., 0)（Windows は _putenv_s）でプロセス環境へ値を設定するため、ユーザーが同名変数を設定していれば上書きしない。engine/src/core/arch_defaults.cpp:218-224,373-390。この処理は generate.cpp の HIP 起動初期化から engine の遅延 switch 読み取りより前に呼ばれる。engine/src/program/generate.cpp:4287-4320。

有効な gfx12 経路で kernel 起動エラーが検出されると、stderr に qsa_block_scores_tc: <CUDA error text> を出して exit(1) する。非対応 geometry や WMMA 未選択時はこのエラーではなく false を返し、呼び出し元が warp scorer に fallback する。engine/src/kernels/cuda/qsa_select.cu:2310-2312,2370-2375。

## ログと測定値

gfx12 既定値を Strata が設定したとき、同名変数が 0 で始まらない場合の stderr 文言は "strata: gfx12 (RDNA4): the matrix-core QSA block scorer is on once a prompt is past 28,672 tokens (+5.7% prompt speed at 98K on an R9700, shorter prompts unchanged; the first-token KL against the warp kernel is 0.002 on average above 30K; STRATA_SELECT_WMMA=0 or STRATA_GFX12_DEFAULTS=0 turns it off)"。既定セットの注記では R9700 (p620), IQ3_S, serve の条件で、32K +1.83% (3 pairs)、98K +5.74% (3 pairs)、7 件の 30K–96K prompt に対する first-token KL は平均 0.0018、最大 0.0055、top-1 は 7/7 と記載されている。これらはソースコメントに記載された測定値であり、この調査で再測定していない。engine/src/core/arch_defaults.cpp:387-390、engine/include/strata/core/gfx12_extra.hpp:12-21。

このログは既定値設定ループで STRATA_SELECT_WMMA または同時に STRATA_SELECT_ALT_MIN_TOKENS のいずれかを新たに設定し、変数値が null または先頭文字 '0' でない場合に出る。ユーザーが WMMA を unset のまま alt threshold だけ指定した場合も、any が立ちログ条件を満たす。STRATA_SELECT_WMMA を空文字または 0... にした場合は抑制される。engine/src/core/arch_defaults.cpp:373-390。

docs/AMD_HIP.md:301-307 は gfx12 でこの switch の default を Off と記す一方、現行コードは既定設定が有効な gfx12 で unset の場合に "1" と threshold を注入する。現行コードでは STRATA_GFX12_DEFAULTS=0 または STRATA_DEFAULTS=026 などで既定値処理が無効な場合に unset が off となる。関連文書の表記はこの条件を反映していない。

## 根拠

- engine/src/kernels/cuda/qsa_select.cu:2309-2319,2365-2375 — HIP scorer の判定、gfx12 条件、kernel 起動と fallback 戻り値。
- engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1705-1727,1729-1757 — SYCL 生成コードの HIP 条件と SYCL 側の非対応経路。
- engine/include/strata/core/gfx12_extra.hpp:54-68 — gfx12 での既定値候補と閾値。
- engine/include/strata/core/gfx11_extra.hpp:87-113 — discrete RDNA3 の WMMA switch 既定値候補。
- engine/src/core/arch_defaults.cpp:119-138,172-224,302-345,360-420 — integrated GPU の set 条件、環境設定、優先順位、ログ。
- engine/src/program/generate.cpp:4287-4320 — HIP 起動時の既定値処理呼び出し。
- engine/src/prefill/prefill.cpp:5377-5392,9445-9456 — prompt 経路と warp scorer fallback。
- docs/AMD_HIP.md:301-307 — 現行ソースとの既定値説明の食い違い。
