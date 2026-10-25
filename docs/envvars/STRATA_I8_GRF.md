# `STRATA_I8_GRF`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。Strata 所有の SYCL 実装を対象とし、外部ライブラリ・driver の動作は含めない。

## 役割

SYCL の fused int8 expert prompt カーネルで、非 work-group 版の ESIMD DPAS kernel に指定する GRF サイズを選びます。`128` を選ぶとカーネルのテンプレート引数が 128、それ以外は 256 です。ゲート/up と down の両方に使われます。実際にこのカーネル経路を通る条件は後述のとおりで、変数を設定しただけでは経路は有効になりません。

## 値と判定

値は `std::atoi` で整数に変換し、変換結果がちょうど `128` かどうかだけを調べます。文字列全体の検証、範囲チェック、エラー報告はありません。

| 環境値 | 変換結果の例 | 非 work-group kernel の GRF |
|---|---:|---:|
| 未設定 | 既定値 `256` | 256 |
| 空文字 | 0 | 256 |
| `128` | 128 | 128 |
| `+128`、`128abc`、`128.5` | `atoi` が読む先頭の整数部分は128 | 128 |
| `0128` | 128（8進数としては扱わない） | 128 |
| `0`、`256`、`-128`、数値で始まらない文字列 | 128以外（例では0、256、-128、0） | 256 |

したがって、`128` 以外の整数値を指定してもその値の GRF サイズにはなりません。`atoi` の整数範囲外の入力の結果はこの実装で検査されません。

## 有効になる条件

- `STRATA_I8_GRF` を読むのは SYCL ESIMD int8 expert 実装です。`STRATA_I8_NO_ESIMD` で構築された stub ではこの実装本体が除外されます。
- 呼び出し元が fused int8 expert 経路を選び、対象デバイスで `i8::available()` が真で、native expert の形式・形状が対応している必要があります。呼び出し元は IQ3_S / IQ3_XXS / IQ2_S gate/up、IQ4_NL / Q2_0 down、`n_ff == 640`、`n_embd == 2560` を条件にしています。明示的に int8 経路を選ぶ設定があっても、これらの条件が合わなければ選ばれません。
- `STRATA_I8_FORCE` の先頭文字が `0` なら `available()` は偽になります（`0anything` も該当）。この capability 判定は device ごとにキャッシュされます。環境変数の内容を使った手動選択・既定の Battlemage 選択については `STRATA_PREFILL_MMQ` / `STRATA_PF_I8` が別に制御します。
- work-group 版の条件を満たす場合は、`STRATA_I8_GRF=128` でも work-group kernel が先に選ばれます。この分岐は GRF 256 のテンプレートを使います。gate/up の IQ2_S は work-group 版の対象外です。`STRATA_I8_WG=0` は work-group 版を無効にし、ほかの条件が揃えば非 work-group 版へ進みます。

## 実行時の詳細

値は `grf_for()` の関数内 `static const int` として初回呼び出し時に一度だけ読み取られます。最初に非 work-group 分岐へ到達して値がキャッシュされた後、プロセス内で環境変数を変更しても再評価されません。work-group 分岐では `grf_for()` を呼ばないため、その実行だけでは読み取りも起きません。

非 work-group 版では、gate/up の `launch_gu<..., 128>` または `launch_gu<..., 256>`、down の `launch_dn<..., 128>` または `launch_dn<..., 256>` を選択します。work-group 版の `launch_gu_wg` / `launch_dn_wg` はいずれも `256` をテンプレート引数にしており、この変数の値を反映しません。カーネル起動時にこの変数専用のログは出ません。

## 根拠

- `sycl/src/prefill/esimd_moe.dp.cpp:763-772`: 周辺の `STRATA_I8_WG` helper と、`STRATA_I8_GRF` の `atoi`、既定値、128/256 への正規化。
- `sycl/src/prefill/esimd_moe.dp.cpp:978-1012,1015-1048`: gate/up と down の形状・型検査、work-group 分岐、非 work-group kernel の選択。
- `sycl/src/prefill/esimd_moe.dp.cpp:199-207,341-349`: ESIMD kernel template parameter と GRF kernel property。
- `sycl/src/prefill/prefill.cpp:269-292,4228-4243,4261-4315`: int8 経路のモード判定、デバイス・モデル形式・形状の条件、FP16 経路への fallback と関連ログ。
- `sycl/src/prefill/esimd_moe.dp.cpp:835-854`: `available()` の ESIMD / s8 DPAS capability 検査と `STRATA_I8_FORCE=0` の扱い。
- `docs/INTEL_INT8_EXPERTS.md:25-27`: プロジェクト資料は `STRATA_I8_GRF=128` を128-register mode の切替として記載。GRF の実際の選択条件は上記ソースに従って説明した。
