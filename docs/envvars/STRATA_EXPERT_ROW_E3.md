# `STRATA_EXPERT_ROW_E3`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL の IQ2_S / IQ3_XXS expert gate/up row-reuse カーネルで、残りの entry がちょうど 3 個のときに、3 entry を一度に処理する経路を選びます。無効時は同じ tail を 2 entry と 1 entry に分けます。4 entry 以上はどちらの場合も 4 entry ずつ処理され、2 entry / 1 entry の残りも従来どおりです。対象は Strata の SYCL 実装で、CUDA/HIP/CPU の実装でこの名前を読む箇所はありません。

## 値と判定

`strata::bm_default_on(name, device, false)` が環境値を判定します。値全体の parse はせず、空でない値の先頭文字だけを確認します。

| 状態 | `e3` の値 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（未設定と同じく `bm_default=false` にフォールバック） |
| 空でない値の先頭が `0` | 無効。例: `0`, `0abc` |
| 空でない値の先頭が `0` 以外 | 有効。例: `1`, `2`, `true`, `false`, 空白で始まる値 |

大文字小文字、空白の除去、数値としての妥当性、文字列全体は検査しません。そのため `false` も有効で、`0anything` は無効です。通常の既定値はオフで、CLI 引数や設定ファイルによる上書きはこの読み取り箇所にはありません。

## 有効になる条件

この値が有効でも、次の条件が満たされなければ三 entry 経路は実行されません。

- Strata の SYCL カーネル経路であること。SYCL ビルドは `sycl/CMakeLists.txt` で `iq_kernels` をカーネル一覧に加えています。
- 量子化形式が IQ2_S (`TG == 22`) または IQ3_XXS (`TG == 18`) で、8 lane の `launch_gu_port` 経路を通ること。
- 対応する row-reuse 制御 `STRATA_IQ2S_GU_ROW_REUSE` または `STRATA_IQ3XXS_GU_ROW_REUSE` が有効で、旧カーネル (`STRATA_OLD_IQ_MMVQ`) と split multi (`STRATA_EXPERT_SPLIT`) が選ばれていないこと。
- GPU 世代が Battlemage であること。row-reuse launcher がこの条件を別途確認するため、`STRATA_EXPERT_ROW_E3` を明示しても他世代ではこの row-reuse 経路を有効にしません。
- row ごとの entry 数の残りがちょうど 3 個であること。

IQ3_S (`TG == 21`) は `launch_gu_row_reuse` を共有しますが、コード上 `TG == 21` なら `e3` は常に true です。この場合、短絡評価により `STRATA_EXPERT_ROW_E3` の helper 呼び出し自体が行われず、当環境変数は IQ3_S の判定には使われません。

## 実行時の詳細

各 `launch_gu_row_reuse<TG>` の `static const bool e3` 初期化時に helper が環境を読み、特殊化ごとに結果を保持します。したがって IQ2_S / IQ3_XXS では、その特殊化の最初の呼び出し後にプロセス環境を変更しても判定は更新されません。値が有効になると stderr に `strata: IQ2_S exact three-entry row reuse enabled` または `strata: IQ3_XXS exact three-entry row reuse enabled` が一度出て、`native_gu_row_reuse_kernel<TG, true>` を launch します。無効なら通常の `native_gu_row_reuse_kernel<TG>` を launch します。

カーネルは各 group の entry 区間を先に 4 個ずつ処理し、`E3` が有効で残りがちょうど 3 個の場合だけ `E=3` の dot 処理を行います。その後の 2 個・1 個の tail は両方の経路にあります。この変数の値が 3-tail の処理方法以外を変えることは、参照した呼び出し経路からは確認できません。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4813-4818` — 4-entry の反復、`E3` による厳密な 3-entry tail、続く 2-entry / 1-entry tail。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4822-4852` — `e3` の判定、診断ログ、true/false で選ばれる kernel specialization。
- `sycl/include/strata/sycl_queue.hpp:159-166` — Battlemage 既定判定 helper の空文字・先頭文字規則とデバイス条件。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4873-4887` — IQ2_S / IQ3_XXS row-reuse 経路の lane、別環境変数、旧カーネル・split 経路の条件、Battlemage 制約。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4986-4998` — IQ3_S も共通 launcher を呼ぶ経路。
- `sycl/CMakeLists.txt:245-254` — SYCL `iq_kernels` ソースの選択。
- `docs/INTEL.md:527-541` — SYCL runtime control の説明と、この変数の対象として記載された IQ2_S / IQ3_XXS row-reuse path。
