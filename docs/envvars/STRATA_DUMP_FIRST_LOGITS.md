# `STRATA_DUMP_FIRST_LOGITS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

最初の verify window の語彙 logits を float 配列としてファイルへ書く診断用の出力先指定である。CUDA/HIP 側の `generate` と server、および SYCL 側の `generate` に読み取りがある。値は有効・無効のフラグではなくファイル名（server では接尾辞を付ける基底名）として使われる。logits の計算、token の選択や生成制御を変更する分岐ではなく、copy とファイル出力だけを追加する（`engine/src/program/generate.cpp:22996-23008,25169-25182`、`engine/sycl/src/program/generate.cpp:14167-14179`）。

## 値と判定

3 箇所とも `std::getenv` の結果が `nullptr` かどうかだけを見る。文字列の parse、数値変換、空白除去、大小文字変換、値域検査はない。空文字列も設定済みとして扱われる。`generate` はその値をそのまま出力ファイル名に渡すため、空文字列なら空のパスで open を試み、失敗時に警告する。server は値に `.<n>` を追加するため、空文字列なら `.0`、`.1` などを試す。`0`、`false`、`off`、`true` なども、文字列の意味を判定せずファイル名として使用する（同上）。

| 経路 | unset | 設定ありの例 | 判定される無効値 |
|---|---|---|---|
| CUDA/HIP `generate`、SYCL `generate` | 出力しない | `/tmp/logits.bin` はそのパスへ出力 | 該当なし。空文字列を含め、`nullptr` 以外は出力を試みる |
| CUDA/HIP server | 出力しない | `/tmp/request` は `/tmp/request.0`, `.1`, … へ出力 | 該当なし。空文字列を含め、`nullptr` 以外は出力を試みる |

CLI 引数や別の環境変数との優先順位・fallback は実装されていない。値はパスとしてのみ使われる（`engine/src/program/generate.cpp:22999-23006,25176-25180`、`engine/sycl/src/program/generate.cpp:14173-14177`）。

## 有効になる条件

- 対象の実行経路で最初の verify window が正常に実行されること。`generate` では `first_window` の処理内、server では各リクエストの最初の window の処理内で出力を試みる（`engine/src/program/generate.cpp:22990-23004,25130-25178`、`engine/sycl/src/program/generate.cpp:14114-14175`）。
- この読み取りを持つ実装は `engine/src/program/generate.cpp` と `engine/sycl/src/program/generate.cpp` にある。前者は `engine/cmake/strata_gpu_engine.cmake:548` で GPU engine の実行ファイルに組み込まれ、後者は `engine/sycl/CMakeLists.txt:40` に列挙される。これらの箇所から確認できるのは当該実装の存在であり、Metal 実装やその他の実行形式での有効性は確認できない。
- `ver.copy_logits` が成功し、指定先を `fopen(..., "wb")` で開け、語彙数分の `float` 書き込みが成功した場合にファイル内容が得られる。copy または open/write が失敗しても、この診断出力自体は生成処理の失敗にせず警告を出す（`engine/src/program/generate.cpp:23002-23008,25177-25182`、`engine/sycl/src/program/generate.cpp:14174-14179`）。

## 実行時の詳細

`generate` は `first_window` が真のときに環境を読み、logits 行 0 をコピーして、指定されたパスを `wb` で開き、`ver.vocab()` 個の `float` を書く。CUDA/HIP と SYCL の読み取りは各 generate 実行の最初の window に限られる。server は最初の request window 後に関数内 `static` の `fl` と `fl_n` を初期化し、以後の各リクエストの最初の window で `fl.<n>` に出力する。したがって server の値はプロセス内で初回評価時にキャッシュされ、番号はその server 処理内で増える（`engine/src/program/generate.cpp:22996-23007,25169-25181`、`engine/sycl/src/program/generate.cpp:14167-14178`）。

ファイルには `fwrite` に渡す `float` 配列がそのまま書かれ、ヘッダーや文字列形式への変換はない。server は `merged` window の場合 `T-1` 行、それ以外は 0 行をコピーし、`generate` は 0 行をコピーする（`engine/src/program/generate.cpp:23002-23005,25176-25180`）。`Verifier::copy_logits` は CUDA/HIP では head の logits を host へコピーし、SYCL でも head logits を host へコピーする。層分割時は次段へ転送して head を持つ verifier でコピーする（`engine/src/core/verify.cpp:5864-5872`、`engine/sycl/src/core/verify.cpp:4114-4123`）。

## ログと測定値

書き込みまたは logits copy が失敗した場合、stderr に `strata generate: STRATA_DUMP_FIRST_LOGITS: cannot write <path>`（CUDA/HIP または SYCL の generate）、server では `strata serve: STRATA_DUMP_FIRST_LOGITS: cannot write <path>` を出す。どちらもこの診断出力の失敗だけで終了コードを変更する処理はない（`engine/src/program/generate.cpp:23004-23007,25178-25181`、`engine/sycl/src/program/generate.cpp:14175-14178`）。

`docs/SETTINGS.md:62` は値種別を `on / off` と記すが、現行コードは真偽値でなく任意の非 null 文字列をファイルパスとして扱うため、その分類は実装と一致しない。同表が挙げる NVIDIA/AMD と Intel Arc は該当実装ファイルと整合する。`docs/DGX_SPARK_LINUX.md:132-136` はこの変数を使った比較に触れるが、そこに記載された測定は他のスイッチの比較結果であり、この変数自体の性能・正確性を測定した結果ではない。

## 根拠

- `engine/src/program/generate.cpp:22996-23008` — server の初回 window 判定、static cache、ファイル名接尾辞、ログ。
- `engine/src/program/generate.cpp:25169-25182` — CUDA/HIP generate の初回 window、読み取り、出力。
- `engine/sycl/src/program/generate.cpp:14167-14179` — SYCL generate の初回 window、読み取り、出力。
- `engine/src/core/verify.cpp:5864-5872`、`engine/sycl/src/core/verify.cpp:4114-4123` — logits の host copy。
- `engine/cmake/strata_gpu_engine.cmake:548`、`engine/sycl/CMakeLists.txt:40` — 該当 generate 実装の実行ファイルへの組み込み。
- `docs/SETTINGS.md:62`、`docs/DGX_SPARK_LINUX.md:132-136` — 文書記載との照合。
