# `STRATA_MMVQ_IL_Q3K`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の interleaved small-batch matvec（`native_mmvq_il`）で、Q3_K 重み向けのカーネル行数テーブルを既定経路として使うかを制御します。無効なら、該当する Q3_K 計算は `native_mmvq` のカーネルへ戻ります。この変数は interleaved 経路全体のスイッチではなく、Q3_K のテーブル選択だけに関係します。

通常利用時の呼び出し元は verifier の複数 token window です。dense projection とロード済み head の計算で、全体スイッチ `STRATA_MMVQ_IL` が有効かつカーネル側がその形状をサポートすると interleaved 経路を呼びます。参照: `src/core/verify.cpp:137-139,1084-1095,1769-1777`。

## 値と判定

判定は `getenv()` が返した文字列の先頭文字だけを見ます。文字列全体の数値 parse や真偽値 parse はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 有効（設定済みだが先頭文字は `\0`） |
| 先頭が `0` | 無効。`0`, `0anything` など |
| それ以外 | 有効。`1`, `true`, `false`, `2` など |

したがって `false` は無効値ではありません。判定結果は `il_q3k_on()` の関数内 `static const bool` に保存され、同一プロセスで一度判定した後の環境変更は反映されません。根拠: `src/kernels/cuda/native_mmvq.cu:2596-2601`。

## 有効になる条件

値が有効でも、実際に Q3_K の interleaved カーネルが選ばれるには、通常は次の条件が必要です。

- CUDA ビルドであること。HIP 側の実装では `native_mmvq_il_supported()` は常に `false` で、呼び出しも `native_mmvq` に転送されます（`src/kernels/cuda/native_mmvq.cu:2735-2747`）。
- verifier 側の `STRATA_MMVQ_IL` が有効であること。これは別変数で、未設定なら有効、先頭文字が `0` なら無効です（`src/core/verify.cpp:137-139`）。
- `g_multi_exact` が有効であること、列数が1〜4であること、GPU の compute capability が対応すること（`src/kernels/cuda/native_mmvq.cu:2705-2708`）。
- Q3_K の行数テーブルがその GPU・列数・出力行数に対して 0 以外を返すこと。

組み込みの Q3_K テーブルがあるのは compute capability 8.6 のみです。そこでは 2〜4列の行数が出力行数の5クラス（2048未満、2048以上4096未満、4096以上8192未満、8192以上12288未満、12288以上）別に設定されています。1列用テーブルも capability 8.6 にありますが、通常の1列経路は `STRATA_MMVQ_IL_T1` の判定を使い、この変数の判定は通りません。ただし、前述の `STRATA_MMVQ_IL_ROWS` override は1列にも指定でき、その場合は Q3_K 用スイッチ判定を迂回します。Q3_K の標準複数列テーブルを持たない他の対応 GPU では、この変数を有効にしても標準表から Q3_K は選択されません（`src/kernels/cuda/native_mmvq.cu:2577-2595,2642-2662`）。

例外として `STRATA_MMVQ_IL_ROWS` に対象 type / 列数の行が指定されると、その行数が Q3_K 用スイッチの判定より先に返ります。そのため当該 override が適用された形状では、`STRATA_MMVQ_IL_Q3K=0` でもこの変数単独では override 経路を無効化しません。override は type・列数・出力行数クラスに対応する行数を設定し、CUDA のアーキテクチャ条件は引き続き適用されます（`src/kernels/cuda/native_mmvq.cu:2611-2638,2642-2656,2705-2708`）。

## 実行時の詳細

verifier の projection 処理は対応条件を満たすと、必要に応じて Q8_1 活性値を interleave 形式に変換してから `native_mmvq_il()` を呼びます。カーネル側では `native_mmvq_il_supported()` が行数0と判定した場合、直ちに `native_mmvq()` を呼んで終了します。Q3_K は内部 type `11` です。組み込み sm_86 表では 2〜4列向けにこの type の行数が登録され、選択時は `IlQ3K` のカーネルを起動します（`src/core/verify.cpp:1084-1095,1769-1777`; `src/kernels/cuda/native_mmvq.cu:2580-2586,2642-2662,2705-2732`）。

ソースコメントは、RTX A4000（sm_86）での測定に基づき Q3_K の複数列テーブルを追加したこと、例として形状 2560×10240・4列で 120→70 µs と記しています。また単列用表の例として A4000 の 2560×10240 で 60→43 µs、6144×2560 で 30→26 µs としています。これらはソースコメント中の測定例で、他 GPU や別形状の性能を示すものではありません（`src/kernels/cuda/native_mmvq.cu:2577-2590`）。

## 根拠

- 候補名の唯一の直接参照と値判定: `src/kernels/cuda/native_mmvq.cu:2601,2655`。
- 既定テーブルと Q3_K の登録範囲: `src/kernels/cuda/native_mmvq.cu:2577-2595`。
- テーブル上書きの優先、単列経路、標準表での Q3_K 無効化: `src/kernels/cuda/native_mmvq.cu:2611-2638,2642-2662`。
- GPU・列数条件、対応時の fallback と Q3_K 起動: `src/kernels/cuda/native_mmvq.cu:2705-2732`。
- verifier の全体スイッチと実行呼び出し箇所: `src/core/verify.cpp:137-139,1084-1095,1769-1777`。
- 関連する説明資料 `docs/MMVQ_IL_TABLE.md` は interleaved 経路、全体スイッチ `STRATA_MMVQ_IL`、行数調整 `STRATA_MMVQ_IL_ROWS` を説明しますが、この Q3_K 専用スイッチは説明していません。対象変数の挙動は上記実装に基づきます。
