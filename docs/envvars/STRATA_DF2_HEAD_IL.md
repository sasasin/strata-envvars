# `STRATA_DF2_HEAD_IL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DFlash2 drafter が draft head を計算するとき、通常の `native_mmvq` の代わりに interleaved `native_mmvq_il` を使うことを許可します。これは DFlash2 の head 計算だけを制御します。値が有効でも、GPU・重み型・行数などが interleaved kernel の対応条件を満たさなければ通常の `native_mmvq` に進みます。

DFlash2 の実装は CUDA/HIP build に含まれ、Metal/SYCL build には含まれません（`CMakeLists.txt:429-436,703-709`）。HIP では interleaved 対応判定が常に false なので、この変数によって HIP の head kernel は切り替わりません（`src/kernels/cuda/native_mmvq.cu:3987-4000`）。

## 値と判定

Strata は文字列を数値や真偽値として parse せず、環境変数の先頭文字だけを検査します（`src/core/dflash2.cpp:520-527`）。

| 値 | `il_on` | 意味 |
|---|---:|---|
| 未設定 | true | interleaved kernel の利用を許可（既定） |
| 空文字 | true | 設定済みだが先頭文字が `\0` のため許可 |
| 先頭文字が `0` | false | どのような後続文字があっても利用しない |
| その他すべて | true | 例: `1`, `true`, `false`, 空白で始まる値 |

大文字小文字、空白、数値としての妥当性、文字列全体は判定しません。無効文字列をエラーにしたり、警告を出したりする処理もありません。

## 有効になる条件

次の条件がすべて成立したときだけ interleaved path が実行されます。

- DFlash2 が実際に使用され、`record_block()` が `head` 部分を記録すること。`STRATA_DF2_SKIP` に `head` が含まれる場合はその部分を飛ばし、変数もこの時点では読まれません（`src/core/dflash2.cpp:82-85,520-527`）。
- `STRATA_DF2_HEAD_IL` が無効値ではないこと。
- `native_mmvq_il_supported(head_type_, ndraft_, n_dvocab_)` が true を返すこと。CUDA 実装は draft 行数が 1〜8、architecture が対応、対象の ggml weight type（`23/12/13/14/11`）、かつ該当する行数 table が非ゼロであることを要求します（`src/kernels/cuda/native_mmvq.cu:3940-3959`）。表の有効性は `STRATA_MMVQ_IL_*` 系設定や GPU 世代にも左右されます（同 `:3821-3849,3853-3882`）。
- HIP は上記の対応判定が常に false のため不成立です（同 `:3987-4000`）。

通常の DFlash2 起動では `ndraft_` は `--spec` と `--mtp-max-t` から設定され、1〜8 に clamp されます（`src/program/generate.cpp:19710`, `src/core/dflash2.cpp:665-674`）。`STRATA_MMVQ_IL` は DFlash2 のこの分岐では直接参照されません。DFlash2 固有の flag と kernel 対応判定が使われ、通常 verifier の `g_mmvq_il()` にある master switch とは別経路です（`src/core/verify.cpp:183-184`; DFlash2 側 `src/core/dflash2.cpp:522-527`）。

## 実行時の詳細

値は `record_block()` の関数内 `static const bool` に一度だけ保存されます。通常の graph 準備では `prepare()` が各 row 数の graph を capture し、その capture 中に初回評価されます。profile 経路では `prepare()` は graph を作らず、最初の draft の `record_block()` で評価されます（`src/core/dflash2.cpp:545-579,676-686,1017-1049`）。この static は drafter instance 間で共有されるため、初回評価後に環境を変更しても同一プロセス中には反映されません。

有効で kernel が対応する場合は、先に `native_q8_1_interleave()` で入力を変換し、続けて `native_mmvq_il()` で head logits を計算します。どちらかの条件を満たさない場合は直接 `native_mmvq()` を使います（`src/core/dflash2.cpp:522-529`）。kernel 関数自体にも対応判定があり、非対応時は `native_mmvq()` に fallback します（`src/kernels/cuda/native_mmvq.cu:3962-3966`）。

この環境変数専用のログ、警告、終了経路はありません。`native_mmvq_il` の CUDA launch error は kernel 側の `launch_check()` を通り、`record_block()` の例外処理でエラー文字列にされます（`src/kernels/cuda/native_mmvq.cu:3977-3984`, `src/core/dflash2.cpp:538-542`）。DFlash2 の準備全体が失敗した場合は generate が診断を stderr に出して MTP drafter に fallback し、`--draft-fallback none` で MTP がない場合は終了します（`src/program/generate.cpp:19703-19722`）。これらはこの変数の値判定に固有の挙動ではありません。

## 根拠

- 変数の唯一の直接参照、head 分岐、両 kernel 呼び出し: `src/core/dflash2.cpp:520-529`。
- DFlash2 の build 条件: `CMakeLists.txt:429-436,703-709`。
- interleaved kernel の対応条件と HIP fallback: `src/kernels/cuda/native_mmvq.cu:3940-4000`。
- DFlash2 の準備・profile・graph capture と評価時期: `src/core/dflash2.cpp:545-579,676-686,1017-1049`。
- generate 側の DFlash2 bind / prepare の失敗時の fallback: `src/program/generate.cpp:19698-19722`。
- 関連資料 `docs/DETAILS.md` と interleaved kernel 資料を確認しましたが、`STRATA_DF2_HEAD_IL` 固有の測定値や説明は見当たりませんでした。測定値は記載していません。
