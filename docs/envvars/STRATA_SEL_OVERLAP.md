# `STRATA_SEL_OVERLAP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA の prefill 選択結果を変更せず、連続する16 queryごとに選択 cell の重複度を集計して stderr に出す診断用フック。実装コメントが `debug` と明記する診断用フックである。CUDA/HIP 共通の `engine/src/prefill/prefill.cpp` と SYCL 版 `engine/sycl/src/prefill/prefill.cpp` に読み取りがある。共通ソースは Metal のホストソースにも含まれるが、設定レジストリは backend を `cuda-hip` と `sycl` のみとしている（`engine/CMakeLists.txt:20-22`、`engine/metal/CMakeLists.txt:135-144`、`terminal/data/settings-register.json:43586-43603`）。

有効時は選択 ID をホストへコピーして stream/queue を同期し、完全な16 query tileごとに各 query の width の合計 `sum_w` と、tile内 ID の union の要素数 `sum_u` を累積する。ログの百分率は `sum_u / sum_w * 100`。従って「一 queryずつ読む」場合の総 cell 数に対する tile 単位の異なる cell 数の割合であり、選択 ID や生成 token を変更しない。16 query 未満の端数 tile は集計対象外。CUDA/HIP: `engine/src/prefill/prefill.cpp:5440-5458`。SYCL: `engine/sycl/src/prefill/prefill.cpp:3721-3747`。

## 値と判定

両 backend は `std::getenv("STRATA_SEL_OVERLAP") != nullptr` で設定有無だけを判定し、戻り値の内容は parse しない。未設定なら診断しない。値が空文字でも、`0`、`false`、大文字小文字違い、空白、任意の文字列でも、環境変数が存在すれば有効になる。無効値や数値境界の概念はない。初回評価結果を関数内 `static const bool` に保存するため、同一プロセス中に環境を変更しても反映されない（`engine/src/prefill/prefill.cpp:5442`、`engine/sycl/src/prefill/prefill.cpp:3723`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA/HIP 共通 prefill | 無効 | 空文字を含む、環境に存在する任意の値 | なし（値内容は検査しない） |
| SYCL prefill | 無効 | 空文字を含む、環境に存在する任意の値 | なし（値内容は検査しない） |
| Metal の共有 prefill ソース | 同じ判定式が共有ソースにある | 環境に存在する任意の値 | なし（値内容は検査しない） |

## 有効になる条件

- プロセスが該当 backend の Strata prefill 経路を実行し、QSA 層の選択処理まで到達すること。CUDA/HIP は共通 GPU engine の prefill ソース、SYCL は別プロジェクト内の移植ソースを使う（`engine/CMakeLists.txt:20-31`、`engine/cmake/strata_gpu_engine.cmake:478-488`、`engine/sycl/CMakeLists.txt:297-308`）。
- 判定が初めて評価された時点で環境変数が設定済みであること。値が有効でも、`qsa_index == 0`（先行する QSA 層がない最初の QSA 層）でなければ出力処理には入らない。index は chunk 開始時点で先行 QSA 層数に設定され、QSA 層の処理後に増える（CUDA/HIP: `engine/src/prefill/prefill.cpp:4594-4595`, `5575-5576`; SYCL: `engine/sycl/src/prefill/prefill.cpp:3027-3028`, `3902-3903`）。
- 別の環境変数、CLI 引数、サーバーモード、モデル設定による優先順位や上書きは、このフックの判定箇所にはない。対象モデルに QSA 層がなければこの処理は実行されない。

## 実行時の詳細

`getenv` は起動時ではなく、コードがこの分岐に初めて到達したときに評価され、その結果を関数内 static に保持する。設定が有効で最初の QSA 層にいる場合、選択済み ID 配列（`T * m.cap` 個）をホストメモリへコピーし、CUDA は `cudaStreamSynchronize`、SYCL は queue の `wait()` で完了を待つ。その後、`t0 + 16 <= T` の tileだけを走査して ID を sort/unique し、集計する。この同期・ホスト転送は診断時に加わるが、選択カーネルや ID の内容を書き換える処理はない（`engine/src/prefill/prefill.cpp:5442-5458`、`engine/sycl/src/prefill/prefill.cpp:3723-3747`）。

## ログと測定値

集計条件を満たすと、各 chunk の `p0` を位置として次の行を stderr に出す（文字列は両実装で同一）。`sum_w` が0の場合は割合を `0.0` とする。値が未設定の場合、または `qsa_index != 0` の場合はこの行を出さない。Strata の資料にこの変数による性能測定値は見当たらない。

```text
strata prefill: selection overlap at %lld: 16-query tiles read %.1f%% of the cells one query at a time does
```

根拠: `engine/src/prefill/prefill.cpp:5447-5458`、`engine/sycl/src/prefill/prefill.cpp:3735-3747`。

## 根拠

- `engine/src/prefill/prefill.cpp:5440-5458` — 設定有無の判定、同期コピー、tile集計、stderr 出力。
- `engine/sycl/src/prefill/prefill.cpp:3721-3747` — SYCL 版の同じ処理。
- `engine/cmake/strata_gpu_engine.cmake:478-488`、`engine/sycl/CMakeLists.txt:297-308`、`engine/metal/CMakeLists.txt:135-144` — 対象 backend が prefill ソースを build に含める箇所。
- `terminal/data/settings-register.json:43586-43621` — レジストリ上の読み取り先と `research` / `off` の分類。利用者向け動作の根拠は上記ソース。
