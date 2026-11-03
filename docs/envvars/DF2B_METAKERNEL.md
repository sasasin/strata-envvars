# `DF2B_METAKERNEL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の `dflash2_bench` が benchmark round のメタデータと RoPE 表を device に渡す方法を選びます。既定では `sycl::queue::memcpy` を使い、変数から得た整数が 0 以外なら host 側配列を読む SYCL `parallel_for` に切り替えます。Strata の通常の推論エンジンで読む箇所は確認できず、この変数は同梱 benchmark 専用です。

## 値と判定

`main()` が `envi("DF2B_METAKERNEL", 0)` を呼び、共通 helper は未設定または空文字なら既定値を返し、それ以外は `std::atoi` で整数に変換します。変換結果が 0 かどうかだけが分岐に使われます。文字列全体の妥当性検査、範囲制限、警告、fallback はありません。

| 環境変数の値 | helper の結果 | benchmark round の選択 |
|---|---:|---|
| 未設定 | 0 | `queue::memcpy` |
| 空文字 | 0 | `queue::memcpy` |
| `0`、`abc`、`0tail` | 0 | `queue::memcpy` |
| `1`、`-1`、`2tail` | 0 以外 | SYCL `parallel_for` |

`atoi` のため、先頭の空白や符号を含む整数接頭辞も変換対象になり、後続の非数値部分は検査されません。整数として表現できない値に対する `atoi` の結果は規格上保証されないため、文書ではその値から選択結果を断定しません。

## 有効になる条件

- 対象は `sycl/CMakeLists.txt` が定義する独立実行ファイル `dflash2_bench` です。通常の Strata engine に対する設定としては確認できません。
- 実行モードが `bench`（引数なしの既定）または未知のモード名で `run_bench()` に入る場合、warm-up、direct 計測、kernel profile 用の round は `io=true` でこの値を参照します。
- graph 用の記録は `record_round(..., false)` で行われ、関数内で `io` が false の場合はメタデータ転送分岐を通りません。graph の各 replay 前には別の `queue::memcpy` が明示的に実行されるため、この変数は graph replay の転送方法を変えません。
- `test`、`gemm`、`attn`、`dp4a`、`bubble`、`small`、`poison`、`poison2`、`ctx` の各モードは `run_bench()` に入らず、当該設定による転送の変更を受けません。

## 実行時の詳細

値はプロセスの `main()` 冒頭で一度読み取られ、グローバル変数 `g_meta_kernel` に保存されます。`record_round()` は `io=true` なら host の `h_meta` から device の `d_meta` へ、メタデータ 32 個と RoPE 表 2048 個（各 `int32_t`）を転送します。設定値が 0 の場合は 2080 要素を `queue::memcpy` し、0 以外の場合は同じ範囲を対象にした `parallel_for` の各 work item が host 側から読み device 側へ 1 要素ずつ代入します。その後、どちらの経路も `meta_rope` stamp を記録して context と block の処理に進みます。

変数固有のログや警告はありません。benchmark は通常の device/configuration、round timing、checksum 等を出力しますが、出力だけでどちらの転送分岐が選ばれたかを示す表示は見つかりませんでした。分岐内にこの変数専用のエラー処理もありません。

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:56-57` — `envi` の未設定・空文字処理と `atoi` 変換。
- `sycl/src/kernels/dflash2_bench.cpp:203-207,259-271` — グローバル設定、`io` 条件、および memcpy / kernel の分岐と後続処理。
- `sycl/src/kernels/dflash2_bench.cpp:486-495,510-512,525-535,547-564,573-584` — benchmark warm-up・direct/profile 呼び出しと graph 記録・replay の別経路。
- `sycl/src/kernels/dflash2_bench.cpp:894-901` — main での一度の読み取りと mode dispatch。
- `sycl/CMakeLists.txt:437-438` — `dflash2_bench` の独立 SYCL target 定義。
- 候補名の `rg` 全参照は `sycl/src/kernels/dflash2_bench.cpp` 内のコメント、helper 呼び出し、グローバル変数と分岐に限られます。`docs/DETAILS.md` にはこの変数や benchmark の説明は見つからず、追加の文書上の仕様は確認できませんでした。
