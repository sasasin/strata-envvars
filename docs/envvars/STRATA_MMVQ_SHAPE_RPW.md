# `STRATA_MMVQ_SHAPE_RPW`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL backend の native MMVQ wide kernel で、Battlemage GPU 上の一部 Q4_K / Q5_K dense projection shape に限り、rows per subgroup（RPW）を 2 にして行方向の row reuse を選びます。対象の計算では列ごとの activation を一度読み、2 行の dot product で共有します。Q4_K / Q5_K の全 shape や他の backend を一律に変更する設定ではありません。

## 値と判定

値は `strata::bm_default_on()` が判定します。設定値は文字列全体や数値として parse せず、先頭文字だけを調べます。

| 値 | 判定 |
|---|---|
| 未設定 | Battlemage なら有効、それ以外は無効 |
| 空文字 | 未設定と同じ。Battlemage なら有効、それ以外は無効 |
| 空でない値の先頭が `0` | 無効（例: `0`, `0abc`） |
| 空でない値の先頭が `0` 以外 | 有効（例: `1`, `true`, `false`, `2`, 空白で始まる値） |

大文字小文字、空白、数値としての妥当性、後続文字は検査されません。明示した空でない値はデバイス世代の既定値に優先します。判定結果は `launch_wide<F, NCOLS>()` の `static const bool` に保存されるため、各テンプレート特殊化では初回評価後に環境値を変えても再評価されません。異なるデバイスを同一プロセスで同じ特殊化から使う場合も、最初に評価したデバイスで得た判定が共有されます。

## 有効になる条件

値判定に加えて、次をすべて満たす場合だけ自動的に `rpw = 2` になります。

- SYCL の native MMVQ wide kernel が呼ばれる。`STRATA_MMVQ_WIDE_K` が未設定または `atoi` の結果が 0 以外であることが必要。`STRATA_MMVQ_WIDE_K=0` なら wide kernel 自体が使われません。
- デバイスが `intel_gpu_gen()` により Battlemage と判定される。ただし明示した空でない対象変数は値判定を上書きし、対象デバイス条件自体は引き続き Battlemage のまま必要。
- `STRATA_MMVQ_WIDE_K_RPW` が未設定である。変数が存在するだけで自動 shape 選択を抑止します。値の妥当性や空文字かどうかは、この抑止判定では見ません。
- Kernel type と寸法がこの表に一致する。

| Weights | `n_in` | `n_out` |
|---|---:|---:|
| Q4_K | 2560 | 6144, 10240, 12288 |
| Q4_K | 6144 | 2560 |
| Q5_K | 2560 | 12288 |
| Q5_K | 6144 | 2560 |

- `NCOLS <= 4`。`try_wide()` が許す列数は 1〜8 で、5〜8 列はこの shape reuse の対象外。

形状が一致しない場合、通常の `STRATA_MMVQ_WIDE_K_RPW` 由来の RPW（既定 1）または後続の通常 wide kernel が選ばれます。`STRATA_MMVQ_WIDE_K_RPW` は `atoi` で整数化され、2 または 4 なら対応する RPW kernel、1 やそれ以外の値なら通常の wide kernel に進みます。環境変数自体の範囲検証・警告はありません。この値が shape reuse より優先されるため、明示設定時は値が `2` でも shape 自動選択のログは出ません。

## 実行時の詳細

Q4_K、Q5_K、IQ4_XS の native MMVQ 関数が `try_wide()` を呼びますが、この環境変数の shape 分岐で対象になる型は Q4_K と Q5_K だけです。条件に合うと `rpw` を 2 にし、2 行を扱う `native_mmvq_wide_rpw_kernel` を launch します。同 kernel は各列の activation を取得して 2 行それぞれの accumulator に適用し、各行の出力を書き込みます。IQ4_XS は同じ wide dispatch を使いますが、shape 判定の型条件に含まれず、この変数では変更されません。

有効な shape reuse が選択されたとき、stderr に `strata: shape-guarded Q4_K/Q5_K dense row reuse enabled` を出します。出力は `launch_wide<F, NCOLS>` のテンプレート特殊化ごとに一度です。変数が無効、shape 不一致、非 Battlemage、列数超過、または `STRATA_MMVQ_WIDE_K_RPW` が設定済みの場合、この変数専用の無効理由ログはありません。カーネル launch 後には既存の `launch_check()` が実行されますが、対象変数に固有の終了・失敗経路は見つかりません。

## 根拠

- `sycl/include/strata/sycl_queue.hpp:123-157` — SYCL device の GPU 世代判定。
- `sycl/include/strata/sycl_queue.hpp:159-166` — `bm_default_on()` の空値・先頭文字・既定世代の判定。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1940-1977` — RPW kernel が列ごとの activation を RPW 行で共有して出力する処理。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1979-1981,2008-2037` — `STRATA_MMVQ_WIDE_K_RPW` の parse、対象環境変数のキャッシュと shape/type/列数 gate、stderr ログ、および RPW kernel launch。
- `sycl/src/kernels/cuda/native_mmvq.dp.cpp:2053-2069,3463-3475,3777-3789` — wide kernel の有効条件と Q5_K / Q4_K の呼び出し経路。
- `docs/INTEL.md:525-532` — SYCL runtime controls の Battlemage 既定設定に関する説明。値の詳細は上記実装を根拠とした。
