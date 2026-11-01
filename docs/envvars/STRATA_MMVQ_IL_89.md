# `STRATA_MMVQ_IL_89`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリや GPU driver が独自に読む環境変数は対象外。

## 役割

CUDA の interleaved MMVQ カーネルで、compute capability 8.9（Ada）用の行数テーブルを選ぶスイッチです。テーブルは各行列 shape に対し warp あたりの処理行数を指定し、該当しないセルは通常の `native_mmvq` カーネル（行数 0）にします。対象は 2〜4 列の Ada 専用テーブルと、1 列の Q3_K 用テーブルです。ソースと設計資料は、この選択で計算出力は bitwise 同一で、変わるのは行数分割と速度だと説明しています。Strata 側で Ada 実機の測定はしていないと記されています。

## 値と判定

resolver は文字列全体を数値変換せず、先頭文字だけを調べます（`include/strata/core/sm120_series.hpp:95-101`）。

| 値 | 判定 |
|---|---|
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | Ada テーブルを有効化。`STRATA_DEFAULTS=026` より優先 |
| 先頭文字が `0`（例: `0`, `0abc`） | Ada テーブルを無効化。共有テーブルに戻る |
| 未設定、空文字、その他の文字列（例: `true`, `2`, ` 1`） | 既定条件に従う。文字列エラーや警告にはならない |

既定では CUDA の cc 89 だけ有効です。`STRATA_DEFAULTS` が厳密に `026`、`0.2.6`、`v0.2.6` のいずれかなら既定は無効になります（`include/strata/core/defaults_026.hpp:21-29`）。従って `STRATA_MMVQ_IL_89=1` はこの既定スイッチを上書きしますが、汎用 `STRATA_MMVQ_IL=0` による MMVQ interleaved 経路の無効化までは上書きしません（`src/core/verify.cpp:175,1508-1517`）。

## 有効になる条件

- CUDA の interleaved 実装が使われる必要があります。HIP 側は interleaved kernel を未サポートとして `native_mmvq_il_supported()` が常に false を返し、通常の MMVQ へ進みます（`src/kernels/cuda/native_mmvq.cu:3930-3941,3960-3975`）。
- 実行デバイスの compute capability が正確に 8.9 である必要があります。デバイス属性は ordinal ごとにキャッシュされ、他の capability ではこの変数によって Ada テーブルは選ばれません（`src/kernels/cuda/native_mmvq.cu:3863-3882,3853-3860`）。
- `native_mmvq_il_supported()` が要求する列数 1〜8、`g_multi_exact`、対応アーキテクチャ、非ゼロ行数、対応量子化型（IQ4_XS、Q4_K、Q5_K、Q6_K、Q3_K）を満たす必要があります（`src/kernels/cuda/native_mmvq.cu:3930-3933`）。Ada 専用の2〜4列表は 2〜4 列でのみ参照されます。1列表は Q3_K のみで、`STRATA_MMVQ_IL_T1=0` なら無効です。5〜8列は別の wide-table 経路を使い、この変数では Ada 用行数表を選びません（同 `:3832-3850`）。
- 実際の verifier 経路では汎用 `STRATA_MMVQ_IL` が先に gate になります。unset は有効、先頭文字が `0` なら無効です（`src/core/verify.cpp:175,1508-1517,2452-2460`）。2〜4列入力で先行して行う interleaved 量子化はさらに `STRATA_QIL` とデバイス条件にも従います（同 `:1495-1506`）。この環境変数単独で interleaved 経路を強制するものではありません。
- `STRATA_MMVQ_IL_ROWS` に該当 type/列数の行指定がある場合、組み込み Ada 表より先にその値が使われます（`src/kernels/cuda/native_mmvq.cu:3795-3824,3842-3859`）。

## 実行時の詳細

通常の Strata verifier は対応する projection や head の処理で `native_mmvq_il_supported()` を呼び、true の場合に interleaved kernel を実行し、それ以外は `native_mmvq()` に fallback します（`src/core/verify.cpp:1508-1517,1551-1560,1791-1798,2452-2460`）。CUDA 側の Ada 表は、4070 と 4080 の測定値が一致するセルだけを採用し、それ以外は 0（plain kernel）にした表です。2〜4列表の他に、1列では Q3_K の行だけを定義しています（`src/kernels/cuda/native_mmvq.cu:3668-3680,3745-3748`）。

環境値は `il_89_opt_in()` 内の `static const bool` に保存され、初回の Ada テーブル判定時に読み取られます。`STRATA_DEFAULTS` の判定も別の static 値として一度だけ評価されます。したがって同じプロセスで初回判定後に環境を書き換えても反映されません（`src/kernels/cuda/native_mmvq.cu:3774-3780`; `include/strata/core/defaults_026.hpp:26-29`）。CLI 引数によるこの環境変数の上書きは確認できません。

この変数自体について、通常実行時の有効・無効ログや無効値警告は実装されていません。要求した行数が0、未対応型、または interleaved 対応条件を満たさない場合は通常 MMVQ へ fallback します。診断ツール `mmvq_il_parity` は、表との不一致があると `FAIL table: ...` を出し、最終行を `mmvq_il_parity: FAIL` として終了コード1にします。一致時は `mmvq_il_parity: OK ...` と終了コード0です（`src/kernels/mmvq_il_parity.cpp:401-423,520-525`）。CMake の `mmvq_il_parity_89table` エントリはこの設定値を `1` にして表チェックを行う定義ですが、調査では build やテストを実行していません（`CMakeLists.txt:1215-1223`）。

## 根拠と資料との照合

- `src/kernels/cuda/native_mmvq.cu:3774-3780,3827-3860` — 値判定結果の cache と Ada 表の選択。
- `include/strata/core/sm120_series.hpp:82-101` — cc 89 の既定、resolver の先頭文字判定。
- `src/kernels/cuda/native_mmvq.cu:3930-3975` — CUDA の適用条件、HIP fallback。
- `src/core/verify.cpp:1495-1517,1551-1560,1791-1798,2452-2460` — verifier からの利用と通常 kernel への fallback。
- `docs/DETAILS.md:1231-1234`、`docs/MMVQ_IL_TABLE.md:18`、`docs/release-notes-0.2.7.md:23` — Ada の表、既定値、測定上の但し書き。資料の記述は現行 resolver と一致します。資料にある 4070/4080 の表由来の情報はコミュニティ測定の記述であり、Strata が Ada 実機で性能を確認したという意味ではありません。
