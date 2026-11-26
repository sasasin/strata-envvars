# `STRATA_TSUM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

GPU の一部の複数値 reduction で、warp ごとに別々に行っていた和を transposed butterfly（`s26_tsum.cuh` の `tsum`）でまとめる実験的なカーネル分岐を選ぶ。Strata の実装コメントは従来経路と「bitwise the same」としているが、この調査では実行比較をしていない。単一の共通設定ではなく、CUDA/HIP/SYCL の複数カーネルがそれぞれ読み取る。主な実装は CUDA/HIP の `native_mmvq.cu`、`native_bf16.cu`、`fused_gr.cu`、`iq_kernels.cu` と、その一部の SYCL 移植である（`engine/src/kernels/cuda/native_mmvq.cu:1252-1256`, `engine/src/kernels/cuda/native_bf16.cu:313-333`, `engine/src/kernels/cuda/fused_gr.cu:3991-4054`, `engine/src/kernels/cuda/iq_kernels.cu:7121-7132`, `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1353-1357`, `engine/sycl/src/kernels/cuda/native_bf16.dp.cpp:317-333`）。

この変数自体は生成設定やモデル選択を変えない。該当する GPU 計算経路が選ばれた場合に reduction の実装を切り替える。GPU 世代別の起動時既定値テーブルが適用される場合は、未設定値を Strata が環境へ追加する（後述）。

## 値と判定

読み取りは箇所により異なる。

| 読み取り経路 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| MMVQ、BF16 rows、grouped expert、SYCL の MMVQ/BF16 | 各関数内の `static const bool` を初期化するときに `getenv`。値の先頭 1 文字が `'1'` なら on | `1`, `10`, `1anything` | 空文字、`0`, `true`, ` 1`, `01`, unset |
| CUDA/HIP fused GR の Q8 経路 | `static const int` 初期化で `atoi`; unset は `-1`、設定値は変換結果 | 数値変換結果が 1 以上（例 `1`, `2`, `1tail`） | `0`, `true`, ` 0`, `0tail`。`atoi` の結果が負なら明示値として使わず未設定時の既定へ戻る |

先頭文字判定の経路は文字列全体を parse せず、大文字小文字・後続文字・数値としての妥当性も検査しない。したがって `1anything` は on、`01` や先頭空白付きの ` 1` は off である。fused GR は `atoi` のため先頭空白と数値後の文字を許容し、数値に変換できない値や空文字は 0 になる。`atoi` の返す整数に範囲制限はない（`engine/src/kernels/cuda/native_mmvq.cu:1253-1255`, `engine/src/kernels/cuda/native_bf16.cu:317`, `engine/src/kernels/cuda/iq_kernels.cu:7123-7124`, `engine/src/kernels/cuda/fused_gr.cu:3993-4009`）。

fused GR の未設定時だけは単純な off ではない。CUDA では、優先経路を通過したあと、現在デバイスの compute capability major が 8 以上なら既定 on、そうでなければ off。HIP ではこの既定判定は常に off。明示された空文字は `atoi("") == 0` となり off を選ぶ（`engine/src/kernels/cuda/fused_gr.cu:3928-3943`, `3993-4010`）。

別途、起動時の AMD architecture defaults が `STRATA_TSUM=1` を環境へ設定することがある。gfx1151 では `STRATA_GFX1151_DEFAULTS` が先頭 `0` でない場合、gfx12 では `STRATA_GFX12_DEFAULTS` が先頭 `0` でなく、かつ `STRATA_DEFAULTS=026` の旧設定表でない場合に既定値候補へ含める。Volta sm_70 の CUDA table では `STRATA_SM70_PERF=0` と `STRATA_DEFAULTS=026` のどちらでもなければ候補となる。これらは `getenv(name) != nullptr` のとき値を問わず保持するため、空文字や `0` も明示設定として優先し、自動値を阻止する（`engine/src/core/arch_defaults.cpp:41-55,64-85`, `engine/src/core/nv_defaults.cpp:136-146`, `engine/src/core/arch_defaults.cpp:302-310`）。

