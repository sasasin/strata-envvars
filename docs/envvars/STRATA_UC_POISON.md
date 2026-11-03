# `STRATA_UC_POISON`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

SYCL 版 `strata` のテスト用カーネル計測フックで、最初の計測の後に指定した小さなカーネルを一度実行します。通常の性能・生成設定ではなく、`STRATA_UC_PROBE` が有効な場合だけ処理されます。呼び出し箇所は SYCL の `src/program/generate.cpp` であり、SYCL ビルド以外にはこのフックは組み込まれません（`sycl/CMakeLists.txt:284-286`）。

## 値と判定

値は `std::string` との完全一致で比較されます。大文字小文字や前後の空白は変換されません。

| 値 | 実行する処理 |
|---|---|
| `fp64` | device メモリに double 配列を確保し、64 要素に平方根と乗算を書き込む kernel を実行して解放する |
| `uc_read` | `host_malloc_polled` の 4096-byte host 領域をゼロ初期化し、kernel から 64 個の int を読み device 領域へ書く |
| `uc_write` | 同じ host 領域をゼロ初期化し、kernel から 64 個の int を host 領域へ書く |
| `cached_read` | `sycl::malloc_host` の 4096-byte 領域をゼロ初期化し、kernel から 64 個の int を読み device 領域へ書く |
| `shared_write` | 4096-byte shared 領域を確保し、kernel から 64 個の int を書く |
| 上記以外の非空文字列 | 分岐に一致せず、カーネル処理は行わない |

未設定（`getenv` が null）と空文字は poison 処理を呼びません。空文字は `if (p[0])` で除外されます。数値変換や fallback はありません。`uc_read` / `uc_write` / `cached_read` は device allocation を解放しますが、対応する host allocation はこの関数内で解放されません。`shared_write` の shared allocation も解放されません。`uc_read` / `uc_write` の host allocation はコードコメントでテスト用に意図的にリークするとされています（`sycl/include/strata/uc_probe.hpp:52-74`）。

## 有効になる条件

- `strata` の SYCL 実行ファイルであること。
- `STRATA_UC_PROBE` が初回 `uc_probe()` 呼び出し時に有効と判定されていること。判定は `static const bool` に保存され、未設定または空文字なら無効、値の先頭文字が `0` なら無効、それ以外の非空値なら有効です。したがって `false` も有効です（`sycl/include/strata/uc_probe.hpp:26,77-80`）。
- probe が有効な状態で、`uc_probe()` が最初に到達すること。`STRATA_UC_POISON` はこの初回 probe の計測後にのみ読み、以後の probe では読みません。SYCL generate の起動処理は引数解析前に `uc_probe("start")` を呼びます（`sycl/src/program/generate.cpp:1790-1805`）。

CLI 引数による上書きはありません。`uc_read` / `uc_write` は `host_malloc_polled` を使います。この helper は `STRATA_HAVE_ZE` が定義され、かつ queue が Level Zero backend で、さらに helper 内の `STRATA_HOST_UNCACHED` 判定が有効な場合に Level Zero host allocation を試します。それ以外は `sycl::malloc_host` に fallback します。`STRATA_HOST_UNCACHED` の判定も先頭文字が `0` かどうかで、helper 内で一度 cache されます（`sycl/include/strata/sycl_queue.hpp:63-78`）。

## 実行時の詳細

`uc_probe()` は probe が有効なら engine の in-order queue を使い、計測用の四種類の kernel を実行して stderr に計測行を出力します。最初の probe の計測後、`STRATA_UC_POISON` が設定されていて空でなければ `ucprobe::poison(q, p)` を呼び、戻ると `UCPROBE poisoned with <値>` を stderr に出して `uc_probe("after-poison")` を再度実行します。未知の非空値も `poison()` 内では何もしませんが、このログは出ます。したがってこの文言だけではカーネルが実行されたことを確認できません（`sycl/include/strata/uc_probe.hpp:77-80,82-150,151-155`）。

各 kernel の `.wait()` や allocation で起きた失敗をこの poison 経路は捕捉しません。例外が送出された場合、`poisoned with` と後続 probe には到達しません。実装にはこの環境変数用の明示的な警告・無効値エラー・終了コード分岐はありません（`sycl/include/strata/uc_probe.hpp:52-74,151-154`）。

## 根拠

- 読み取りと初回だけの実行、値の分岐: `sycl/include/strata/uc_probe.hpp:26,52-80,151-155`
- probe 呼び出し元と起動時の位置: `sycl/src/program/generate.cpp:28,1790-1805`; probe 呼び出し全箇所: 同 `3083,3095,3691,4455,5244,5784,9143,12475,12643,12764,13313,13724`
- SYCL 実行ファイルへの組み込み: `sycl/CMakeLists.txt:284-286`
- `uc_read` / `uc_write` の allocation 条件と fallback: `sycl/include/strata/sycl_queue.hpp:63-78`
