# `STRATA_SM61_TABLE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Pascal の compute capability 6.1（Tesla P40/P4、GTX 10 系）で、2種類の CUDA カーネル選択に使う opt-out 変数です。既定では sm_61 専用の最適化を使い、`STRATA_SM61_TABLE=0` で従来の CUDA レイアウト／`native_mmvq` カーネルを選びます。

対象の最適化は、(1) native expert の mode 8 レイアウト、(2) dense 行列ベクトル積の interleaved カーネルと sm_61 用行数テーブルです。両方とも CUDA 実装で、値を設定するだけでは他の GPU 世代に作用しません。

## 値と判定

どちらの読み取り箇所も `std::atoi` の結果が 0 かどうかで判定します。文字列全体の妥当性は検証しません。

| 値 | expert mode 8（sm_61） | interleaved matvec（sm_61） |
|---|---|---|
| 未設定 | 有効 | 有効 |
| `0`、空文字、数字に変換できない文字列（例: `false`） | 無効 | 無効 |
| `1`、`-1`、`2`、`1tail` など `atoi` が非0を返す値 | 有効 | 有効 |
| `0tail`、先頭の空白の後に `0` がある値 | 無効 | 無効 |

`atoi` は先頭の空白と符号付き10進数を読み、数値の後ろに続く文字を無視します。数値として変換できない文字列は 0 になります。たとえば `false` は無効、`1tail` は有効です。明示的な空文字も `atoi("") == 0` のため無効です。

## 有効になる条件

- **expert mode 8**: CUDA ビルドで `STRATA_EXP_LAYOUTS` が有効であること（`iq_kernels.cu` では CUDA または `STRATA_HIP_GFX906` 向けに有効化）。GPU の capability が major 6、minor 1 であること。`STRATA_EXP_MODE` が `atoi` で 0 以上になる値を指定すると、sm_61 既定値より明示 mode が優先されます。ベンチ用 `native_expert_set_mode()` が mode を設定した場合も、その値が優先されます。
- **interleaved matvec**: HIP 以外の CUDA 実装であること。対応 GPU 判定に加えて `g_multi_exact` が true、列数が 1〜4、行数テーブルが非0、データ型が IQ4_XS / Q4_K / Q5_K / Q6_K / Q3_K のいずれかである必要があります。Q3_K は別変数 `STRATA_MMVQ_IL_Q3K=0` で除外でき、1列処理は `STRATA_MMVQ_IL_T1=0` で除外できます。Verifier 側ではさらに `STRATA_MMVQ_IL` が先頭文字 `0` でない場合に限り interleaved 関数を呼びます。
- `STRATA_MMVQ_IL_ROWS` の明示行数設定は、対応 GPU 判定を通った後にカード別テーブルに優先します。したがって sm_61 でこの変数を設定しても、`STRATA_SM61_TABLE=0` による GPU 判定を覆しません。
- sm_60 や sm_70、sm_80 以降は別の既定／opt-in 判定を使います。その他の GPU ではこの変数はそれらの経路を切り替えません。

## 実行時の詳細

expert 経路では、最初にデバイスごとの `exp_mode()` が呼ばれたときに compute capability と環境変数を読み、結果をデバイス別の static 配列 `per_dev` に保存します。mode 8 は gate/up と down の native expert カーネル選択に使われます。適用される重み型や shape などが対応しない場合は mode 8 専用 kernel に入らないことがあります。さらに CUDA では `grid_groups` が `0` より大きく `cap_groups` より小さい呼び出しでは、`exp_mode()` の結果を使わず mode 0 にします。

interleaved matvec 経路では、最初の `native_mmvq_il_supported()` 判定時に `il_arch_ok()` が capability と `STRATA_SM61_TABLE` を評価し、結果をデバイス別 static 配列 `ok` にキャッシュします。対応 shape の行数は `kIlRows_61`（1列用には `kIl1Rows_61`）から選ばれます。対応判定を通った場合、Verifier は必要に応じて量子化 activation の interleaved copy を作り、`native_mmvq_il()` を呼びます。非対応なら `native_mmvq()` にフォールバックします。

両経路とも設定変更を各デバイスの初回判定後に反映しません。コード内にこの変数を理由とするログ出力はありません。

## 文書・測定値との照合

`docs/OLDER_GPUS.md` は sm_61 について、expert mode 8 と interleaved matvec のテーブルを既定で有効とし、`STRATA_SM61_TABLE=0` を A/B 比較用スイッチとして記載しています。同文書の測定条件は Tesla P40 24 GB、20-vCPU VM（Xeon E5-2695 v4、RAM 98 GB）、CUDA 12.4、IQ3_S です。例として、18 expert・2 token の native expert 呼び出しで IQ3_S 390→255 µs、interleaved matvec で IQ4_XS 2560×10240・2列が 112→65 µs と記録されています。これは同文書が記載する測定結果であり、他の環境での性能を示すものではありません。

## 根拠

- `src/kernels/cuda/iq_kernels.cu:3001-3016,3591-3621,3702-3713` — expert mode のビルド条件、値の読み取り、sm_61 判定、kernel 選択条件。
- `src/kernels/cuda/native_mmvq.cu:2622-2632,2648-2653,2746-2777,2779-2800` — sm_61 行数テーブル、値判定、device 判定のキャッシュ、対応条件と fallback。
- `src/core/verify.cpp:153-159,1120-1130,1804-1812` — interleaved matvec 全体の追加 opt-out と verifier 経路。
- `docs/OLDER_GPUS.md:103-121` — sm_61 向け説明と測定条件・値。
