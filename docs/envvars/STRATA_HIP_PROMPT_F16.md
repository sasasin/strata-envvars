# `STRATA_HIP_PROMPT_F16`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP の prompt prefill における 16-bit GEMM の I/O を FP16 に切り替える。対象 stage の活性値画像を BF16 ではなく FP16 で書き、対応する 16-bit GEMM を FP16 入力・FP16 出力で実行する。出力は結果バッファ内で FP32 に widen される。従って prompt 計算の丸め結果は既定経路と bit-identical ではない。設定は `engine/src/prefill/gemm.cu` の `prompt_f16()` が決め、`Prefill::init` が GEMM と活性値カーネルへ反映する（`engine/src/prefill/gemm.cu:681-713`、`engine/src/prefill/prefill.cpp:2724-2731`、`engine/src/prefill/gemm.cu:1169-1180,1318-1320,1460-1474`）。

これは prompt 側の選択で、decode 全般を切り替える設定ではない。GEMM がこの経路を使うのは HIP コンパイル時であり、`beta == 0` の `f16` GEMM、およびこのモード用に FP16 化した BF16 GEMM。FP16 出力は FP32 に widen される。活性値の FP16 化も行うため、単に計算ライブラリを選ぶだけの設定ではない（`engine/src/prefill/gemm.cu:1169-1180,1303-1320,1460-1474`、`engine/src/prefill/kernels.cu:88-95,2901-2911`）。

## 値と判定

HIP 実装は `std::getenv` で文字列を得て、値が設定されていれば全体を parse せず先頭文字だけを `'1'` と比較する。未設定時だけ GPU の既定ルールを使う。空文字は設定済みで先頭文字が `'1'` ではないため off。大文字小文字、空白、数値としての妥当性は検証しない。先頭が `'1'` なら残りの文字にかかわらず on（例: `1`, `10`, `1anything`）、それ以外は off（例: `0`, `0anything`, `true`, `True`, ` 1`, 空文字）。範囲や境界値の数値変換はない（`engine/src/prefill/gemm.cu:691-699`、判定 helper: `engine/include/strata/core/arch_defaults.hpp:85-90`）。

| HIP 実装での条件 | unset | 有効になる値の例 | 無効になる値の例 |
| --- | --- | --- | --- |
| 統合 GPU と判定された gfx1103、Linux | on | `1`, `1x` | 空文字、`0`, `true` |
| discrete gfx1030 / gfx1031 / gfx1032（Linux または Windows） | on | `1`, `1x` | 空文字、`0`, `true` |
| それ以外（gfx11/gfx12、統合 gfx103x を含む） | off | `1`, `1x` | 空文字、`0`, `true` |

明示値はデバイス既定値に優先する。従って `=0` は既定 on のデバイスでも off にし、先頭が `1` の値は既定 off のデバイスでも on にする。統合 GPU の gfx1103 既定 on は Linux のみだが、discrete gfx1030/31/32 の既定 on は両 OS である。機種判定は `hipGetDeviceProperties` の architecture 名と integrated フラグに基づく（`engine/src/prefill/gemm.cu:693-705`、`engine/include/strata/core/arch_defaults.hpp:85-90`）。

SYCL コピー `engine/sycl/src/prefill/gemm.dp.cpp:360-384` にも同名の `getenv` があるが、判定全体が `#if defined(__HIPCC__)` 内にある。SYCL は独立プロジェクトとして `icpx` で構成されるため（`engine/sycl/CMakeLists.txt:1-10,21,303-308`）、通常の SYCL ビルドではこの関数は `false` を返し、変数を読み取らない。HIP の値規則を SYCL の動作として扱わない。

## 有効になる条件

- HIP コンパイルであること。`prompt_f16()` は `__HIPCC__` がないビルドでは `false` を返す。CUDA の活性値画像も常に BF16 で、この変数を読み取らない（`engine/src/prefill/gemm.cu:681-713`、`engine/src/prefill/kernels.cu:88-95,2901-2911`）。
- prefill stage の初期化が対象デバイス上で行われること。stage ごとに `prompt_f16()` の結果を `Gemm::set_f16_io` と `set_act_f16` に設定する（`engine/src/prefill/prefill.cpp:2724-2731`）。
- GEMM ごとに専用の早期 return 経路が成立した場合、その GEMM は `f16_io_` 分岐まで進まない。HIP の `STRATA_PF_GEMM` が有効で閾値以上かつ専用 GEMM が成功した場合、または `STRATA_WMMA_GEMM` が有効で `T >= 16` かつ beta 条件を満たして専用 GEMM が成功した場合は先に return する（`engine/src/prefill/gemm.cu:1307-1320`）。
- `f16` GEMM の FP16 in-place 分岐は `beta == 0` の場合だけ。`beta != 0` では通常分岐へ進む（`engine/src/prefill/gemm.cu:1303-1320`）。FP16 prompt mode の BF16 GEMM は beta が 0 でない場合にエラー終了する（`engine/src/prefill/gemm.cu:1169-1174`）。
- 無効なデバイス番号、または `hipGetDevice` 失敗時は off を返し、HIP の last error を取得して消費する。デバイス属性取得に失敗すると architecture 名を空、integrated を false として既定値判定するが、明示的な環境値はその判定に優先する（`engine/src/prefill/gemm.cu:684-699`）。

