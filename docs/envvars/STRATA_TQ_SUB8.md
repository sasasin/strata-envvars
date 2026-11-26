# `STRATA_TQ_SUB8`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-26 時点）。

## 役割

CUDA の native grouped expert 計算で、trellis 量子化型の gate/up 行（TQ2_T=144、TQK6=145）と down 行（TQ2_T=144、TQK7=146）に使う 8-lane サブワープ経路を選びます。値は `tq_sub8_on()` が読むだけで、CLI 引数や設定ファイルから渡す処理はありません。標準経路と切り替わっても計算結果の和は同じとソースコメントにあります。`engine/src/kernels/cuda/iq_kernels.cu:692, 3746-3761, 4551-4567, 4622-4636`。

この設定は CUDA 専用です。同じ `.cu` は HIP ビルドにも含まれますが、HIP コンパイル時は `tq_sub8_on()` が環境変数を読まず `false` を返します。SYCL と Metal の別実装にはこの名前の読取箇所がありません。`engine/src/kernels/cuda/iq_kernels.cu:3750-3762`, `engine/cmake/strata_gpu_engine.cmake:98-111`。

## 値と判定

CUDA の `tq_sub8_on()` は初回呼出時に `STRATA_TQ_STAGE` と本変数を読み、判定結果を関数内 `static const bool` に保存します。本変数は文字列を数値や真偽値として parse せず、先頭文字が `'0'` かだけを見ます。空文字を含め、未設定または先頭文字が `'0'` でない値はこの判定上 ON です。`true` / `false`、大文字小文字、空白、数値としての妥当性は検証されず、例えば `0anything` と `00` は OFF、`false`、` 0`、`1tail` は ON です。`engine/src/kernels/cuda/iq_kernels.cu:3750-3760`。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA | `STRATA_TQ_SUB8` 自体は ON 判定。ただし他の条件も必要 | 空文字、`1`、`true`、` 0` | `0`、`0anything` |
| HIP (`__HIPCC__`) | 常に OFF | なし（本変数は読まれない） | すべて |

## 有効になる条件

- 実行経路が CUDA の `native_expert_grouped()` から trellis 向け `launch_gu()` / `launch_down()` に入ること。上位の grouped-expert 別経路が選ばれた場合には本分岐を通りません。`engine/src/kernels/cuda/iq_kernels.cu:7085-7103, 7215-7238, 7300-7312, 7402-7409`。
- `STRATA_OLD_IQ_MMVQ` と `STRATA_NO_SUB16_GU` が `env_on()` 判定で OFF であること。`env_on()` は未設定、空文字、先頭が `0` の文字列を OFF、それ以外を ON とします。`STRATA_NO_SUB16_GU` が ON なら 8-lane 条件から外れます。`engine/src/kernels/cuda/iq_kernels.cu:3689-3695, 4551-4557, 7340-7343`。
- `STRATA_IQ_STAGE_GRID` が未設定、空文字、または先頭が `0` 以外であること。先頭が `0` なら staged-grid 全体が無効になり、本変数による分岐も無効です。`engine/src/kernels/cuda/iq_kernels.cu:3696-3700, 3760`。
- `STRATA_TQ_STAGE` の有効な明示値（空でない値の先頭文字が `0` 以外）で trellis staging を強制していないこと。`STRATA_TQ_STAGE=0` は本経路を無効にします。未設定または空文字の場合、CUDA は実行 GPU の compute capability を確認し、6.1 未満なら staging を選ぶため、本変数のサブ8経路は選ばれません。`engine/src/kernels/cuda/iq_kernels.cu:3726-3744, 3754-3760`。
- Gate/up では型 144 または 145 かつ `(n_embd / qk) * ipb == 160` が必要です。down では型 144 または 146、`n_ff == 640`、旧 kernel と `STRATA_NO_SUB16_GU` が無効で、さらに `tq_stage_on()` または本関数が真である必要があります。down のチャンク数には `STRATA_TQ_ROWCH`（既定 4、整数変換後 1..32 に clamp）が使われます。`engine/src/kernels/cuda/iq_kernels.cu:993-995, 4551-4557, 4622-4636, 7340-7343`。
- したがって `STRATA_TQ_SUB8=0` はサブ8経路を止めますが、`STRATA_TQ_STAGE` が GPU 条件で既定 ON となる経路や、明示的に staging を有効にした経路までは止めません。`STRATA_TQ_STAGE=0` は staging とサブ8の双方を止めます。`STRATA_IQ_STAGE_GRID=0` も両方の staging 条件を外します。`engine/src/kernels/cuda/iq_kernels.cu:3726-3744, 3750-3760, 4559-4567, 4628-4634`。

