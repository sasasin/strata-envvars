# `DF2B_GRAPH`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の `dflash2_bench` が、DFlash2 の直接 launch 測定に加えて SYCL command graph の replay 測定を実行するかを切り替えます。Strata engine のモデル推論・サーバー経路では読み取られず、ベンチマーク専用です。ソース先頭の説明も `DF2B_GRAPH=0` を graph replay のスキップとして挙げています（`sycl/src/kernels/dflash2_bench.cpp:1-9`）。

## 値と判定

`envi("DF2B_GRAPH", 1)` が `getenv()` の値を受け、空でない場合だけ `atoi()` で整数に変換します。変換後の整数が C++ の条件式で 0 なら replay を飛ばし、0 以外なら replay を試みます（`sycl/src/kernels/dflash2_bench.cpp:56-57,547`）。

| 環境値 | 判定 |
|---|---|
| 未設定 | 既定値 `1`。graph replay を試みる |
| 空文字 | `envi()` が既定値 `1` を返す。graph replay を試みる |
| `0`、`00`、`-0` | `atoi()` の結果が 0。graph replay を飛ばす |
| `1`、`2`、`-1` など、変換結果が非ゼロ | graph replay を試みる |
| `abc` など、先頭から整数に変換できない文字列 | `atoi()` の結果が 0。graph replay を飛ばす |
| `1tail`、` 1x` など、先頭部分が整数として読める文字列 | `atoi()` が得る整数を使う。例では結果が 1 なので replay を試みる |

文字列全体の一致や範囲検査はありません。したがって `DF2B_GRAPH=true` は真偽値として解釈されず、`atoi()` の結果 0 となって replay を飛ばします。数値として表現可能な範囲を超える値の変換結果は、このコードから保証できません。

## 有効になる条件

- 対象は `sycl/src/kernels/dflash2_bench.cpp` の `dflash2_bench` のみです。CMake では `STRATA_SYCL_PARITY` が ON のときに同実行ファイルを追加し、この option の既定値は ON です（`sycl/CMakeLists.txt:289-291,437-438`）。
- `main()` は引数なしなら `bench` を選び、`test`、`gemm`、`attn`、`dp4a`、`bubble`、`small`、`poison`、`poison2`、`ctx` ならそれぞれ別の関数を呼びます。これらの経路は `run_bench()` の graph 判定に入りません。列挙外の引数は最後の分岐により `run_bench()` へ進みます（`sycl/src/kernels/dflash2_bench.cpp:894-902`）。
- `run_bench()` に入ると、まず直接 launch の測定を行い、その後にこの値を評価します。0 の場合も直接 launch 測定は行われます（`sycl/src/kernels/dflash2_bench.cpp:486-489,525-547`）。

## 実行時の詳細

値は graph replay 分岐に到達するたびに `getenv()` で読み取られ、`static` cache はありません。判定が有効なら command graph の記録・確定を行い、反復実行して時間と checksum を `GRAPH    wall ms/round: ...` の形式で stdout に出します。graph の構築・実行中に `std::exception` が発生した場合は `GRAPH    unavailable: <例外文>` を stdout に出して catch し、後続の profile 処理へ進みます。値を 0 として分岐を飛ばした場合、graph の測定行は出ません（`sycl/src/kernels/dflash2_bench.cpp:547-601`）。

この環境変数による Strata 独自の終了・失敗処理はありません。graph が使えるかどうかや例外の原因について、ここでは外部 SYCL 実装の動作を説明しません。

## 根拠

- 読み取り helper と変換規則: `sycl/src/kernels/dflash2_bench.cpp:56-57`
- graph replay の条件・処理・観測出力・例外処理: `sycl/src/kernels/dflash2_bench.cpp:525-572`
- `run_bench()` の入口と、他の positional mode を含む dispatch: `sycl/src/kernels/dflash2_bench.cpp:486-489,894-902`
- ベンチマーク実行ファイルの CMake 定義と構成条件: `sycl/CMakeLists.txt:289-291,437-438`