## 実行時の詳細

`prompt_f16()` は現在デバイス番号を取得し、64 要素の static cache をデバイス番号単位で確認する。未 cache のデバイスで `getenv` と GPU 属性取得を行い、on/off を保存する。したがって同じプロセス内で環境を後から変更しても、そのデバイスでは判定済みの値が使われ続ける。複数 GPU の layer split では各 stage が動作するデバイスごとに判定・cache する（`engine/src/prefill/gemm.cu:681-709`、`engine/src/prefill/prefill.cpp:2724-2729`）。

有効時は prefill の活性値カーネルが FP16 画像を書き、GEMM の BF16 重みを FP16 に変換してから FP16 in/out の GEMM を実行する。出力先の FP32 行へ FP16 結果を widen する。`STRATA_DBG_NAN` が設定されていると widen 後の非有限出力を数え、各 GEMM で stream を同期し、件数が非ゼロならログを出してカウンタをリセットする（`engine/src/prefill/kernels.cu:88-95`、`engine/src/prefill/gemm.cu:1169-1180,1460-1482`）。

無効値を受けた場合の警告や CLI による上書きはない。環境値は GPU 既定値より優先する。FP16 activation symbol の設定に失敗すると `prefill: setting the FP16 activation image failed: %s` を stderr に出して `exit(1)`。FP16 prompt 経路で累積 BF16 GEMM が呼ばれた場合や scratch が不足する場合も、それぞれエラーを stderr に出して `exit(1)` する（`engine/src/prefill/kernels.cu:2901-2910`、`engine/src/prefill/gemm.cu:1169-1175`）。

## ログと測定値

HIP で明示値により on になった場合は、デバイスごとの初回判定時に次を stderr に出す（`engine/src/prefill/gemm.cu:700-702`）。

```text
strata prefill: HIP device <番号> <arch> - STRATA_HIP_PROMPT_F16=1: the prompt's 16-bit GEMMs run FP16 in and out (rocBLAS is tuned only for that on gfx103x; not bit-identical to the default)
```

未設定で gfx103x の既定 on になった場合は、別の既定値ログを出す。明示値により on でない場合、または他の既定 on デバイスではこの2種類のログは出ない（同 `engine/src/prefill/gemm.cu:700-705`）。SYCL コピーには異なる案内ログがあるが、通常の `icpx` SYCL ビルドは前述の HIP 条件に入らない（`engine/sycl/src/prefill/gemm.dp.cpp:360-384`）。

Strata の `docs/AMD_HIP.md:516` は、RX 6700 XT（gfx1031）、ROCm 10.1、IQ2_XS、2K prompt 16 件・64 forced tokens の測定として、FP32 積を真値にした KL 0.00549（旧経路 0.00621）および prompt 11–14% 高速と記載する。同資料は Radeon 780M の Q2_0 における複数 prompt 長の結果や gfx1201 で遅くなる例も記載する。これらは資料記載の測定であり、今回実行して再測定した値ではない。

## 根拠

- `engine/src/prefill/gemm.cu:681-713` — HIP 側の読み取り、デバイス既定解決、ログ、cache、非 HIP の戻り値。
- `engine/include/strata/core/arch_defaults.hpp:79-90` — 未設定時の機種ルールと明示値の判定。
- `engine/src/prefill/prefill.cpp:2724-2735` — prefill stage での適用。
- `engine/src/prefill/gemm.cu:1169-1180,1303-1320,1460-1482` — GEMM の経路、出力、失敗と診断ログ。
- `engine/src/prefill/kernels.cu:88-95,2901-2911` — 活性値形式と symbol 設定時の失敗。
- `engine/sycl/src/prefill/gemm.dp.cpp:360-384`、`engine/sycl/CMakeLists.txt:1-10,21,303-308` — SYCL 側の条件付きコピーとビルド構成。
- `docs/AMD_HIP.md:516` — 資料に記載された測定値。
