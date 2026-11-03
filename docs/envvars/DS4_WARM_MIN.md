# `DS4_WARM_MIN`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 エンジンの chunked prompt 処理後に行う decode warm-up の開始条件を、処理した token 数で決めます。条件を満たすと、prompt の最後の行が選んだうち、GPU slot や RAM にない expert のファイル範囲について、decode と並行するスレッドから OS の prefetch 要求を出します。VRAM へ expert をコピーする設定ではありません。

この環境変数は `strata-dsv41` の実装にあります。CMake の `STRATA_BUILD_DSV41` は既定 OFF で、このオプションを有効にすると同実行ファイルへ `src/dsv41/ds4_model.cu` が組み込まれます（`CMakeLists.txt:931-945`）。

## 値と判定

未設定なら閾値は `512` です。設定されている場合は `std::atoi` の結果を使い、文字列全体の妥当性検査、範囲制限、無効値の警告はありません。

| 値 | 閾値 `wmin` の結果 | `n < wmin` の判定 |
|---|---:|---|
| unset | 512 | `n` が 512 未満なら warm-up を行わない |
| `512` | 512 | unset と同じ |
| 空文字、数字で始まらない文字列 | 0 | `n` が負でない限り、この条件では止めない |
| `128tail` | 128 | 数字の先頭部分を変換した閾値になる |
| `-1` | -1 | 通常の非負 `n` では、この条件では止めない |

`atoi` は先頭の空白と符号を許し、数字列の後ろは変換対象にしません。変換できる数字がない場合は 0 になります。オーバーフローを含む値域検査は実装していません。閾値は `warm_after()` 内の `static const int` なので、最初に同関数が呼ばれた時点で一度だけ読みます。以後プロセス内で環境値を変更しても閾値は再評価されません（`src/dsv41/ds4_model.cu:12785-12787`）。

## 有効になる条件

閾値を満たしても、`warm_after()` は次の条件をすべて通る場合にだけ warm-up を開始します。

- `file_experts` が有効である。GGUF ではこの値を有効にし、その他の形式では `--mmap-experts` または自動判定で決まります（`src/dsv41/ds4_model.cu:2750-2771`）。
- `L` が空でなく、先頭 layer の形式が MXFP4 である。
- 複数 GPU のときは `DS4_WARM_GB` が設定されている。未設定なら複数 GPU では戻ります（`src/dsv41/ds4_model.cu:12787-12789`）。
- 候補に使う `last_picks` があること。新しい picks は flow の最終 chunk で最大 32 行分記録されます。非 flow 経路では更新されませんが、この処理は vector を clear しないため、以前の flow で保存した値が残っていれば warm-up がその値を読む可能性があります（`src/dsv41/ds4_model.cu:11776-11780,12793-12811`）。
- `DS4_WARM_GB` から決まる予算が正である。未設定なら空き RAM と 8 GiB の余裕から半分を見積もり、最大 32 GB、空き RAM が不明なら 8 GB とします。設定時は `atof` の結果が予算を上書きし、0 以下なら warm-up を行いません（`src/dsv41/ds4_model.cu:12789-12792`）。

`DS4_WARM_MIN` に対応する CLI 引数や他の環境変数による閾値上書きはありません。`DS4_WARM_GB` は warm-up の予算と複数 GPU 時の許可条件を変えますが、閾値は変えません。

## 実行時の詳細

`warm_after(took)` は `forward_chunks()` の処理後に呼ばれ、閾値と比較するのはその呼び出しで処理された `took` です（`src/dsv41/ds4_model.cu:13175-13187`）。通常の `feed()` では chunked prompt 経路に入る条件として `chunk > 0` かつ入力 `n >= chunk_min` があり、flow 選択または全行 logits の場合に `forward_chunks()` が実行されます（`src/dsv41/ds4_model.cu:14862-14875`）。

候補は最後の最大 32 行の expert picks を、末尾行から layer 順にたどって作ります。同じ layer/expert の重複、GPU slot にある expert、`l.ram` にある expert は除外されます。その後専用 thread が候補を順に処理し、各 expert の3範囲を sampled residency check して、未 resident と見なした範囲に `os::prefetch()` を呼びます。thread は次の `forward_chunks()` の開始時に停止・join され、モデル破棄時にも join されます（`src/dsv41/ds4_model.cu:901,1163,12793-12840,12945-12953,1895-1899`）。

`os::prefetch()` は Windows では `PrefetchVirtualMemory`、それ以外では `madvise(..., MADV_WILLNEED)` を呼びます。戻り値を検査せず、失敗時の Strata の警告やエラー処理はありません（`src/dsv41/ds4_os.hpp:348-367`）。`o.verbose` が有効なら stderr に `ds4: decode warm-up: ...` の進捗行を出します。閾値未満や他の条件で戻る場合、`DS4_WARM_MIN` 専用のログはありません（`src/dsv41/ds4_model.cu:12810-12835`）。

## 根拠

- 候補名の全参照は `src/dsv41/ds4_model.cu` のコメントと読み取り箇所の2件です。実際の読み取りは `std::getenv("DS4_WARM_MIN")` と `std::atoi` によるものです（`src/dsv41/ds4_model.cu:12779-12787`）。
- prompt 後の呼び出しと直近 picks の保存: `src/dsv41/ds4_model.cu:11776-11780,13175-13187`。
- 実行ファイルのビルド条件: `CMakeLists.txt:931-945`。
