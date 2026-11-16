# `STRATA_SYCL_GDN_STATE_COMMIT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL verifier が GDN 層の commit graph を記録するとき、GDN の状態更新に `gdn_commit_state_multi` を使うか、従来の `gdn_step_norm_multi` を使うかを切り替えるスイッチです。値が有効なら前者、そうでなければ後者をグラフに記録します。どちらの経路でも先に `gdn_conv_commit` を呼びます。通常の commit 経路では `gdn_step_norm_multi` の出力先は `y_dummy_` で、コメント上もリプレイ出力を参照しないとされています（`sycl/src/core/verify.cpp:2120-2139`）。

これは SYCL エンジン内の verifier commit 用です。通常の decode 全般や CUDA/HIP の経路で参照される変数ではありません。SYCL エンジン自体は `STRATA_ENABLE_SYCL` が有効な場合にビルド対象になります（既定値 `OFF`、`CMakeLists.txt:25-31`）。

## 値と判定

読み取りは `std::getenv` で行い、値の先頭文字が `'1'` かだけを判定します。未設定または空文字は無効です。`1`、`10`、`1anything` は有効になり、`0`、`true`、` 1`、`01`、その他 `'1'` で始まらない値は無効です。数値変換、空白除去、文字列全体の比較、大文字小文字の正規化はありません（`sycl/src/core/verify.cpp:2129-2134`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `Verifier::capture_commit` が GDN 層を処理する場合 | `state_only == false`。`gdn_step_norm_multi` を記録 | 先頭文字が `1` の値。`gdn_commit_state_multi` を記録 | 空文字、`0`、`true`、`01` など。`gdn_step_norm_multi` を記録 |

## 有効になる条件

- SYCL エンジンで verifier を使い、`capture_commit` が実行されること。SYCL エンジンのビルドは `STRATA_ENABLE_SYCL` によって選択されます（`CMakeLists.txt:25-31`）。
- 対象 verifier の layer range に GDN 層があること。`capture_commit` は layer range を走査し、QSA ではない層でのみこの設定を評価します（`sycl/src/core/verify.cpp:2118-2129`）。モデル・ステージに該当 GDN 層がなければ、この設定はその verifier では読み取られません。
- 通常の verifier 実行では `run` が commit graph を準備します。パイプライン実行では `capture_all` が同じ `capture_commit` を呼びます（`sycl/src/core/verify.cpp:2278-2292`, `4040-4048`）。生成・serve 側では `--spec` を verifier の窓幅として渡し、生成時には `--spec` が 2 以上の場合に verifier を初期化します（`sycl/src/program/generate.cpp:1983`, `13336-13357`, serve の初期化は `7713-7718`）。
- `--batch` の slot 用 commit graph は別関数 `capture_commit_batch` で記録され、この環境変数の分岐を含みません。その経路の GDN commit は `gdn_step_norm_multi` または `gdn_step_norm_groups` です（`sycl/src/core/verify.cpp:3292-3325`, `3336-3358`, `3485`）。
- CLI 引数、設定ファイル、他の環境変数による上書き・優先順位はありません。設定が無効でも通常の `gdn_step_norm_multi` 経路に戻ります（`sycl/src/core/verify.cpp:2129-2139`）。

## 実行時の詳細

設定はプロセス起動時ではなく、`capture_commit` が最初に GDN 層の commit graph を記録するときに読みます。関数内の `static const bool` なので、その判定はプロセス内で一度だけ評価され、以後の verifier や環境値の変更には反映されません。すでに `commit_exec_` がある verifier では graph の再記録も行いません（`sycl/src/core/verify.cpp:2100-2101`, `2129`）。

有効時は、`gdn_conv_commit` の後に `gdn_commit_state_multi` を記録します。無効時は同じ位置で `gdn_step_norm_multi` を記録し、`z_`、`ssm_norm.weight`、`EPS`、`y_dummy_` も渡します。GDN 層以外の処理、QSA の indexer 更新、PLE 履歴更新はこの分岐の外です（`sycl/src/core/verify.cpp:2120-2159`）。

この選択は記録された command graph に保持されます。commit 時には `commit_exec_` を起動し、必要な keep 数と位置を graph 入力へ設定します。1-token window が既に state を進めており self-commit が有効な場合は、通常 commit で graph の起動を省略します（`sycl/src/core/verify.cpp:3040-3052`, `3047-3049`）。

## ログと測定値

この変数専用の有効・無効ログや測定値はありません。commit graph の起動時にエラーコードが返ると `verify: commit launch: ...` を `err` に設定して失敗を返します。SYCL 例外は catch 節で例外文字列とファイル・行を stderr に出し、`exit(1)` します。これらは変数固有の失敗ではありません（`sycl/src/core/verify.cpp:3065-3068`, `3040-3041`, `3087-3090`, `2190-2192`）。

## 根拠

- `sycl/src/core/verify.cpp:2100-2139` — commit graph の生成、環境変数の判定、および GDN 経路の選択。
- `sycl/src/core/verify.cpp:2278-2292`, `4040-4048` — 通常実行とパイプライン準備からの `capture_commit` 呼び出し。
- `sycl/src/core/verify.cpp:3040-3052`, `3065-3068` — commit graph の起動と失敗の返却。
- `sycl/src/core/verify.cpp:3292-3358`, `3485` — batch 用の別 commit graph 経路。
- `sycl/src/program/generate.cpp:1983`, `7713-7718`, `13336-13357` — `--spec` と verifier 初期化。
- `CMakeLists.txt:25-31` — SYCL エンジンがビルド対象となる条件。
