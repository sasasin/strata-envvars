# `STRATA_EXPDEC_R`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA/HIP の IQ expert kernel にある EXPDEC gate/up カーネルで、lane あたりに処理する行数 `R` を選ぶ。`R=1` または `R=2` により `expdec_gu_kernel` のテンプレート実体と、1 block が扱う行数の計算が変わる。down projection 用の `STRATA_EXPDEC_DR` とは別の設定である。EXPDEC が選ばれないとき、この値は通常の gate/up kernel の選択に影響しない（`engine/src/kernels/cuda/iq_kernels.cu:4363-4376, 4400-4419, 4453-4466`）。

## 値と判定

`env_int_or` は `std::getenv` で設定有無を調べ、未設定または空文字なら既定値を返し、それ以外は `std::atoi` の結果を使う。既定値は `1`。その後 `expdec_r()` が変換結果を検査し、厳密に `2` のときだけ `2`、それ以外はすべて `1` に正規化する（`engine/src/kernels/cuda/iq_kernels.cu:4356-4359, 4363, 4375`）。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA または HIP（この `.cu` がビルドされる場合） | `1` | `atoi` の結果が `2` になる値。例: `2`, `02`, `+2`, `2tail`, `2.5` | 結果が `2` 以外なら `1`。例: 空文字は既定値 `1`、`0`, `1`, `3`, `-2`, `true`, `false`, `0anything`, `n/a` |

`atoi` は数値全体の妥当性を検査しないため、先頭の空白・符号と数値の後ろの文字列を許し、数値部分が無い文字列は `0` になる。大文字小文字は値の判定に関係しない。`2tail` のような入力も整数として拒否されず `R=2` になる（同 `iq_kernels.cu:4356-4359, 4375`）。

## 有効になる条件

- この実装ファイルを含む CUDA/HIP GPU engine が必要。CMake は共通 GPU engine を CUDA または HIP が有効な場合に構成し、`iq_kernels.cu` を `strata_kernels` に含める（`engine/cmake/strata_gpu_engine.cmake:6-8, 96-100`）。
- EXPDEC 自体が有効で、旧 IQ kernel が選択されていないこと。`expdec_gu` は `STRATA_EXPDEC` の有効判定が偽、または `g_old_kernels` が真なら既定経路へ戻る。`STRATA_OLD_IQ_MMVQ` は空でなく先頭文字が `'0'` 以外なら `g_old_kernels` を有効にする（`engine/src/kernels/cuda/iq_kernels.cu:3689-3695, 4360-4363, 4453-4458`）。`STRATA_EXPDEC` は値を直接見ると unset/空文字/先頭文字 `'0'` なら無効だが、別の起動時設定が gfx12 または discrete RDNA3（gfx1100/1101/1102）で `1` を既定値として設定する経路がある（`engine/src/core/arch_defaults.cpp:28-55`, `engine/include/strata/core/gfx11_extra.hpp:39-64`）。
- gate/up layout が対応する型（type `16`, `17`, `18`, `21`, `22`）、block/tail 条件を満たし、`n_embd == 32 * ED_XB`（`ED_XB=80`、すなわち 2560）、`n_ff` が 64 の倍数かつ正であること。合わなければ default kernel が使われる（`engine/src/kernels/cuda/iq_kernels.cu:2661, 4378-4380, 4455-4466`）。
- `nib_layout(L)` が真なら EXPDEC を呼ばず nibble gate/up kernel を使う。nibble kernel を含まない build では nibble slot の grouped 呼び出しは `4-bit gate/up slots are not built into this engine` を stderr に出して終了する（`engine/src/kernels/cuda/iq_kernels.cu:7113-7117, 7300-7307`）。
- `STRATA_EXP_LAYOUTS` build で `fused_gu` が選択される場合（たとえば `em0 == 8` と対応形式・形状条件を満たす場合）は、先行 fused kernel が gate/up を処理し、後段の EXPDEC 呼び出しは `!fused_gu` guard により実行されない。`em0` は `STRATA_EXP_MODE` などの状態から決まるため、この経路では `STRATA_EXPDEC_R` は使われない（`engine/src/kernels/cuda/iq_kernels.cu:7196-7204, 7205-7239, 7265-7307`）。
- `STRATA_EXPERT_V2` が空でなく先頭文字 `'1'` で、`gu_type=21`, `d_type=20`, `n_embd=2560`, `n_ff=640` などの条件を満たす場合は、`native_expert_grouped` の先行 S26 分岐が gate/up と down を処理して return するため、この呼び出しでは `STRATA_EXPDEC_R` の EXPDEC 分岐に到達しない（`engine/src/kernels/cuda/iq_kernels.cu:7121-7132`）。
- grouped 呼び出しの `cap_groups` または `cap_entries` が 0 以下なら、kernel dispatch 前に return する（`engine/src/kernels/cuda/iq_kernels.cu:7085-7090`）。
- 内部の `g_exp_phase == 2` の実行では gate/up launch block が飛ばされるため、この呼び出しでも `R` は使われない（`engine/src/kernels/cuda/iq_kernels.cu:7265-7269, 7316-7318`）。
- 通常の engine CLI に `STRATA_EXPDEC_R` を上書きする引数は見つからなかった。C++ API `native_expert_set_expdec_params` に正の `gu_rows_per_lane` が渡された場合は環境変数由来の値を上書きし、`2` 以外の正数は `expdec_r()` で `1` に正規化される。調査対象内の呼び出しは EXPDEC benchmark と parity harness にある（`engine/src/kernels/cuda/iq_kernels.cu:7057-7065`; 呼び出し元: `engine/src/kernels/expdec_bench.cpp:115-117`, `engine/src/kernels/iq_multi_parity.cpp:263-275`）。benchmark の `dec:r` 選択肢自体は `1` または `2` のみを受け付ける（`engine/src/kernels/expdec_bench.cpp:95-101`）。

