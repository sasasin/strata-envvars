# `STRATA_EXPERT_ROW_E3`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Intel 向け SYCL backend の IQ2_S / IQ3_XXS gate/up row-reuse kernel で、各 expert group の末尾にちょうど 3 entry が残るとき、3 entry をまとめて処理する E3 kernel variant を選びます。未設定時は無効です。IQ3_S も同じ launcher を通りますが、`TG == 21` のため E3 は常時有効で、この環境変数は評価されません（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4428-4457`）。

この設定自体は row-reuse 経路を有効化しません。すでに選ばれた row-reuse kernel 内で、末尾 3 entry の処理方法だけを切り替えます。Strata のコードから確認できる変化は entry のまとめ方であり、性能差や出力の一致に関する測定結果はここでは確認できません（同ファイル `:4405-4424`）。

## 値と判定

`strata::bm_default_on` は `std::getenv` で値を読み、未設定または空文字なら引数 `bm_default` と GPU 世代から既定値を返します。この呼び出しは `bm_default=false` を渡すため、どの GPU でも既定値は OFF です。空でない値は文字列全体や数値として parse せず、先頭文字が `0` なら OFF、それ以外なら ON です（`engine/sycl/include/strata/sycl_queue.hpp:193-200`、`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4437`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| IQ2_S / IQ3_XXS row-reuse launcher | OFF（Battlemage でも OFF） | 空でない文字列で先頭文字が `0` 以外。例: `1`, `true`, `false`, ` 0`, `x` (`0anything` は無効) | 空文字は unset と同じ。先頭が `0` の文字列は OFF（例: `0`, `0anything`, `01`） |
| IQ3_S row-reuse launcher (`TG == 21`) | E3 は常時 ON。環境変数を評価しない | 該当なし | 該当なし |

大文字小文字、空白、後続文字、数値としての妥当性は検査しません。たとえば `false` や先頭に空白がある ` 0` は ON、`0.5` と `01` は OFF です。`STRATA_EXPERT_ROW_E3` の判定と helper の結果は `launch_gu_row_reuse<TG>` の関数内 `static` に保持され、TG ごとに最初に launcher が呼ばれたときの環境値と queue device で決まります。その後の環境変更は反映されません（同ファイル `:4428-4438`）。

## 有効になる条件

- Strata の実験的 Intel SYCL backend を使う必要があります。SYCL は `STRATA_ENABLE_SYCL` による別 build で、CUDA/HIP と同時には選べません（`engine/CMakeLists.txt:23-32`）。
- 対象は IQ2_S (`TG == 22`) または IQ3_XXS (`TG == 18`) の gate/up 経路です。通常の `launch_gu_port` では `LN == 8`、`!g_old_kernels`、`!g_split_multi` が必要で、さらに各形式の row-reuse 制御が ON で、device が Battlemage の場合に launcher が呼ばれます。各 row-reuse 制御は `STRATA_IQ2S_GU_ROW_REUSE` または `STRATA_IQ3XXS_GU_ROW_REUSE` で、未設定時は Battlemage で ON、それ以外では OFF です（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5885-5908`、helper `engine/sycl/include/strata/sycl_queue.hpp:193-200`）。このため `STRATA_EXPERT_ROW_E3=1` だけでは Battlemage 以外でこの経路を強制できません。
- IQ2_S には private hook もあり、`LN == 8`、旧 kernel / split-multi が無効で、`STRATA_PRIVATE_GU_PREPARED` が `1` 始まり、device が Battlemage の場合に同じ launcher を呼びます（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4463-4472, 5863-5876`）。
- `#if !STRATA_GRID_SLM` の条件が偽の build では通常の IQ2_S / IQ3_XXS row-reuse 分岐がコンパイルされません（同ファイル `:5895-5910`）。
- IQ3_S の row-reuse は別の `STRATA_IQ3S_GU_ROW_REUSE` 判定、8 lanes、`n_embd == 2560`、`n_ff == 640`、Battlemage 等の条件で選ばれますが、選ばれた場合も E3 は `TG == 21` により常時有効です。`STRATA_EXPERT_ROW_E3` はこの経路を変更しません（同ファイル `:6020-6038, 4437`）。

## 実行時の詳細

E3 が無効なら launcher は通常の `native_gu_row_reuse_kernel<TG>` を投入し、有効なら `native_gu_row_reuse_kernel<TG, true>` を投入します。kernel は各 group の entry をまず 4 件ずつ処理し、残数がちょうど 3 件なら E3 版で 3 件をまとめます。E3 が無効、または残数が 3 件以外なら 2 件単位と最後の 1 件に分けます。各 pass は IQ2_S / IQ3_XXS の gate/up 2 row を再利用し、対応する出力バッファへ計算結果を書き込みます（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4374-4424, 4428-4457`）。

設定の読み取りはモデル要求ごとではなく、TG ごとの launcher 初回呼び出し時の static 初期化です。CLI 引数による上書きはこのコードにはなく、同じ環境変数への別の Strata 読み取りもありません。標準の IQ2_S / IQ3_XXS row-reuse 経路では Battlemage 判定が別途必要なため、値が ON でも条件を満たさなければ E3 launcher まで到達しません（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5895-5908`）。

## ログと測定値

E3 launcher が有効な場合、TG ごとに初回起動時に stderr へ `strata: IQ2_S exact three-entry row reuse enabled` または `strata: IQ3_XXS exact three-entry row reuse enabled` を出します。IQ3_S は launcher が選ばれれば環境変数の値によらず `strata: IQ3_S exact three-entry row reuse enabled` を出します。E3 無効時はこの exact three-entry ログを出しません（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4437-4443`）。この変数による性能測定値は記載していません。

## 根拠

- 値の読み取り・既定値・Battlemage 判定 helper: `engine/sycl/include/strata/sycl_queue.hpp:193-200`
- E3 variant の選択、entry tail の分割、出力: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4374-4457`
- IQ2_S / IQ3_XXS row-reuse の呼び出し条件: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5885-5908`
- IQ2_S private hook と IQ3_S 経路: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4463-4472, 5863-5876, 6020-6038`
- SYCL backend の分離: `engine/CMakeLists.txt:23-32`
