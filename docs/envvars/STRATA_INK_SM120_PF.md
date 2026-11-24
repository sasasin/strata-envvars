# `STRATA_INK_SM120_PF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling CUDA の Blackwell SM120 系 SF4（NVFP4）MoE gate/up Tensor Core kernel で、重み行に対して発行する L2 prefetch window の大きさを byte 単位で指定する。未設定時は 128 byte、0 ならこの prefetch を行わない。GPU の prefetch hint として使われ、ソースコメントは結果を変えないと説明している。down projection は `STRATA_INK_SM120_PFD`、MX8 gate/up kernel は `STRATA_INK_SM120_PF_MX8` の担当で、この変数では制御しない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:971-988, 991-1015`）。

## 値と判定

`sf4_pf_env(true)` 内で `std::getenv` の結果を `std::atoi` に渡し、未設定の場合だけ 128 を返す。明示的な空文字は `atoi("") == 0` となる。`atoi` は整数全体の厳密な検証をせず、先頭の空白と符号を許し、数字列の後ろにある非数字を無視する。数字に変換できない文字列は 0 になる。読み取った値を clamp したり、32 の倍数かを検査したりするコードはない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:974-978`）。

| 環境変数の状態・値 | 値として渡るもの | kernel 上の扱い |
| --- | ---: | --- |
| unset | 128 | 128 byte の prefetch window |
| `0`、空文字、`false`、`abc` | 0 | `if (pf)` が偽になり prefetch を行わない |
| `1`〜`31` | その整数 | 初回 prefetch 後の `pf / 32` が 0 となり、kernel のループで `st % 0` を評価し得る。安全な値域として扱えない |
| `32`、`64`、`128` | その整数 | byte window として処理。コードコメントが想定するのは 32 byte 単位 |
| `128junk`、`  +128tail` | 128 | 数字の先頭部分だけが変換される |
| `-31`〜`-1` | 負の整数 | `pf / 32` が 0 となり、kernel のループで `st % 0` を評価し得る |
| `-32` 以下の負値 | 負の整数 | 正規化・拒否されず kernel に渡る。初回 window 長の `size_t` 変換などで意図した正の window とは異なる処理になるため、使用可能値とはみなせない |

数値変換の失敗や範囲外を通知する Strata 側の検査・fallback はない。32 の倍数でない値も拒否されず、32 以上の場合は後続 prefetch 間隔の計算に `pf / 32`（整数除算）が使われる（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:316-331`）。

## 有効になる条件

- Inkling CUDA backend を使い、`ink_moe_fp4_sm120.cu` が CUDA 12.8 以降の実行環境向けに含まれること。`available()` は `CUDART_VERSION >= 12080`、現在の device が `ink_cap_sm120` を満たすこと、および対象 kernel の `binaryVersion >= 120` を確認する（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:942-956`）。
- CUDA backend の build が SM120 系の kernel を含むこと。同 backend の CMake はこの翻訳単位を別 target として組み、CUDA architecture を `sm_120a` / `sm_121a` に設定する（`engine/src/inkling2/cuda/CMakeLists.txt:40-50`; `engine/src/inkling2/cuda/ink_sm120a.cmake:1-19`）。
- MoE dispatch が `!force_exact_dec && M >= 24 && sm120::available()` を満たすこと。`M` が 24 未満、exact decode 強制中、または kernel が利用不可なら、この SM120 kernel 経路には進まず、この変数も参照されない（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3676-3680, 3724-3734`）。
- 対象 layer に SF4 重みがあり、dispatch の `info.has_sf4` 分岐に入ること。MX8 重みだけの layer ではこの読み取りを使わない（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3588-3593, 3724-3738`）。
- `STRATA_INK_SM120_PF` に CLI 引数や他の環境変数から値を上書きする処理は、Strata 所有ソース内で確認できない。0 は kernel 内で prefetch を止めるが、SF4 計算自体を無効にする設定ではない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:974-978, 993-1006`）。

## 実行時の詳細

SF4 dispatch は activation を FP4 に量子化した後、gate/up kernel `moe_sf4_gu_tc` を呼ぶ。この関数は `sf4_pf_env(true)` を通じて値を取得し、選択した tile 行数に応じた `k_moe_sf4_tc<true, ...>` に渡す。kernel は各重み行の先頭で `min(pf, W_P_ROW)` byte を L2 prefetch し、`pf` が非ゼロなら gate/up の scale row も prefetch する。K step のループ中にも、`pf / 32` に基づいて次の window を追加する。結果の gate/up 計算を実行した後、down 側は別経路・別設定で処理する（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3726-3734`; `engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:991-1006, 208-220, 294-331`）。

値は `sf4_pf_env` の関数内 `static const int` に保存される。最初の SF4 gate/up 呼び出しで一度評価され、その後の呼び出しでは同じ値を使うため、プロセス実行中に環境値を変えても再読込されない。未設定時の 128 は kernel に渡される既定値であり、CLI 引数や他変数との優先順位による上書きはない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:974-978, 991-997`）。

## ログと測定値

この環境変数の値や有効化を表示するログ、値の不正を示す明示的な Strata 警告は実装にない。1〜31 など `pf / 32 == 0` となる値では device kernel が剰余 0 を評価し得るが、この調査では GPU 実行を行っていないため、実行時の CUDA エラー文言や終了経路は確認していない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:326-331`）。

ソースコメントには、RTX 5090、64 slots、SQ-20 条件で gate/up phase が 20.6 ms から 13.1 ms になったとある。これはソースコメントに記録された測定であり、本調査で再測定した値ではない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:971-973`）。

## 根拠

- 候補名の実際の読み取りと既定値: `engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:974-978`。
- SF4 gate/up kernel への値の伝播と kernel 内 prefetch: `engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:294-331, 991-997`。
- SM120 device 条件: `engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:942-956`。
- dispatch、batch 条件、SF4 / MX8 分岐: `engine/src/inkling2/cuda/ink_moe_cuda.cuh:3588-3593, 3676-3680, 3724-3738`。
- architecture-specific build: `engine/src/inkling2/cuda/CMakeLists.txt:40-50`; `engine/src/inkling2/cuda/ink_sm120a.cmake:1-19`。
