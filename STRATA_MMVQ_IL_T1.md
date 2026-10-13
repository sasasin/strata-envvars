# `STRATA_MMVQ_IL_T1`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。対象は Strata 所有ソース。外部ライブラリ・GPU driver の環境変数動作は含めない。

## 役割

CUDA の `native_mmvq_il` における単列（`ncols == 1`）カーネルを使うかどうかを制御する補助スイッチです。現行テーブルで単列カーネルが登録されているのは compute capability 8.6（sm_86）の Q3_K（ggml type 11）だけです。したがって既定で有効でも、通常この変数が選ぶ処理は RTX A4000 など sm_86 の Q3_K 単列経路に限られます。単列経路は通常の q8_1 入力を使い、複数列用の interleave コピーを行いません。

## 値と判定

`il_env_on()` は文字列を数値として parse せず、先頭文字だけを調べます。読み取り結果は `il_t1_on()` 内の `static const bool` に保存されます。

| 値 | 判定 |
|---|---|
| unset | 有効（既定） |
| 空文字 | 有効（設定済みだが先頭文字が `\0`） |
| 先頭文字が `0` | 無効。`0`、`0anything`、`00` など |
| その他すべて | 有効。`1`、`true`、`false`、空白や数字以外で始まる文字列を含む |

大文字小文字、後続文字、数値としての妥当性は検査しません。読み取り後にプロセス環境を書き換えても、最初の評価結果は変わりません。根拠: `src/kernels/cuda/native_mmvq.cu:2596-2601`。

## 有効になる条件

このスイッチが有効でも、次の条件を満たさなければ単列の interleaved カーネルは選ばれません。

- CUDA 実装であること。HIP ビルドでは interleaved 機能の stub が常に非対応を返し、通常の `native_mmvq` を呼びます。
- `STRATA_MMVQ_IL` が有効であること。Verifier 側のこの変数は未設定なら有効、値の先頭文字が `0` なら無効です。無効なら `native_mmvq_il` の選択判定に進みません。
- 呼び出しが 1〜4 列で、`g_multi_exact` が有効で、GPU アーキテクチャが `il_arch_ok()` を通ること。
- 型・形状に対応するテーブル行が 0 でないこと。単列テーブルは sm_86 の Q3_K のみで、出力行数 `n_out < 2048` のクラスは 0、それ以上の全クラスは 1 です。他の compute capability や型ではこの変数を有効にしてもテーブルが 0 のため、通常カーネルに fallback します。
- `STRATA_MMVQ_IL_ROWS` に同じ `type` と `ncols=1` の有効な行がないこと。このカスタム行があればテーブル検索が先に返るため、`STRATA_MMVQ_IL_T1` の判定は使われません。

通常の decode / verify 経路では、Verifier が dense projection や loaded head の処理時に `native_mmvq_il_supported()` を確認し、対応する場合に `native_mmvq_il()` を呼びます。非対応なら呼び出し元が直接 `native_mmvq()` を実行します。また `native_mmvq_il()` 自身も非対応なら `native_mmvq()` に戻ります。根拠: `src/core/verify.cpp:138-139,1085-1095,1769-1777`; `src/kernels/cuda/native_mmvq.cu:2642-2662,2682-2708,2711-2715,2735-2746`。

## 実行時の詳細

単列の行数テーブルは `kIl1Arch` にあり、sm_86 の Q3_K に対して `{0, 1, 1, 1, 1}`（行数クラスは順に `n_out < 2048`, `<4096`, `<8192`, `<12288`, `>=12288`）を返します。`STRATA_MMVQ_IL_T1=0` に相当する先頭文字 `0` で無効化すると、行数 0 が返り、対応していた sm_86 / Q3_K の呼び出しも標準カーネルへ fallback します。有効時は `native_mmvq_il()` が単列カーネルを起動し、`x_il` の代わりに通常の `x_q8_1` ブロックを渡します。

起動可能な GPU は別の `il_arch_ok()` が device ごとに static cache します。機能表上 sm_86 はこの判定を通ります。sm_70 / sm_60 は別変数による opt-in が必要ですが、それらには単列用テーブル行がないため、この変数だけでは単列カーネルは選ばれません。対応する処理はログを出しません。

## 根拠

- 値の判定、既定値、static cache: `src/kernels/cuda/native_mmvq.cu:2587-2601`。
- 単列テーブル（sm_86 / Q3_K）とカスタム行の優先順位: `src/kernels/cuda/native_mmvq.cu:2587-2595,2611-2638,2642-2653`。
- compute capability 判定、対応型と fallback: `src/kernels/cuda/native_mmvq.cu:2682-2708,2711-2733`。
- HIP stub: `src/kernels/cuda/native_mmvq.cu:2735-2746`。
- decode / verify の呼び出し箇所と `STRATA_MMVQ_IL` の判定: `src/core/verify.cpp:138-139,1085-1095,1769-1777`。
- `docs/MMVQ_IL_TABLE.md` は複数列の interleaved 経路と `STRATA_MMVQ_IL_ROWS` を説明していますが、`STRATA_MMVQ_IL_T1` の説明は見つかりませんでした。この文書の挙動説明は実装コードに基づきます。