## 実行時の詳細

`g_expdec_r` は翻訳単位のグローバル初期化時に環境から一度読み込まれる。したがって、プロセス起動後に環境を書き換えても自動では反映されない。読み込んだ値は gate/up の EXPDEC dispatch 時に `expdec_r()` で `1`/`2` に正規化され、テンプレート引数 `R` として `expdec_gu_kernel` に渡る。`R` は `expdec_rows_per_block` の rows-per-pass（`16 * R`）にも使われるため、`STRATA_EXPDEC_RB` が自動値の `0` の場合の block 行数計算にも関係する（`engine/src/kernels/cuda/iq_kernels.cu:4363, 4375, 4388-4406, 4411-4419`）。

`native_expert_set_expdec_params` は `gu_rows_per_lane > 0` のときグローバル値を更新するため、環境読み込み後の API 呼び出しによる上書きは可能。ベンチマークや parity harness は複数設定を切り替えるためこの API を呼ぶ。一方、通常の server/engine 呼び出し箇所からこの setter を呼ぶ経路は確認できなかった。EXPDEC の選択は graph capture 前に行うよう API コメントに記載され、capture 済み graph は capture 時の kernel を保持する（`engine/src/kernels/cuda/iq_kernels.cu:7057-7065`; `engine/include/strata/kernels/iq_kernels.hpp:164-175`）。

## ログと測定値

`STRATA_EXPDEC` が有効で旧 kernel が無効な場合、対応 layout の最初の呼び出しでは stderr に `strata expdec: CUDA%d gate/up type %d: expdec_gu_kernel R %d MINB %d, %d rows per block, grid %d x %lld (cap %lld groups)%s` の形式で出力され、`R` に正規化後の値が表示される。未対応 layout では `strata expdec: CUDA%d gate/up type %d (n_embd %lld, n_ff %lld) not covered: the default kernel runs` と出力する。role/type/taken ごとに一度だけで、モードが無効または旧 kernel が有効ならこの診断箇所には到達しない（`engine/src/kernels/cuda/iq_kernels.cu:4421-4442, 4453-4458`）。

`docs/EXPERTDEC.md:25` は gate/up の `R` を 1 または 2、既定 1 と説明している。同文書のベンチ表は主に既定 `R=1` 構成との比較であり、ここでは `R=2` の一般的な速度差を断定しない。文書に記載された bitwise 一致は資料上の主張であり、本調査では benchmark や GPU 実行を行っていない。

## 根拠

- 読み取りと変換: `engine/src/kernels/cuda/iq_kernels.cu:4356-4359, 4363, 4375`
- gate/up の layout 条件と fallback: `engine/src/kernels/cuda/iq_kernels.cu:4378-4380, 4453-4466`
- `R` による行数・kernel 選択: `engine/src/kernels/cuda/iq_kernels.cu:4388-4419`
- 実行時 setter と値の取得: `engine/src/kernels/cuda/iq_kernels.cu:7055-7077`
- stderr 診断: `engine/src/kernels/cuda/iq_kernels.cu:4421-4449`
- EXPDEC 資料: `docs/EXPERTDEC.md:1-6, 18-46`