`STRATA_TSUM` 専用の CLI 引数は見つからず、CLI による直接上書き経路もない。`--gpu` は選択デバイスを変えるため、間接的に適用されるアーキテクチャ既定値には影響し得る（`engine/src/program/generate.cpp:3781-3802,4320`）。

## 有効になる条件

- **CUDA/HIP native MMVQ**: 複数列 MMVQ が native multi kernel に到達すること。`STRATA_B6_MMVQ_ROWS` による B6 専用 kernel が成立するとそちらが先に return し、TSUM reduction は使わない。`g_multi_exact` が false の分岐も TSUM=false を template に渡す。Volta の `STRATA_Q8_V70` kernel は TSUM が on だと候補から外れる。通常経路では Q8_0/Q4_K/Q5_K/Q6_K/IQ4_XS 等の multi kernel、native packed Q8_0/Q6_K、Q8_0 pair kernel が対象（`engine/src/kernels/cuda/native_mmvq.cu:1554-1570,1653-1674,1677-1710,2750-2760,2933-2941,3662-3671`）。
- **CUDA/HIP BF16 rows**: `STRATA_MMVF_ROWS` が先頭 `1` で、呼び出し側の BF16 multi-row kernel 条件を満たす場合に限る。通常経路では `n_out >= 64` かつ `n_tok <= 8`、aux 経路ではさらに `2 <= n_tok <= 8` やポインタ等の検査を通る必要がある。`n_tok <= 4` とそれより大きい場合で別の template kernel を起動する。`STRATA_MMVF_ROWS` が無効、単一 token、幅や入力条件の不一致なら TSUM 読み取り箇所へ来ない（`engine/src/kernels/cuda/native_bf16.cu:313-333,387-435`）。
- **fused GR の Q8**: `launch_q8_t` に到達し、CUDA の `STRATA_HC_Q8_TC` 経路または `STRATA_HC_Q8_BF16TC` 経路がグリッド条件を満たして先に return しないこと。これらは条件成立時 TSUM 値を読む前に別の down/up kernel を起動する。両経路が選ばれない場合に TSUM が down/up Q8 kernel の選択へ使われる。`STRATA_GR_Q8_PFS` は別に parse され、TSUM と併用時に prefetched kernel を選べる。`STRATA_GR_Q8_DOWN_MODE`, `STRATA_GR_Q8_UP_COLS`, `STRATA_GR_Q8_UP_MODE` は該当する down/up 実装をさらに選ぶ（`engine/src/kernels/cuda/fused_gr.cu:3904-3958,3960-4054`）。
- **CUDA grouped expert**: `STRATA_EXPERT_V2=1` の場合でも、`had_block==0`, `tail_off==0`, `gu_type==21`, `d_type==20`, `n_embd==2560`, `n_ff==640` の専用 grouped path に一致したときだけ最初の TSUM 読み取りへ進む（`engine/src/kernels/cuda/iq_kernels.cu:7121-7132`）。
- **grouped expert v2k**: v2k 自体が有効で、`had_block==0`, `tail_off==0`、指定の Q4_K/Q5_K gate/up と down type、モデル寸法条件に合う場合だけ TSUM を読む。`STRATA_EXPERT_V2K` の非空値は先頭文字が `1` かで v2k を明示指定できる。未設定時の自動 v2k は HIP の gfx12 と Windows gfx1151 に限られる（`engine/src/kernels/cuda/iq_kernels.cu:7134-7164`）。
- **SYCL**: SYCL 移植側の MMVQ multi、packed Q8_0/Q6_K、Q8_0 pair および BF16 rows にも独立した同じ先頭文字読み取りがある。MMVQ は multi kernel が実際に選ばれたとき、BF16 は `STRATA_MMVF_ROWS` 等の条件を通ったときだけ効果がある（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1353-1357,2225-2267,2625-2640,2830-2842,4059-4076`, `engine/sycl/src/kernels/cuda/native_bf16.dp.cpp:317-348,582-600`）。
- AMD の gfx1151/gfx12 defaults と CUDA sm_70 defaults はアーキテクチャ固有の自動値であり、全 GPU や全モデルに一律で有効になるものではない。`apply_arch_defaults` は `generate.cpp` から GPU 情報取得後に呼ばれ、ユーザーが設定した値があれば上書きしない（`engine/src/program/generate.cpp:4320`, `engine/src/core/arch_defaults.cpp:302-310`）。

## 実行時の詳細

MMVQ、BF16 rows、grouped expert と SYCL 側は、環境変数を各カーネル経路の初回到達時に関数内 `static` へ保存する。そのため同じプロセス内で後から環境を書き換えても、その読み取り箇所の結果は変わらない。fused GR の TSUM 値も `launch_q8_t<T>` specialization ごとに初回の該当経路で cache される。より前段の TC/BF16 TC 経路が毎回成立して return する状況では、その時点で TSUM はまだ評価されない（`engine/src/kernels/cuda/fused_gr.cu:3991-4010`）。

Strata の AMD architecture defaults と Volta defaults は GPU 情報に基づいて起動時に候補を選び、候補名が既に環境に存在すれば何もしない。未設定なら値 `1` を設定してから後続の遅延読み取りが行われる。従ってこれらの既定値が適用されたプロセスでは、カーネル側から見れば `STRATA_TSUM=1` が明示されている状態と同じになる（`engine/src/program/generate.cpp:4320`, `engine/src/core/arch_defaults.cpp:302-310`, `engine/src/core/nv_defaults.cpp:136-146`）。

TSUM が選ばれた kernel は複数列または複数 row/token の partial sum を butterfly でまとめて出力先へ書く。コード上、この変数を理由にした追加の待ち、timeout、ファイル I/O、通信、子プロセスへの転送はない。対象外の kernel や前段条件で return する経路では設定値があってもその計算には使われない。

## ログと測定値

TSUM の各読み取り箇所に、値が on/off になったことを示す専用ログはない。AMD architecture defaults で値を新規設定した場合、`apply_arch_defaults` はまとめて `strata: gfx12 (RDNA4): ... exact speed switches on by default ...` または `strata: gfx1151 (Strix Halo): ... exact speed switches on by default ...` の行に `TSUM` を含めて stderr 出力する。ユーザー設定が保持された場合やテーブルが空の場合、この一覧には出ない（`engine/src/core/arch_defaults.cpp:302-310,397-404`）。Volta テーブルのソースは設定値を列挙するが、TSUM 専用のメッセージ出力はない（`engine/src/core/nv_defaults.cpp:136-146`）。

kernel 起動失敗時には各呼び出し元の通常の launch check / backend error 経路が適用されるが、TSUM 専用の警告・終了文言は確認できない。ソースコメントには一部経路の bitwise 同一性や測定記録への言及があるものの、この文書ではソースコメント以上の性能・正確性を独自確認した事実として扱わない。

## 根拠

- `engine/src/kernels/cuda/native_mmvq.cu:1252-1256,1653-1710,2750-2760,2933-2941,3662-3671`
- `engine/src/kernels/cuda/native_bf16.cu:313-333,387-435`
- `engine/src/kernels/cuda/fused_gr.cu:3904-3958,3960-4054`
- `engine/src/kernels/cuda/iq_kernels.cu:7121-7182`
- `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:1353-1357,2225-2267,2625-2640,2830-2842,4059-4076`
- `engine/sycl/src/kernels/cuda/native_bf16.dp.cpp:317-348,582-600`
- `engine/src/core/arch_defaults.cpp:28-66,302-310,397-404`; `engine/src/core/nv_defaults.cpp:136-146`; `engine/src/program/generate.cpp:4320`
- `docs/DETAILS.md:1487`; `docs/NVIDIA_V100.md:57,80`; `docs/STRIX_HALO.md:116`; `docs/RADEON_780M.md:87`
