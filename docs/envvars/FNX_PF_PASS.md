# `FNX_PF_PASS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

sFNX の prompt prefill で、1 回の pass にまとめて処理する chunk 数を指定します。Engine は pass 数分の chunk 用 device buffer を確保し、prefill 中はその数を上限として prompt を分割します。ExpertCache がある場合は、pass ごとに RAM 上の expert を stage へコピーする仕組みと組み合わさります。通常の Strata engine ではなく、Qwen3.8-Flash-Next の全層を複数 GPU に分割する opt-in `sfnx` 実行経路の設定です（`src/split/CMakeLists.txt:1-7,64-79`; `src/split/src/engine.cu:31-36,274-275`）。

## 値と判定

`src/split/src/prefill.cu:810-812` は `env_int("FNX_PF_PASS", ...)` で値を読み、`1 <= pass <= PF_PASS` を要求します。`PF_PASS` は 8 です（`src/split/src/engine.hpp:353-356`）。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | その GPU の `w.ec.n_slots` が 0 なら 2、0 以外なら 4 |
| 有効な設定 | 10 進の整数で、1〜8（両端を含む） |
| 空文字・整数以外 | helper が `FNX_PF_PASS: '<値>' is not a whole number` の例外を送出 |
| 1 未満、8 超 | `FNX_PF_PASS: 1 to 8, got <値>` の例外を送出 |

helper は省略可能な符号と数字だけを許し、`strtoll` で base 10 の `long long` に変換します。文字列全体の消費とオーバーフローなしを確認するため、空白、末尾の文字、桁あふれは無効です。`+2` や `02` は整数として受理され、`-1` や `0` は整数として parse された後、範囲検査で拒否されます（`src/split/src/env.hpp:15-22,33-40`; `src/split/src/prefill.cu:810-812`）。

## 有効になる条件

- `STRATA_BUILD_SPLIT` でビルドされる sFNX が対象です。CMake は Linux CUDA または Linux HIP を対象とし、split engine はカード数別にビルドします。既定のカード数は 2 で、設定可能な範囲は 2〜4 です（`src/split/CMakeLists.txt:1-7,16-27,64-79`）。
- Engine の構築中に prompt prefill buffer を割り当てる際に読み取られます。カードごとに `w.ec.n_slots` を使った既定値が評価され、そのカードの pass 数として保持されます（`src/split/src/engine.cu:274-275`; `src/split/src/prefill.cu:625-635,810-812`）。
- `prefill()` は各カードの pass 数の最小値を `K` とし、最大 `K * pf_c_` token をまとめる単位で prompt を chunk 化します。最後の単位は短くなる場合があります。CLI 引数による `FNX_PF_PASS` の上書きはこの読み取り経路にはなく、値は環境変数から取得されます（`src/split/src/prefill.cu:982-1015`）。
- ExpertCache の slot があると既定 pass 数は 4、ないときは 2 です。slot がある場合は pass 中に expert stage を使うかを別途 prompt 長と stage 設定で決めます。`FNX_PF_PASS` 自体は stage の有無を切り替えません（`src/split/src/prefill.cu:810-812,832-845,989-992,1088-1137`）。

## 実行時の詳細

環境変数は Engine 構築時の `prefill_alloc()` で各カードについて読み、その結果を `Pf::pass` に保存します。1 より大きい値では、追加 chunk 用の residual、FFN/attention 出力、制御 buffer を確保します。これらの確保に失敗した場合の処理は一般の `palloc` の失敗経路であり、`FNX_PF_PASS` 固有の fallback はありません（`src/split/src/prefill.cu:625-643,807-820`）。

`prefill()` は全カード中の最小 pass 数を採用し、`per = K * pf_c_` ごとに prompt を分割して各区間を `prefill_pass()` に渡します。ExpertCache のある場合、stage 対象 expert の配置は pass の開始時に準備され、stage 有効時は各 layer の処理に合わせて expert をコピーします（`src/split/src/prefill.cu:982-1035,1088-1137`）。pass 数を変えることでこの処理単位と必要 buffer 数が変わります。ソースにはこの環境変数単独の性能値や出力同一性の測定記録は見つかりません。

値は Engine ごとに初期化時に保存されます。後からプロセス環境を変更しても、構築済み Engine の pass 数は再評価されず、リクエストごとにも読み直しません（`src/split/src/prefill.cu:810-820,982-992`）。

無効値の例外は `sfnx` の Engine 構築中に発生します。`sfnx` は `fail()` から stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` を出し、終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1030-1035,1052-1062`）。

## 根拠

- 読み取り、既定値、範囲検査、追加 buffer の確保: `src/split/src/prefill.cu:807-820`
- 整数 parse と parse エラー: `src/split/src/env.hpp:15-22,33-40`
- pass 数の上限と処理単位: `src/split/src/engine.hpp:353-356`; `src/split/src/prefill.cu:982-1015`
- Engine 構築時の呼び出しと sFNX の例外出力: `src/split/src/engine.cu:274-275`; `src/split/tools/sfnx.cpp:1030-1035,1052-1062`
- build 対象と backend: `src/split/CMakeLists.txt:1-7,20-27,64-79`
