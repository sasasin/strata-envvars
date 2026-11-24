# `STRATA_INK_SM120_PFD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA 版 `strata-inkling` の Blackwell SM120/SM121 native SF4（NVFP4）MoE down projection で、重み行から L2 へ先読みする窓の大きさをバイト単位で指定する。値は `moe_sf4_dn_tc` から `k_moe_sf4_tc<false, ...>` に渡され、重みデータの初回および後続 K64 step の `pf_l2` 発行に使われる。0 ならこの down kernel の先読みを行わない。先読みは結果を変えないヒントとソースコメントに記載されている。gate/up 専用の `STRATA_INK_SM120_PF` とは別の値であり、MX8 down kernel はこの値を使わない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:61-65, 971-977, 1000-1006, 1018-1024`）。

## 値と判定

読み取りは `std::getenv` と `std::atoi`。未設定なら 0、設定済みなら `atoi` の変換結果をそのまま使い、値域チェック・32 バイト丸め・clamp は読み取り側にない。空文字、数字で始まらない文字列（`true` など）は `atoi` が 0 を返す。先頭空白と符号の後の数字を変換し、数字の後ろは無視するため、`32tail` は 32 になる。大文字小文字の概念はない。変換結果が 0 なら先読みなし。正の 32 の倍数（例 `32`, `128`）がコメントに沿う値である（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:971-977`）。

| 条件 | unset | 設定時に先読みなし | 設定時に先読みあり・注意点 |
|---|---|---|---|
| `strata-inkling` CUDA の SF4 down kernel が選択される場合 | 0 byte（既定） | `""`, `"0"`, `"false"`, `"abc"`, `"0tail"` は変換結果 0 | `"32"`, `"128"` は指定 byte 数。`pf` は重みデータ行の 576 byte を超える各要求で kernel 内 `min` によりその範囲までに制限される。32 未満の非ゼロ値は `pf / 32 == 0` となり、kernel 内の剰余演算が 0 除算になる。負値も正規化されず、負の `-1`〜`-31` は同じ問題を持つ。より小さくない負値も安全な値ではなく、初回の長さ計算で `size_t` に変換されるため行全体に制限される一方、後続 step の間隔計算は負値のままになる。 |

数値全体の妥当性は検査しないため、`"128tail"` は 128、`"1"` は 1 として扱われる。32 の倍数という制約も実行時には検査されない。`atoi` で `int` の表現範囲を超える文字列を渡したときの値は Strata 側で定義・検証されていない。行ごとのデータ領域は down projection で 576 byte（`ROWS_K = kInter = 1152`、`W_P_ROW = ROWS_K / 2`）であり、指定値がこれより大きくても先読み要求は行の残りを超えない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:211-219, 316-331`）。

## 有効になる条件

- Inkling の CUDA backend を使うこと。対象コードは `engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu` で、HIP・Metal・一般の Strata engine に同名の読み取りはない（`engine/src/inkling2/cuda/CMakeLists.txt:1-3, 40-50`）。
- 対象の translation unit が CUDA 12.8 以上の device code（`__CUDA_ARCH__` が 1200 以上 1300 未満）としてコンパイルされ、実行時にも `CUDART_VERSION >= 12080`、現在の GPU が `ink_cap_sm120` を満たし、kernel binary version が 120 以上であること。どれかを満たさなければ `available()` は false となる（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:25-27, 46-48, 942-956`）。
- MoE dispatch で `force_exact_dec` が false、`M >= 24`、かつ `sm120::available()` が true となること。条件を満たさない経路では FP16/WMMA 等の別 kernel が選ばれ、この変数は使われない（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3676-3687, 3724-3740`）。
- モデルの MoE に SF4 expert があること。`info.has_sf4` が true のときに gate/up と down の SM120 kernel が呼ばれ、down のうち `dn_code == FMT_SF4` の expert がこの先読みを実行する（`engine/src/inkling2/cuda/ink_moe_cuda.cuh:3726-3733`; `engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:251-259`）。
- 別の CLI 引数や環境変数がこの値を上書きする処理は見つからない。`force_exact_dec` はこの dispatch の可否には影響するが、値の parse や cache には影響しない。

## 実行時の詳細

`sf4_pf_env(false)` が初めて呼ばれると関数内 `static` の初期化で `STRATA_INK_SM120_PFD` を読み、その `atoi` 結果をプロセス内に保持する。`sf4_pf_env(true)` 用の `STRATA_INK_SM120_PF` も同じ関数内 static で初期化される。以後は再読み込みしないため、初回初期化後にプロセス環境を変更しても反映されず、複数 GPU で別々の値にはならない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:974-977`）。

選択された down kernel は、行の先頭で `min(pf, W_P_ROW)` byte の prefetch を発行し、K64 step のループ内でも `pf / 32` step ごとに先のデータ窓を発行する。down projection では重みデータ `wrow_p` のみを先読みし、gate/up にある scale 行の prefetch は行わない。`pf == 0` なら両方の prefetch 分岐を通らない。先読みは routed SF4 expert の down projection に限られ、MX8 expert と fallback kernel には適用されない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:316-331, 1000-1006`; `engine/src/inkling2/cuda/ink_moe_cuda.cuh:3724-3738`）。

## ログと測定値

この変数の値や有効化を表示する Strata のログは該当箇所にない。32 未満の非ゼロ値では `pf / 32` が 0 となり、kernel の `(st % (pf / 32))` は 0 除算式になるが、通常の実行結果やエラー文言はソースから確定できないため記載しない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:326-331`）。

同ファイルのコメントには gate/up 用 `STRATA_INK_SM120_PF` を 128 byte にしたときの 5090 / SQ-20 / 64 slots の 20.6 ms から 13.1 ms という値があるが、これはこの down 専用変数の測定値ではないため、本書の効果値として扱わない（`engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:971-973`）。`docs/DETAILS.md` と `docs/SETTINGS.md` に `STRATA_INK_SM120_PFD` の個別説明は見当たらない。

## 根拠

- `engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:61-65, 971-977` — prefetch 命令、コメント上の用途、値の読み取りと既定値。
- `engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:211-219, 251-259, 316-331, 1000-1006` — SF4 down kernel の対象 expert、データ範囲、prefetch の発行。
- `engine/src/inkling2/cuda/ink_moe_fp4_sm120.cu:25-27, 46-48, 942-956` — compile/runtime/compute capability による利用可能性。
- `engine/src/inkling2/cuda/ink_moe_cuda.cuh:3676-3687, 3724-3740` — SM120 dispatch と SF4 kernel の呼び出し条件。
- `engine/src/inkling2/cuda/CMakeLists.txt:1-3, 40-50` — Inkling CUDA backend と SM120 translation unit のビルド構成。
