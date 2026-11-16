# `STRATA_SYCL_GDN_PREFILL_REG_QK`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の GDN recurrence で、ソフトウェアパイプライン版の列分割カーネルを使うとき、標準の `gdn_rec_cols_pipe_kernel` の代わりに `gdn_rec_cols_pipe_local_kernel` を起動します。後者は Q/K の値をレジスタに読み、サブグループ内の `group_broadcast` で各状態行の計算に使います。どちらも recurrence の出力 `y` と状態 `state` を更新し、その後に共通の出力 norm kernel が起動します。この変数は recurrence kernel の選択を変えますが、出力 norm kernel の選択は変えません。`sycl/src/prefill/kernels.dp.cpp:1001-1032,2762-2805`。

## 値と判定

SYCL の `gdn_recurrence_variant()` が列分割パイプラインへ進んだときに `std::getenv` を呼び、値が存在し、かつ先頭文字が `'1'` なら有効です。文字列全体の比較や数値変換はしません。空文字は無効、`1`・`10`・`1anything` は有効、`0`・`0anything`・`true`・先頭空白付きの ` 1` は無効です。大文字小文字や後続文字は判定されません。`sycl/src/prefill/kernels.dp.cpp:2762-2766`。

| ビルド / 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL の GDN 列分割パイプライン | 標準 `gdn_rec_cols_pipe_kernel` を選択 | 先頭文字が `1` の任意の非空文字列 | 空文字、または先頭文字が `1` 以外の文字列 |

## 有効になる条件

- SYCL の `strata_prefill` に含まれる GDN 実装を実行する必要があります。`sycl/CMakeLists.txt:271-276`。
- `gdn_recurrence_variant()` が Xe variant の直接起動、serial / `T <= 0` / variant 2 の経路を通らず、列分割側に進む必要があります。一般の `gdn_recurrence()` は `STRATA_GDN_HEAD` と `STRATA_GDN_REC_HEADS`、および `gdn_xe_on()` の選択から variant を決めます。`sycl/src/prefill/kernels.dp.cpp:2665-2677,2712-2716,2809-2817`。
- `STRATA_GDN_PIPELINE` が未設定または `atoi` の結果が 0 以外である必要があります。未設定時は pipeline が有効です。設定値が空、`0`、数値変換できない文字列など `atoi` が 0 を返す値では通常の非 pipeline 列カーネルに進み、この変数は評価されません。`sycl/src/prefill/kernels.dp.cpp:2735-2737,2757-2788`。
- Pipeline 経路でも `STRATA_GDN_KEYHEAD` の `atoi` 結果が 1 なら key-head kernel が先に選ばれ、この変数は評価されません。`sycl/src/prefill/kernels.dp.cpp:1270-1275,2740-2766`。
- `STRATA_GDN_REC_HEADS` が設定されていると値にかかわらず serial 経路になり、この変数は評価されません。`STRATA_GDN_XE` で Intel GPU の Xe variant が選ばれる場合も別 kernel 経路です。`sycl/src/prefill/kernels.dp.cpp:2656-2663,2712-2738,2809-2817`。

## 実行時の詳細

通常の prompt GDN 処理は `sycl/src/prefill/prefill.cpp:3314-3317` から `gdn_recurrence()` を呼びます。一般 dispatch は variant を選んで `gdn_recurrence_variant()` に渡します。列分割 pipeline に進んだ場合に限り、環境値をその呼び出しごとに読み、真なら `gdn_rec_cols_pipe_local_kernel`、それ以外なら `gdn_rec_cols_pipe_kernel` を `parallel_for` で起動します。読み取り値を保持する `static` cache はないため、呼び出し時点の環境値を参照します。`sycl/src/prefill/kernels.dp.cpp:2665-2667,2735-2775,2809-2817`。

選択された recurrence kernel の後に、共通の `gdn_out_norm_kernel` が起動します。Strata のコードには、このフラグ専用の CLI 設定、ログ、fallback 警告はありません。`check("gdn_recurrence")` は呼ばれますが、このファイル内の `check()` はエラー取得・出力処理がコメント化された空関数です。`sycl/src/prefill/kernels.dp.cpp:125-137,2791-2807`。

## ログと測定値

この変数が選択した kernel 名を出力するログはありません。Strata の資料ではこの変数固有の測定値を確認できませんでした。`docs/INTEL.md:540-547` にある `STRATA_GDN_QK_REG` は別名であり、この変数の測定根拠にはしていません。

## 根拠

- 候補名の直接参照と値判定・kernel 選択: `sycl/src/prefill/kernels.dp.cpp:2762-2775`。
- 代替 kernel の register / subgroup broadcast 処理と出力・状態更新: `sycl/src/prefill/kernels.dp.cpp:1001-1032`。
- recurrence の上位 dispatch、pipeline と key-head 条件: `sycl/src/prefill/kernels.dp.cpp:2656-2667,2712-2817`。
- prompt 側からの呼び出し: `sycl/src/prefill/prefill.cpp:3314-3317`。
- SYCL build target への収録: `sycl/CMakeLists.txt:271-276`。
