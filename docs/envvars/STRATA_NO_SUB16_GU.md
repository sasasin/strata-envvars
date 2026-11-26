# `STRATA_NO_SUB16_GU`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

CUDA/HIP の native grouped-expert kernel で、gate/up の 16-lane（sub-16）行カーネルと、一部 down の小行幅カーネルを選ばないための切替です。設定すると、対象形状では全 warp の multi kernel や 8 行単位の grid へ切り替わり、特定の融合・段階化経路も選択されなくなります。環境変数による値の判定自体は CUDA/HIP と SYCL の実装にあります。CPU・Metal の読み取り箇所は見つかりませんでした。`engine/src/kernels/cuda/iq_kernels.cu:3689-3695,4541-4571,4622-4636,7192-7195,7340-7343`; SYCL は `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3938,7948-7950`。

## 値と判定

両実装とも `env_on` が `getenv` の結果を調べ、未設定、空文字、または先頭文字が `0` なら false、それ以外なら true とします。文字列全体の比較や数値変換はしません。したがって `0` と `0anything` は無効、`1`・`true`・`false`・`-1`・先頭が空白の値は有効です。大文字小文字や後続文字も判定に影響しません。`engine/src/kernels/cuda/iq_kernels.cu:3689-3695`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3938`。

| ビルド | unset / 空文字 | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA / HIP | false（既定の kernel 選択） | 先頭文字が `0` 以外の非空文字列 | 空文字、先頭文字 `0` |
| SYCL | false（既定の行幅選択） | 先頭文字が `0` 以外の非空文字列 | 空文字、先頭文字 `0` |

## 有効になる条件

- `engine/src/kernels/cuda/iq_kernels.cu` を使う CUDA/HIP build では、native grouped-expert の対象分岐で作用します。同ファイルは CUDA/HIP 共通の GPU engine source list に含まれます（`engine/cmake/strata_gpu_engine.cmake:1-8,95-100`）。
- gate/up の 16-lane 経路が候補になるのは、旧 kernel が選ばれておらず、`n_embd == 2560`、形式が split 対象で、`gu_calls(...) == 80` の場合です。設定時は `gu_sub16_rows` が false となり、`GU_ROWS` 行幅を使います。形状がこの条件を満たさなければ、この gate/up の切替による差はありません（`engine/src/kernels/cuda/iq_kernels.cu:7184-7195`）。
- CUDA/HIP の `launch_gu` では、環境変数が有効でも `!kSplit<TG>`、`g_old_kernels`、`split_off<TG>()` などの別条件が先に経路を決める場合があります。適用対象の multi kernel では `SUB16=false` のテンプレート実体を選びます。設定は `tq_sub8_on()` も無効化し、`launch_gu_swiglu` と `down_ws_on` の専用経路を拒否します（`engine/src/kernels/cuda/iq_kernels.cu:3750-3761,4541-4571,4597-4608,4916-4928`）。
- CUDA/HIP の down 側は `L.n_ff == 640` などの形状で小さい行幅を選びます。有効時は通常の down multi kernel の `SUB_DOWN=false` を選ぶ分岐があり、TQ の staged / sub8 経路では条件により別テンプレート経路へ進みます（`engine/src/kernels/cuda/iq_kernels.cu:4622-4636,7340-7343`）。
- SYCL 版では変数の読み取り箇所は同じファイル内の一か所で、`n_ff == 640` の down grid の行幅を 32 / 16 から 8 に戻します。その他の形状ではこの行幅選択に作用しません（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3937-3938,7948-7950`）。
- CUDA/HIP と SYCL 以外の backend、または native grouped-expert 分岐を通らない処理には、確認できた読み取り・適用箇所がありません。CLI 引数や Strata 設定ファイルによる上書き・優先順位も、この名前については見つかりませんでした。

## 実行時の詳細

CUDA/HIP と SYCL の各翻訳単位で、namespace-scope の `g_no_sub16_gu` を初期化するときに一度読みます。関数内 static cache やリクエスト単位の再読込ではありません。従って、プロセス起動後に環境値だけを変更しても、この値は更新されません（`engine/src/kernels/cuda/iq_kernels.cu:3689-3695`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3938`）。

CUDA/HIP では gate/up の 80-dot row shape に使う `row_dot_80_sub16` を避け、通常の multi kernel の full-warp 側へ進みます。down 側も対象分岐で小行幅 template を避けます。別経路である `STRATA_GU_SWIGLU` の融合 gate/up と `STRATA_DOWN_WS` の down kernel は、この変数が有効だと採用されません。SYCL では上記のとおり down grid の行幅を選びます。これらは kernel と grid の選択を変える実装であり、この調査ではモデル出力の同一性や性能差を実行測定していません（`engine/src/kernels/cuda/iq_kernels.cu:1848-1858,2207-2250,4524-4538,4541-4571,4597-4618,4622-4636,4916-4928,7192-7195,7340-7343`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7948-7950`）。

## ログと測定値

通常の kernel 選択コードに、この変数を理由として出すログや警告はありません。benchmark 用 `expdec_bench` は、値が上記 helper の判定で有効な場合に `# warning: STRATA_NO_SUB16_GU is set, the kernel choice is bypassed` を stdout に出します。これは benchmark 内の注意表示で、通常エンジンのログではありません（`engine/src/kernels/expdec_bench.cpp:443-446`）。この変数自体の性能測定値は、参照した `docs/DETAILS.md` および `docs/EXPERTDEC.md` に見つかりませんでした。

## 根拠

- 値判定と初期化: `engine/src/kernels/cuda/iq_kernels.cu:3689-3695`; `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:3927-3938`
- CUDA/HIP の gate/up、down、融合経路: `engine/src/kernels/cuda/iq_kernels.cu:3750-3761,4524-4538,4541-4571,4597-4618,4622-4636,4916-4928,7184-7195,7339-7347`
- SYCL の down grid: `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7948-7950`
- build への登録: `engine/cmake/strata_gpu_engine.cmake:1-8,95-100`; `engine/sycl/CMakeLists.txt:41-46`
- benchmark の注意表示: `engine/src/kernels/expdec_bench.cpp:443-446`
