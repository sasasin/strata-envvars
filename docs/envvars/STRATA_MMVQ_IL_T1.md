# `STRATA_MMVQ_IL_T1`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の `native_mmvq_il` が単一列（`ncols == 1`）を処理するとき、GPU 世代と重み型に対応する1列用テーブルを使うかを制御します。テーブル値は warp 当たりの行数で、0 なら通常の `native_mmvq` に戻り、非0なら interleaved 系の CUDA kernel を選びます。単一列では通常の `q8_1` 入力ブロックをそのまま使い、複数列向けの interleave コピーは作りません。

この環境変数は複数列向け経路を制御しません。複数列の有効化には別の表や条件が使われます。

## 値と判定

環境変数名を受け取る共通関数は `getenv()` の結果が未設定なら有効、設定されていれば先頭文字が `'0'` 以外の場合に有効とします。文字列全体・数値としての妥当性・大文字小文字は調べません。

| 値 | `STRATA_MMVQ_IL_T1` の判定 |
|---|---|
| 未設定 | 有効 |
| 空文字 | 有効（先頭文字が終端の `\0`） |
| `0`、`0anything` | 無効 |
| `1`、`true`、`false`、空白で始まる値など | 有効（先頭文字が `0` ではない） |

判定結果は `il_t1_on()` の関数内 `static const bool` に初回呼び出し時に保存されます。通常のプロセスでは、その後の環境変更は再評価されません。

## 有効になる条件

`STRATA_MMVQ_IL_T1` が有効でも、次の条件がそろった場合だけこのテーブル経由のカーネルが選ばれます。

- CUDA ビルドである。HIP 側は interleaved 対応を持たず、常に `native_mmvq` へ戻ります。
- 呼び出しが `native_mmvq_il_supported()` を通る。`ncols` は1から8、`g_multi_exact` が有効で、GPU が `il_arch_ok()` の対象である必要があります。
- `ncols == 1` で、対応アーキテクチャ表に重み型の行があること。現在の1列表は sm_61 と sm_86 のみで、sm_61 は `STRATA_SM61_TABLE=0` で対象外にできます。表にない GPU / 型の組み合わせは0を返し、通常 kernel を使います。
- 通常実行では、検証処理側の `STRATA_MMVQ_IL` スイッチも有効であること。こちらは未設定を有効、先頭文字が `0` の値を無効として別途キャッシュします。

`STRATA_MMVQ_IL_ROWS` に `ncols=1` の一致行がある場合、その値は `STRATA_MMVQ_IL_T1` の判定より先に返されます。したがって、明示したテーブル行がある場合には `STRATA_MMVQ_IL_T1=0` だけではその行を無効化しません。これはテーブル上書き用変数との相互作用です。

## 実行時の詳細

検証処理は投影や出力 head の行列ベクトル計算について `native_mmvq_il_supported()` を確認し、真なら `native_mmvq_il()`、偽なら `native_mmvq()` を呼びます。`native_mmvq_il()` 自身も未対応時には通常 kernel に fallback します。単一列では interleave 変換を行わず、入力の `x_q8_1` をそのまま使います。

単一列用テーブルは型別に IQ4_XS（type 23）、Q5_K（13）、Q3_K（11）の行を持ちます。表の各値は出力行数の5クラス（2048未満、4096未満、8192未満、12288未満、それ以上）で選ばれ、型または GPU が表にない場合は0です。Q4_K / Q6_K の1列行は現在ありません。

コードにはこの変数専用のログやエラー出力はありません。無効または該当表なしの場合、呼び出し元が通常 kernel を選ぶため、1列 kernel は静かに fallback します。既存の `docs/MMVQ_IL_TABLE.md` は表のカード別選択や測定方法を説明していますが、`STRATA_MMVQ_IL_T1` の値判定の説明はありません。

## 根拠

- `src/kernels/cuda/native_mmvq.cu:3076-3097` — 1列用テーブル、環境値判定、`STRATA_MMVQ_IL_T1` の関数内キャッシュ。
- `src/kernels/cuda/native_mmvq.cu:3141-3165` — 行数クラス、`STRATA_MMVQ_IL_ROWS` の先行、1列テーブルの選択。
- `src/kernels/cuda/native_mmvq.cu:3205-3233` — GPU 対応条件、`STRATA_SM61_TABLE`、exact mode 条件。
- `src/kernels/cuda/native_mmvq.cu:3235-3274` — 対応判定、通常 kernel への fallback、HIP stub。
- `src/core/verify.cpp:164-165,1320-1342,2233-2241` — 全体スイッチ `STRATA_MMVQ_IL` と検証経路からの選択、単一列時の入力処理。
- `docs/MMVQ_IL_TABLE.md:3-20` — interleaved MMVQ の概要とカード別テーブル説明。
