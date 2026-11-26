# `STRATA_GDN_COMMIT_SPLIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

speculative verifier が採用済み token の GDN state を commit するとき、state-only の `gdn_step_commit_kernel` を使うか、通常の `gdn_step_norm_multi_kernel` を使うかを切り替える診断・実装選択スイッチです。CUDA/HIP の kernel 実装では、値が `0` で始まると state-only kernel を使わず、`gdn_commit_layers()` による全 GDN 層一括 commit も候補から外します。未設定または `0` 以外で始まる値では state-only kernel を許可し、一括 commit の他条件も満たせば層をまとめて処理します（`engine/src/kernels/cuda/verify_kernels.cu:1231-1252, 1353-1365`、呼び出し元 `engine/src/core/verify.cpp:3445-3470, 3498-3521`）。

SYCL にも同名の読み取りがあります。`STRATA_SYCL_GDN_STATE_COMMIT=1` が設定されていない通常経路で、verifier の per-layer commit が `gdn_step_norm_multi()` を通る場合に state-only kernel の選択を制御します（`engine/sycl/src/core/verify.cpp:2224-2243`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2351-2373`）。

## 値と判定

両 backend とも数値変換や文字列全体の比較をせず、`getenv` の結果と先頭 1 文字だけを見ます。

| 読み取り箇所 | unset | state-only commit を許可 | state-only commit を無効化 |
|---|---|---|---|
| CUDA/HIP の `gdn_commit_layers()` 適用判定 | `per_layer=false`（他条件が合えば層一括経路を試す） | 先頭が `0` 以外なら `per_layer=false` | 先頭が `0` なら `per_layer=true`。層一括経路を使わない |
| CUDA/HIP の `gdn_step_norm_multi()` | `commit_split=true` | 先頭が `0` 以外なら `commit_split=true` | 先頭が `0` なら `commit_split=false` |
| SYCL の `gdn_step_norm_multi()` | `commit_split=true` | 先頭が `0` 以外なら `commit_split=true` | 先頭が `0` なら `commit_split=false` |

空文字は設定済みですが、先頭文字が終端 NUL なので `0` ではなく、state-only commit を許可します。`0`、`0anything`、`0.5` は無効化し、`1`、`true`、`false`、先頭が空白の ` 0` はいずれも有効扱いです。大文字小文字、後続文字、数値妥当性、空白の trim は検査しません。無効化条件は文字列が `"0"` と等しいことではなく、最初の文字が `'0'` であることです（`engine/src/kernels/cuda/verify_kernels.cu:1235-1240, 1353-1356`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2351-2354`）。

## 有効になる条件

- verifier の GDN state commit に到達すること。通常の生成・prefill の GDN recurrence 全般を切り替える変数ではありません（`engine/src/core/verify.cpp:3425-3470, 3511-3521`）。
- CUDA/HIP で全層一括 commit を使うには、`STRATA_COMMIT_BATCH` が未設定または先頭が `0` 以外であり、`gdn_commit_layers()` の層数・形状検査も通る必要があります。`STRATA_GDN_COMMIT_SPLIT` が先頭 `0` なら、ほかの条件にかかわらず一括関数は `false` を返し、呼び出し元は GDN 層ごとのループに進みます（`engine/src/core/verify.cpp:3445-3470`、`engine/src/kernels/cuda/verify_kernels.cu:1235-1244`）。
- CUDA/HIP で `STRATA_GDN_SPLIT` の先頭が `1`、または `STRATA_DBG_GDN` の先頭が `1` の場合も `gdn_commit_layers()` は一括処理を断ります。個別処理では `STRATA_GDN_SPLIT` の分岐が `STRATA_GDN_COMMIT_SPLIT` より先に評価され、commit が state-only replay 経路に入ることがあります。この場合、本変数でその分岐を止めません（`engine/src/kernels/cuda/verify_kernels.cu:1235-1244, 1325-1365`）。
- `STRATA_COMMIT_BATCH=0` は CUDA/HIP の層一括 commit 自体を止めますが、個別 `gdn_step_norm_multi()` の state-only kernel 選択は別判定であり、本変数の値に従います（`engine/src/core/verify.cpp:3445-3454, 3511-3521`）。
- SYCL の verifier は `STRATA_SYCL_GDN_STATE_COMMIT` の先頭が `1` のとき `gdn_commit_state_multi()` を直接呼ぶため、その経路では本変数を読む `gdn_step_norm_multi()` に入りません。別の経路で `gdn_step_norm_multi()` が commit を処理するときは、`STRATA_GDN_SPLIT` の先行分岐が該当しない場合に本変数が判定されます（`engine/sycl/src/core/verify.cpp:2224-2243`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2251-2373`）。
- 対象名を読むコードに専用 CLI option はありません。読み取り元は engine プロセスの環境です。`terminal/data/settings-register.json` にも名前はありますが、これは設定登録データであり、実行時の挙動は上記ソースの読み取り・分岐だけを根拠にしています。
- `gdn_commit_layers()` が一括 commit を開始できない場合、呼び出し元は理由ログを出さず per-layer loop に続きます。ただし `MT > kVerifyMaxT` で一括 commit も成立しなければ、capture は `verify commit: windows past <N> tokens (--lookup-max-t) need the batched GDN commit (unset STRATA_COMMIT_BATCH=0, STRATA_GDN_SPLIT, STRATA_GDN_COMMIT_SPLIT=0)` をエラー文字列にして失敗します（`engine/src/core/verify.cpp:3502-3510`）。

## 実行時の詳細

CUDA/HIP の `gdn_commit_layers()` は、初回呼び出し時に `STRATA_GDN_SPLIT`、本変数、`STRATA_DBG_GDN` を `static const bool per_layer` に保存します。本変数が未設定または先頭が `0` 以外なら `per_layer` 判定には影響せず、層数・形状などが適合したとき、各層の convolution history と recurrence state をまとめて kernel に渡します。先頭が `0` なら `gdn_commit_layers()` は何も launch せず `false` を返し、capture 側の層ごとの loop に戻ります（`engine/src/kernels/cuda/verify_kernels.cu:1231-1252`、`engine/src/core/verify.cpp:3453-3470,3498-3521`）。

個別経路の `gdn_step_norm_multi()` も、commit 条件に到達した最初の呼び出し時に本変数を `static const bool commit_split` へ保存します。未設定または先頭が `0` 以外で、`n_keep != nullptr` かつ `t_out_begin >= n_tok` なら、state-only `gdn_step_commit_kernel` を launch して出力計算をせず state を更新します。`STRATA_DBG_GDN` の先頭が `1` なら debug 版 kernel を使い、device 上の keep 数が window 行数を超えたとき `strata DBG: gdn_step_commit: n_keep %d is past the window's %d rows: commit skipped (#937)` を出します。条件に合わない場合は一般の `gdn_step_norm_multi_kernel` に進みます（`engine/src/kernels/cuda/verify_kernels.cu:1353-1380`、kernel 本体 `engine/src/kernels/cuda/verify_kernels.cu:203-225`）。ヘッダーは一括 commit が per-layer call と同じ演算で bitwise に loop と一致すると記述しています（`engine/include/strata/kernels/verify_kernels.hpp:68-76`）。

