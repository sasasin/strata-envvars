# `STRATA_SM60_TABLE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Pascal 世代の NVIDIA GPU（compute capability 6.0、GP100 / Tesla P100）で、二つの CUDA 最適化を選びます。

- decode / verify の小バッチ行列ベクトル積 `native_mmvq_il` で、sm_60 専用の行数テーブル `kIlRows_60` を使うか。
- IQ 形式の grouped expert 計算で、CUDA レイアウトに代えて expert mode 8 を既定選択するか。

どちらも unset が有効です。`STRATA_SM60_TABLE=0` は両方を無効にします。これは通常利用者向けの GPU 選択設定ではなく、sm_60 のカーネル経路を切り替える実行時スイッチです。

## 値と判定

両箇所とも `std::atoi()` の結果が 0 かどうかで判定し、文字列全体の厳密な数値検証はしません。

| 値 | sm_60 の `native_mmvq_il` テーブル | IQ grouped expert mode 8 |
|---|---|---|
| 未設定 | 有効 | 有効 |
| `0`、空文字、数字に変換できない文字列（例 `false`） | 無効 | 無効 |
| `1`、その他 0 以外に変換される整数（負数を含む） | 有効 | 有効 |

`atoi` は先頭の空白と符号を許容し、整数として読める部分以降は判定に使いません。したがって `0suffix` は無効、`1suffix` は有効です。数値として読めない先頭なら 0 となり無効です。値の範囲チェックや警告はありません。整数の範囲を超える入力の結果は保証されません。

根拠: `src/kernels/cuda/native_mmvq.cu:2687-2699`、`src/kernels/cuda/iq_kernels.cu:3423-3429`。

## 有効になる条件

**小バッチ matvec:** CUDA ビルドで、現在の GPU が compute capability 6.0 の場合にだけ、この変数が `il_arch_ok()` の判定に使われます。HIP 側は interleaved path が無効の stub なので、この変数は効きません。さらに `native_mmvq_il_supported()` が要求する列数 1〜4、`g_multi_exact`、テーブル行数が 0 でないこと、対応量子化形式（IQ4_XS / Q4_K / Q5_K / Q6_K / Q3_K）の条件を満たす必要があります。上位層では `STRATA_MMVQ_IL` が有効な場合に呼び出し候補になり、条件に合わなければ通常の `native_mmvq` に進みます。`STRATA_MMVQ_IL_ROWS` が該当する形式・列数の値を与えた場合は組み込み表より先に使われます。sm_60 の表にない形式・形状や行数クラスは表の値が 0 となり、この専用カーネルを使いません。

**Grouped expert:** CUDA の IQ grouped expert 経路で参照されます。`STRATA_EXP_MODE` が 0 以上に設定されていると、その値がカード別既定値より優先されるため、この変数による mode 8 選択は上書きされます。内部ベンチ用の `native_expert_set_mode()` も明示した mode で環境由来の値を上書きできます。CUDA では `grid_groups > 0 && grid_groups < cap_groups` の呼び出しは mode 0 に固定されるので、その呼び出しではこの変数は効果を持ちません。

根拠: `src/core/verify.cpp:1085-1095,1769-1777`、`src/kernels/cuda/native_mmvq.cu:31-33,2705-2714,2735-2746`、`src/kernels/cuda/iq_kernels.cu:3406-3430,3492-3503`。

## 実行時の詳細

小バッチ matvec 側では、sm_60 が有効と判定されると `il_arch_ok()` がその結果を GPU ordinal ごとの配列に保存します。以後そのプロセス内の同じ ordinal では環境変数を読み直しません。対応形状なら `native_mmvq_il()` が interleaved kernel を起動し、そうでなければ plain kernel に fallback します。テーブル `kIlRows_60` は量子化形式、列数、行数クラスごとに warp 当たりの行数（0 / 1 / 2 / 4）を選びます。1 列の経路では元の q8_1 ブロックを使い、2 列以上では呼び出し元が interleaved activation copy を作ります。

Grouped expert 側では、CUDA の `exp_mode()` が GPU ordinal ごとに mode を cache します。sm_60 かつ変数が有効なら mode 8 を選びます。mode 8 は対応する gate/up 型（18、21、22、23、および CUDA で対応する 16）で shared-memory の LDS gate/up カーネルを使い、条件が合う型では SwiGLU と q8_1 量子化を gate/up と融合します。down 型 20 または 42 なら LDS down kernel を使います。型や call 条件が対象外の場合は既存 CUDA kernel に進みます。

この変数を起動後に変更しても、既に評価済みの GPU ordinal の選択は変わりません。環境変数そのものによる stdout / stderr のログ、警告、エラー、終了処理はありません。

根拠: `src/kernels/cuda/native_mmvq.cu:2546-2576,2687-2723`、`src/kernels/cuda/iq_kernels.cu:3406-3430,3505-3537,3582-3593`。

## 資料との照合

`docs/MMVQ_IL_TABLE.md:9-16` には「sm_75 and older は path off」とありますが、調査時点の CUDA 実装では sm_60 に `kIlRows_60` があり、この環境変数が unset なら有効です。したがって、その資料の記述は現行実装と一致しません。コード内コメントでは P100 での行列積テーブルが plain kernel と bitwise equal と説明され、grouped expert mode 8 についても P100 の測定値（down projection 116→94 us、IQ3_S gate/up 360→229 us）とモデル層での bitwise equality が記されています。これらはソースコメントの報告値で、ここで再測定した結果ではありません。

根拠: `docs/MMVQ_IL_TABLE.md:9-16`、`src/kernels/cuda/native_mmvq.cu:2568-2576`、`src/kernels/cuda/iq_kernels.cu:3423-3428`。