## 実行時の詳細

グローバル設定 `g_old_kernels`、`g_no_sub16_gu`、`g_stage_grid` は翻訳単位の初期化時に読み取られます。`tq_sub8_on()` の2変数の判定は同関数の初回呼出時に static 保存されます。`tq_stage_on()` も `STRATA_TQ_STAGE` 判定を static 保存し、未設定時の GPU 判定は device ごとに cache します。そのためプロセス実行中に環境を変更しても、これらの判定には反映されません。`engine/src/kernels/cuda/iq_kernels.cu:3693-3700, 3726-3744, 3750-3760`。

Gate/up の条件が揃うと `native_gu_multi_kernel<TG, true, true>` の 8-lane 行分岐を起動します。1 block が 32 行を担当し、行幅が 160 dots の場合に各行 8 lane で計算します。down は TQ の staged multi-kernel を選び、`n_ff == 640` の場合に 32-row grid と `STRATA_TQ_ROWCH` の row chunk 数を使います。サブ8を使わない場合も別 kernel 分岐で計算が続きます。`engine/src/kernels/cuda/iq_kernels.cu:2165-2185, 4551-4567, 4622-4636, 7340-7343`。

## ログと測定値

本変数の ON/OFF を示す専用ログや警告はありません。通常の grouped expert launch の CUDA エラーがあれば `native_expert_grouped/gu`、`native_expert_grouped/down` などのラベルと CUDA エラー文字列を stderr に出し、終了コード 1 で終了します。`engine/src/kernels/cuda/iq_kernels.cu:47-50, 7316, 7409`。

リリースノートは CUDA の NVIDIA カードでの測定として、RTX 3060 12 GB 上の Gyro-S が 53.6→62.8 tok/s（5 組中 4 組）、Gyro-M が 50.6→56.1 tok/s（5 組中 5 組）、各 5 組の interleaved pair と記載しています。また同カード・Gyro-M の 24 groups / 1 token では gate/up 221→140 µs、down 182→86 µs とソースコメントにあります。結果は測定条件の記載された範囲に限られ、他 GPU やモデルに一般化できません。ノートは `STRATA_TQ_SUB8=0` で旧 rows に戻るとしています。`docs/release-notes-0.2.2.md:34-37`, `engine/src/kernels/cuda/iq_kernels.cu:3746-3749`。

## 根拠

- 読取・値判定・cache・CUDA/HIP 分岐: `engine/src/kernels/cuda/iq_kernels.cu:3693-3700, 3726-3744, 3750-3762`
- gate/up と down の条件・kernel dispatch: `engine/src/kernels/cuda/iq_kernels.cu:993-995, 2165-2185, 4551-4567, 4622-4636, 7340-7343`
- grouped expert の呼出経路とエラー報告: `engine/src/kernels/cuda/iq_kernels.cu:47-50, 7085-7103, 7215-7238, 7300-7316, 7402-7409`
- CUDA/HIP 共用ソースの build 登録: `engine/cmake/strata_gpu_engine.cmake:98-111`
- 性能測定の条件: `docs/release-notes-0.2.2.md:34-37`
