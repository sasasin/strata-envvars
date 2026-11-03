# `DF2B_STANDIN_MB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL 版の診断用実行ファイル `dflash2_bench` が benchmark モードで、各 timed round の前にメモリ帯域負荷 kernel を投入するための float 配列サイズを MB 単位で指定します。Strata 本体の推論処理からは読み取られず、このベンチマーク専用です。実行ファイルは `STRATA_SYCL_PARITY` が有効なビルドで追加されます（既定 ON）。

## 値と判定

共通 helper は値を整数全体として検証せず、空でない場合に `std::atoi` で変換します。`run_bench()` の既定値は `0` です。

| 環境値 | `standin_mb` | 結果 |
|---|---:|---|
| 未設定 | 0 | stand-in 配列を作らず、kernel を投入しない |
| 空文字 | 0 | helper が既定値を返し、kernel を投入しない |
| `0` | 0 | kernel を投入しない |
| 正の整数文字列（例: `128`） | その整数 | `standin_mb * 1024 * 1024 / 4` 個の float を確保し、その全体を読む kernel を投入する |
| 数字の後ろに文字（例: `12MB`） | `atoi` が読む先頭整数（例: 12） | 変換された整数に従う。文字列全体の検証はない |
| 数値に変換できない非空文字列 | 0 | kernel を投入しない |
| 負の整数 | 負値 | 0 への clamp はない。要素数を計算する際に `size_t` へ変換され、大きなサイズとして確保が試みられる |

空白や符号なども `atoi` の変換規則に従い、独自の境界検査はありません。`atoi` の表現範囲を超える入力に対する Strata 独自の処理もありません。MB は 1024×1024 bytes として扱い、float 1 個あたり 4 bytes で要素数を計算します。

## 有効になる条件

- `sycl/src/kernels/dflash2_bench.cpp` の `run_bench()` を通る場合に限り、この変数を読みます。引数なし、未知の mode、または `bench` mode は `run_bench()` を呼びます。`test`、`gemm`、`attn`、`dp4a`、`bubble`、`small`、`poison`、`poison2`、`ctx` は別関数へ進み、この値を使いません。
- `dflash2_bench` は SYCL CMake プロジェクト内のターゲットで、`STRATA_SYCL_PARITY` が ON の場合に定義されます。これは CUDA/HIP の通常エンジン設定ではありません。
- `DF2B_GRAPH` は既定で有効です。GRAPH 計測も実行されるときは、その各 round の前にも同じ stand-in kernel が投入されます。`DF2B_GRAPH=0` なら GRAPH 計測は省かれますが、DIRECT 計測前の投入は残ります。
- CLI 引数や他の変数が `DF2B_STANDIN_MB` を上書きする処理はありません。

## 実行時の詳細

値は `run_bench()` 冒頭で一度読み取られ、ローカル変数に保持されます。プロセス起動後に環境値を変えても、この実行中の値は再評価されません。

値が 0 以外なら、まず `standin_mb * 1024 * 1024 / 4` 個の float を持つホスト `std::vector` を作り、値 1.0 で埋めてから同じ要素数を GPU device memory に確保・転送します。各 stand-in kernel は固定の 1024×256 work-item を使い、各 work-item が stride 262144 で配列を走査して加算します。計算結果は `a == 12345.678f` の場合だけ sink に書かれます。0 ならポインタは null のままで、kernel 呼び出しは即時 return します。

DIRECT の各 round（warm-up 10 回を含む）の前、および GRAPH が有効な場合の各 graph round（同じく warm-up を含む）の前に投入されます。投入後、任意の `DF2B_GAPMS` 待機処理に先立って queue を wait し、続く round の計測開始はさらにその後です。そのため stand-in kernel の実行時間は round の `wall ms/round` 計測に含めず、各 round に先行する別の帯域負荷として働きます。結果として出力される `config:` 行には stand-in の設定値が MB として表示されます。

容量チェックや clamp はありません。device allocation が失敗した場合、共通 allocation helper が stderr に `out of device memory (%zu bytes)` を出して終了コード 2 で終了します。大きすぎる値では、この device allocation より先にホスト vector の確保が問題になる可能性がありますが、その失敗をこのコードが独自に処理する経路は確認できません。

## 根拠

- `sycl/src/kernels/dflash2_bench.cpp:56` — `envi` は未設定または空文字に default を返し、それ以外を `std::atoi` に渡す。
- `sycl/src/kernels/dflash2_bench.cpp:62,77-83` — device allocation 失敗時の stderr と終了コード 2、float 配列の host/device 作成。
- `sycl/src/kernels/dflash2_bench.cpp:486-508` — benchmark 入口での一度だけの読み取り、MB から float 要素数への換算、kernel と config 出力。
- `sycl/src/kernels/dflash2_bench.cpp:499-505,525-539,546-568` — stand-in kernel の処理、DIRECT / GRAPH の各 round 前への投入と待機順序。
- `sycl/src/kernels/dflash2_bench.cpp:894-901` — CLI mode による `run_bench()` 選択。
- `sycl/CMakeLists.txt:289-290,437-438` — parity build option（既定 ON）と `dflash2_bench` ターゲット。
