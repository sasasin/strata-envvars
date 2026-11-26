# `STRATA_PREFILL_DUMP_R`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prefill の chunk が終わった時点の residual 行を、環境変数の値をファイル名としてバイナリ出力する診断用スイッチです。CUDA/HIP の chunk-major `Prefill::run_impl` と layer-major `Prefill::lm_run`、および SYCL の `Prefill::run_impl` が読み取ります。値は真偽値ではなく出力先パスとして使われ、各 chunk で位置番号が 64 の倍数となる行だけを記録します。ログ出力やモデル計算の選択を直接変える処理ではありません。実装は `engine/src/prefill/prefill.cpp` と `engine/sycl/src/prefill/prefill.cpp` にあります（CUDA/HIP: `engine/src/prefill/prefill.cpp:7845-7856,9190-9201`、SYCL: `engine/sycl/src/prefill/prefill.cpp:5572-5585`）。

## 値と判定

3 か所とも `std::getenv("STRATA_PREFILL_DUMP_R")` の null 判定だけを行い、文字列を parse せず、返された文字列全体を `std::fopen` のパスに渡します。未設定ならその箇所の出力処理をしません。空文字列を含め、設定されていれば出力を試みます。`"0"`、`"1"`、`"true"`、`"false"`、空白付きの値も特別扱いされず、そのままファイル名です。たとえば `0anything` も無効値として拒否されず、その名前のファイルを開こうとします。境界値や数値変換はありません（同上）。

| 条件 | unset | 出力を試みる値 | 特別扱いされる値 |
|---|---|---|---|
| CUDA/HIP chunk-major・layer-major、SYCL chunk-major | 出力しない | `dump.bin`、`/tmp/residuals.bin` など、空でないパス文字列 | なし。`0` や `false` もパスとして扱う |
| いずれの経路でも空文字列 | — | `fopen("")` を試みる | 真偽値としては拒否されないが、ファイルを開けなければ何も書かず、Strata は警告しない |

## 有効になる条件

- 対象の prefill 実装が動き、該当 chunk の residual `m.R` ができていること。Metal 実装にはこの名前の読み取りがありません。
- ファイルを開けるパスを指定すること。`fopen` が失敗した場合は出力ブロックを抜けるだけで、Strata のログやエラーにはなりません（CUDA/HIP: `engine/src/prefill/prefill.cpp:7845-7856,9190-9201`、SYCL: `engine/sycl/src/prefill/prefill.cpp:5572-5585`）。
- CUDA/HIP の layer-major 経路は、`STRATA_PREFILL_LAYER_MAJOR` と `STRATA_DEFAULTS` 等でその経路が選ばれ、`lm_prepare_chain` が成功した場合に実行されます。`STRATA_PREFILL_DUMP_R` 自体は layer-major の適格性を落としません。一方 `STRATA_PREFILL_DUMP_R_ALL` が設定されていると `lm_prepare` が「a routing or row debug dump」を理由に layer-major を断り、通常の `run_impl` に進みます（`engine/src/prefill/prefill.cpp:8205-8209,9657-9705`）。

## 実行時の詳細

- CUDA/HIP chunk-major は chunk 処理の後に環境を読み直します。設定があれば stream を同期し、`c0 == 0` の chunk では `"wb"`、後続 chunk では `"ab"` で開きます。各 `p0+t` が 64 の倍数になる `t` を走査し、まず位置を `int64_t` で、続いてその位置の `D` 個の `float` residual を書きます（`engine/src/prefill/prefill.cpp:7845-7856`）。
- CUDA/HIP layer-major も `l == LE` の最終行で同じ形式を出力します。環境はそこでも読み直され、chunk の先頭では上書き、後続 chunk では追記です（`engine/src/prefill/prefill.cpp:9186-9201`）。layer-major の準備で `STRATA_PREFILL_DUMP_R` を cache したり、無効化したりはしません。
- SYCL の chunk-major は各 chunk の処理後に読み直し、queue を待ってから同じ位置選択・位置番号・float 行を出力します。先頭 chunk は `"wb"`、後続 chunk は `"ab"` です（`engine/sycl/src/prefill/prefill.cpp:5572-5585`）。
- いずれも読み取りは chunk ごとの実行時で、関数内 `static` cache はありません。Strata 内でプロセス環境を書き換えた場合は後続 chunk の読み取りに反映されます。別プロセスから起動済みプロセスの環境を書き換える仕組みは本処理にはありません。
- `fopen` の成否以外に書き込み結果（`fwrite`）や CUDA の同期戻り値は検査していません。失敗時の明示的な警告・エラー文、終了処理はこの出力箇所にはありません（同上）。

## ログと測定値

この変数専用のログや測定値はありません。成功時の観測結果は指定ファイルのバイナリ内容です。出力レコードはネイティブ表現の `int64_t` 位置番号と、それに続く `D` 個のネイティブ `float` 値です。ファイルを開けない場合や書き込みが失敗した場合も、この処理は独自のログを出しません（`engine/src/prefill/prefill.cpp:7847-7855,9192-9200`、`engine/sycl/src/prefill/prefill.cpp:5574-5584`）。

## 根拠

- `engine/src/prefill/prefill.cpp:7845-7856` — CUDA/HIP chunk-major の読み取り、chunk ごとの上書き・追記、64 位置ごとの位置番号と residual 書き出し。
- `engine/src/prefill/prefill.cpp:8166-8209` — layer-major の準備条件。`STRATA_PREFILL_DUMP_R_ALL` は拒否条件だが、対象変数は拒否条件に含まれない。
- `engine/src/prefill/prefill.cpp:9186-9201` — CUDA/HIP layer-major の最終行出力。
- `engine/src/prefill/prefill.cpp:9657-9705` — layer-major 選択、準備失敗時の通常 `run_impl` へのフォールバック。
- `engine/sycl/src/prefill/prefill.cpp:5572-5585` — SYCL chunk-major の同等の読み取りと出力。