SYCL の `gdn_step_norm_multi()` にも別の `static const bool commit_split` があり、初回評価後の環境変更はそのプロセス内で反映されません。`STRATA_GDN_SPLIT` の commit replay 分岐が成立すればその先で return し、本変数の判定には到達しません。通常の state-only commit 条件では `gdn_step_commit_kernel` を呼び、そうでなければ一般 kernel に進みます（`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2251-2373`）。

CUDA/HIP の一括判定、CUDA/HIP の個別 kernel 判定、SYCL の個別 kernel 判定はそれぞれ別々の関数 static です。最初の評価以降は、同一プロセス内で環境を変更しても各判定値は更新されません。通常の verifier では capture 時の commit 処理でこの関数群が呼ばれます（`engine/src/core/verify.cpp:3425-3470`、`engine/sycl/src/core/verify.cpp:2204-2243`）。

## ログと測定値

本変数自体の読み取りや値の有効化を知らせるログはありません。CUDA/HIP の一括経路が使えないことだけで通常は警告されず、per-layer loop へ進みます。state-only debug kernel の範囲外 keep 数ログは `STRATA_DBG_GDN` の先頭が `1` の場合に限られます（`engine/src/kernels/cuda/verify_kernels.cu:1237-1252,1358-1364,217-225`）。通常の `gdn_step_norm_multi()` で引数検証に失敗すると stderr に `gdn_step_norm_multi: invalid arguments` を出して `exit(1)` します（CUDA/HIP: `engine/src/kernels/cuda/verify_kernels.cu:1320-1330`、SYCL: `engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2198-2205`）。

`docs/DETAILS.md` にこの変数固有の説明や測定値は見つかりませんでした。性能差や出力差をこの文書では推定しません。

## 根拠

- `engine/src/kernels/cuda/verify_kernels.cu:1231-1252,1320-1380` — CUDA/HIP の全層一括判定、値の読み取り、state-only kernel の選択。
- `engine/src/core/verify.cpp:3425-3470,3498-3521` — verifier commit capture から一括・per-layer 経路への流れ、条件不成立時のエラー。
- `engine/sycl/src/core/verify.cpp:2204-2243` — SYCL verifier の commit 経路と `STRATA_SYCL_GDN_STATE_COMMIT` による迂回。
- `engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2198-2205,2251-2373` — SYCL の値判定と kernel 分岐。
- `engine/include/strata/kernels/verify_kernels.hpp:68-76` — 一括 commit と per-layer commit の関係についての API 契約。
- `engine/src/kernels/cuda/verify_kernels.cu:203-225` — CUDA/HIP state-only kernel と debug ログ。
