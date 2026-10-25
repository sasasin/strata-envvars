# `STRATA_PF_I8`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL の prompt 処理で、対象形式の expert を fused int8 DPAS kernel で計算するかを指定します。これは `STRATA_PREFILL_MMQ` の別名です。通常の未設定時は Battlemage でのみ auto 選択され、それ以外の GPU は FP16 expert path です。明示指定すると、対象形式があり、カーネルが利用可能な経路では int8 または FP16 を選びます。

## 値と判定

`i8_env()` はまず `STRATA_PREFILL_MMQ` を読みます。値が未設定または空文字なら `STRATA_PF_I8` を読み、最終的に空文字も未設定相当（null）として扱います。したがって、空の `STRATA_PREFILL_MMQ` は `STRATA_PF_I8` にフォールバックします。非空の `STRATA_PREFILL_MMQ` があれば、`STRATA_PF_I8` より優先されます。(`sycl/src/prefill/prefill.cpp:275-278`)

非空値は文字列全体の比較ではありません。先頭文字が `a` または `A` なら `auto` mode、それ以外は先頭から連続する数字を `long` に蓄積し、結果が 0 かどうかで mode を選びます。数字を一つも読めなければ 0 です。蓄積値が 1,000,000 以上になると追加読み取りを止めますが、結果は非ゼロのままなので mode 1 になります。(`sycl/include/strata/prefill/esimd_moe.hpp:43-50`)

| 有効な環境値 | 判定結果 |
|---|---|
| 未設定、空文字 | Battlemage かつ kernel 利用可能なら auto、それ以外は FP16 |
| `0`、`00`, `0xyz`、`true`、` 1` | mode 0（FP16）。数字が先頭でない場合も 0 |
| `1`、`2`、`1suffix`、`0002` | mode 1（対象 group で int8 を選択） |
| `auto`、`AUTO`、`anything` のうち先頭が `a` / `A` の値 | mode 2（auto） |

`true` は一般的な真偽値として扱われません。たとえば `1suffix` は先頭の数字 `1` を読んで mode 1、`2x` も mode 1 です。`auto` の判定は先頭一文字だけなので `a-no` も mode 2 です。

## 有効になる条件

環境値で mode 1 / 2 を指定しても、それだけでは int8 kernel は実行されません。SYCL の expert layer ごとの処理で、MMQ 経路を使っておらず、native expert layout であり、Hadamard 変換の gate/up と down を使わず、gate/up type が IQ3_XXS (18)、IQ3_S (21)、IQ2_S (22)、down type が IQ4_NL (20) または Q2_0 (42)、形状が `n_ff=640` / `n_embd=2560` で、`i8::available()` が true の場合に対象になります。その他の形式・形状は int8 経路の対象外です。(`sycl/src/prefill/prefill.cpp:4230-4236`)

- 未設定時に auto を既定選択する Battlemage は、GPU の architecture id が `intel_gpu_bmg_g21` または `intel_gpu_bmg_g31` の場合です。製品名では判定しません。カーネル利用可否も確認します。(`sycl/src/prefill/esimd_moe.dp.cpp:811-832`, `sycl/src/prefill/prefill.cpp:282-286`)
- 実行可能性の確認は device ごとに一度行った結果を cache します。`STRATA_I8_FORCE` の先頭文字が `0` なら false、ESIMD aspect がなければ false、sint8 × sint8 の matrix combination に `nsize=16`, `ksize=32` がなければ false です。(`sycl/src/prefill/esimd_moe.dp.cpp:835-853`)
- `STRATA_SYCL_I8_ESIMD=OFF`、または `AUTO` の AOT build が `bmg` / `lnl` 以外を対象とすると stub 実装になり、`available()` は常に false です。JIT と Xe2 AOT（bmg / lnl）では既定 `AUTO` が kernel を含めます。(`sycl/CMakeLists.txt:45-63`, `sycl/src/prefill/esimd_moe.dp.cpp:40-55`)
- int8 kernel が対象でも scratch を確保できない、または kernel が処理できない group は FP16 chain に fallback します。例外で launch が失敗した場合は `g_i8_failed` が立ち、その後の mode 判定はプロセス内で FP16 を返します。(`sycl/src/prefill/prefill.cpp:280-286,4303-4315`)

## 実行時の詳細

設定文字列は `i8_env()` を通して `i8_mode()` から読み直され、関数内に環境値の static cache はありません。値の変更が環境に反映される実行環境なら、後続の `i8_mode()` 呼び出しは再評価します。ただし、`STRATA_I8_FORCE` を含む kernel 利用可否は device ごとに最初の確認結果が cache されます。未設定時の「Battlemage GPU があるか」の探索結果も static cache です。(`sycl/src/prefill/prefill.cpp:275-292`, `sycl/src/prefill/esimd_moe.dp.cpp:824-852`)

明示値 `1` は対象 group ごとに int8 chain を試みます。`auto` は device queue と形式ごとに crossover を測定・再利用し、group の平均 rows/expert がその境界未満の場合に int8 を選びます。選択した group は activation を量子化し、int8 gate/up、SwiGLU 後の量子化、int8 down の順に実行します。int8 の結果が使えない場合は、FP16 dequantize + oneMKL GEMM の chain を実行します。(`sycl/src/prefill/prefill.cpp:4266-4328`)

有効判定時は stderr に `strata: int8 prompt experts are on (...)` が出ます。明示値で対象形式を走査したときは layer ごとの int8 path 選択ログも出ます。kernel を実行できない場合や launch が失敗した場合は、FP16 fallback のログを出します。ログ文面では alias 名ではなく `STRATA_PREFILL_MMQ` が表示されます。(`sycl/src/prefill/prefill.cpp:1205-1209,4237-4243,4303-4313`)

## 根拠

- alias の優先順位と空値処理: `sycl/src/prefill/prefill.cpp:275-278`
- 値の parse と unset 時の default: `sycl/include/strata/prefill/esimd_moe.hpp:39-50`; `sycl/src/prefill/prefill.cpp:282-292`
- 対象 format / shape / 実行条件: `sycl/src/prefill/prefill.cpp:4230-4236`
- device 判定と利用可否の cache: `sycl/src/prefill/esimd_moe.dp.cpp:811-853`
- AOT / stub 条件: `sycl/CMakeLists.txt:45-63`; `sycl/src/prefill/esimd_moe.dp.cpp:40-55`
- 実行、fallback、ログ: `sycl/src/prefill/prefill.cpp:1205-1209,4266-4328`
- 説明資料との照合: `docs/INTEL_INT8_EXPERTS.md:13-27,66-71` は `STRATA_PF_I8` を `STRATA_PREFILL_MMQ` の alias とし、既定条件と形式制限を説明しています。現行ソースでは alias の実際の優先順位・値 parse を上記の実装から確認しました。
