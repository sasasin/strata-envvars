# `STRATA_MMVQ_RPW`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL 版の Q6_K MMVQ で、1 warp がまとめて処理する出力行数を選ぶ実験用設定です。既定の `0` は row-blocked カーネルを選ばず、通常の Q6_K カーネルへ進みます。`1`、`2`、`4` はそれぞれ 1、2、4 行を warp ごとに処理する特殊化カーネルを選びます。読み取りは `rowwarp_rpw()`、分岐と起動は `native_q6_k_mmvq()` にあります（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2187-2199,3958-3968`）。

この環境変数を読む実装は SYCL ポート内だけにあり、通常の CUDA/HIP 実装での効果は確認できません。SYCL は別ビルドの実験的 backend で、トップレベルでは `STRATA_ENABLE_SYCL` を有効にすると別プロジェクトとして構成されます（`engine/CMakeLists.txt:23-32`）。

## 値と判定

関数内 `static const int` の初期化で `std::getenv` が非 null かを見て、設定されていれば `std::atoi` の結果を保存します。`atoi` のため文字列全体の厳密な数値検証はありません。未設定と空文字はともに `0` です。数値変換可能な先頭部分が `1`、`2`、`4` になる値（例: `1tail`、` 2`、`+4`）は対応する特殊化を選びます。`0`、`true`、`false`、`0anything`、変換できない文字列は `0` 相当となり、row-blocked カーネルを選びません。`3`、`5`、負値など、変換結果が `1/2/4` 以外の場合も特殊化に一致せず通常経路に戻ります（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2196-2199,3958-3968`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL の Q6_K MMVQ | `0`（通常カーネル） | `1`、`2`、`4`。`atoi` の変換結果がこのいずれか | 空文字、`0`、`3`、負値、不正文字列など、結果が `1/2/4` 以外 |

## 有効になる条件

- SYCL backend がビルドされ、その実行経路でこの翻訳単位の `native_mmvq()` が呼ばれる必要があります。通常の CUDA/HIP ビルドではこの SYCL ソースが選ばれません（`engine/CMakeLists.txt:23-32`; `engine/sycl/CMakeLists.txt:273-288`）。
- GGML type `14`（Q6_K）の MMVQ である必要があります。型 `14` は `native_mmvq()` から `native_q6_k_mmvq()` にだけ振り分けられます（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4204-4223`）。
- `ncols` が 1〜4 かつ `n_in` が 256 の倍数である必要があります。この条件を満たさなければ row-blocked 分岐を飛ばします（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3958-3968`）。
- packed Q6_K または登録済み planar Q6_K の経路が先に処理を完了した場合、この設定の分岐には到達しません。`STRATA_Q6_PACKED` による packed 経路が先行し、続いて planar registry の一致を調べます（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2876-2899,3007-3035,3935-3939`）。SYCL の native output head は Q6_K packed を優先し、そうでなく `STRATA_Q6_PLANAR` が有効なら planar 化を試みます（`engine/sycl/src/core/native_head.cpp:93-96`）。
- CLI 引数や別の設定ファイルからこの値を上書きする読み取り箇所は見つかりませんでした。対象名のソース参照はこの読み取り 2 箇所（同一の初期化式）以外にはなく、動的 helper への引き渡しもありません。

## 実行時の詳細

`native_mmvq()` が Q6_K を選ぶと `native_q6_k_mmvq()` に入り、まず packed、次に planar の処理を試します。どちらも処理しなかった場合、列数と入力幅の条件を満たし、かつ `rowwarp_rpw()` が `1`、`2`、`4` のいずれかなら該当するテンプレート特殊化を起動して関数から戻ります。値が `0` またはその他の場合は通常の Q6_K MMVQ の検証・起動へ続きます（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3935-3984`）。

値は `rowwarp_rpw()` の初回呼び出しで関数内 `static` に保存され、そのプロセス中は再読込されません。初回呼び出し後の環境変更は反映されません。子プロセスへの設定継承・上書きはこの読み取り実装では扱っていません。

## ログと測定値

この設定の値、選択カーネル、無効値に対する専用ログや警告はありません。`1/2/4` 以外は通常経路へ進みます。通常経路には形状・ポインタ・stream の検証があり、例えば `n_out <= 0` では `native MMVQ requires n_out > 0` の例外になりますが、これはこの環境変数固有の失敗ではありません（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3968-3974`）。

ソースコメントには既定の shared kernel と warm clocks で同等とした記述がありますが、条件や測定データは同じコード範囲に示されていません。この文書では性能値や同等性を実測事実として扱いません（`engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2196-2198`）。

## 根拠

- 値の取得・変換・cache: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2196-2199`
- row-blocked 分岐、条件、値ごとの特殊化: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:3958-3968`
- backend 分離とビルド対象: `engine/CMakeLists.txt:23-32`; `engine/sycl/CMakeLists.txt:273-288`
- Q6_K の型 dispatch: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:4204-4223`
- packed/planar の先行経路と head の条件: `engine/sycl/src/kernels/cuda/native_mmvq.dp.cpp:2876-2899,3007-3035,3935-3939`; `engine/sycl/src/core/native_head.cpp:93-96`
