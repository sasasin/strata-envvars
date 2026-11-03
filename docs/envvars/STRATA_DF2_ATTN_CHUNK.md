# `STRATA_DF2_ATTN_CHUNK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

SYCL 版 DFlash2 drafter の attention kernel で、work-group あたりに処理する key 数を選びます。環境変数の変換結果が整数 `128` のときだけ 128-key chunk を選び、それ以外はビルド既定の 64-key chunk になります。`df2_attention()` は DFlash2 の各 layer の attention 計算から呼ばれます（`sycl/src/core/dflash2.cpp:394-400`）。

これは CUDA/HIP 側の同名設定ではなく、SYCL 用に移植された `dflash2.dp.cpp` の実装です。CMake は `dflash2.cu` に対して移植済み `.dp.cpp` があればそのファイルを選ぶ仕組みで、SYCL kernel 一覧に DFlash2 を含めています（`sycl/CMakeLists.txt:115-125,245-257`）。DFlash2 自体を使うには `--draft dflash2` が必要で、pack・draft vocabulary・`--spec 2` 以上などの条件を満たす必要があります（`sycl/src/program/generate.cpp:4370-4375`）。

## 値と判定

環境値は `std::atoi` で整数に変換され、変換結果が厳密に `128` と等しい場合だけ 128 を選びます。それ以外は 64 です。文字列全体の検査、範囲チェック、無効値の警告はありません。

| 環境値 | `atoi` の結果 | chunk 幅 |
|---|---:|---:|
| 未設定 | 0（コード上の代替値） | 64 |
| 空文字 | 0 | 64 |
| `128` | 128 | 128 |
| `+128`、` 128`、`128suffix` | 128 | 128 |
| `64`、`0`、負数、数値以外 | 128 以外（数値以外は 0） | 64 |

`atoi` の整数変換範囲を超える入力について、Strata は独自の検査やエラー処理をしていません。既定値 64 は `DF2_ATTN_CHUNK_AUTO` がソース内で定義されている値です（`sycl/src/kernels/cuda/dflash2.dp.cpp:31-33,196-198`）。

## 有効になる条件

- SYCL backend の DFlash2 kernel を含む build でのみ、この読み取り箇所が使われます。通常の CUDA/HIP 実装にこの環境変数名の読み取りはありません（候補名の全参照を検索した結果は `sycl/src/kernels/cuda/dflash2.dp.cpp:196` の一箇所）。
- 実行時には DFlash2 drafter が選択され、初期化条件を満たして `df2_attention()` まで到達する必要があります。CLI 側では pack、draft vocabulary、`--spec 2` 以上が必要で、複数 GPU、batch、`--pipeline-windows` との組み合わせは拒否されます（`sycl/src/program/generate.cpp:4370-4375,4423-4431`）。
- bench-only API `df2_attention_chunk(int)` が 0 以外を設定している場合は、その値が環境変数より優先します。同 API は `g_attn_chunk` に値を代入し、`df2_attention()` は `g_attn_chunk != 0` を先に判定します（`sycl/src/kernels/cuda/dflash2.dp.cpp:197,735-737`）。通常の DFlash2 engine 呼び出しではこの setter を使わず、SYCL benchmark が使います（`sycl/src/kernels/dflash2_bench.cpp:450-451,683-687`）。
- 別の環境変数 `STRATA_DF2_ATTN` は attention kernel variant を選びますが、chunk 幅の選択条件には含まれず、variant 2 とそれ以外の両 kernel 分岐に `CK` が渡されます（`sycl/src/kernels/cuda/dflash2.dp.cpp:194-204,336-349`）。

## 実行時の詳細

環境値は `df2_attention()` 内の関数ローカル `static const int` 初期化で読み取られます。したがってそのプロセスで最初にこの関数へ入ったときに一度だけ `getenv` / `atoi` が評価され、その後に環境を書き換えても再読込されません（`sycl/src/kernels/cuda/dflash2.dp.cpp:191-198`）。CLI 引数や設定ファイルからこの値を上書きする経路は確認できません。bench-only setter だけは前述のとおり優先します。

`CK` は work-group が走査する key の区間幅に使われ、128 のとき `kDf2MaxChunks`（17）、それ以外は `kDf2PartChunks`（33）個の partial chunk を確保・結合する想定です。kernel は `k_begin = chunk * CK` から `k_end = min(k_begin + CK, nkeys)` までの key を処理し、後段は `nch` 個の partial を結合します（`sycl/src/kernels/cuda/dflash2.dp.cpp:197-198,212-236,473-485`; 定数の説明は `include/strata/kernels/dflash2.hpp:18-20`）。

Strata はこの環境変数についてログ、警告、専用の失敗・終了経路を出しません。無効な文字列もエラーにはせず、`atoi` の結果に応じて既定の 64-key 経路へ進みます。`docs/DETAILS.md:1002-1006` に名前は候補として列挙されていますが、chunk の挙動や性能測定値の説明はありません。この文書ではコードで確認した制御だけを記載しています。

## 根拠

- 全参照と値の選択: `sycl/src/kernels/cuda/dflash2.dp.cpp:191-198`。
- 128/64 chunk の kernel 処理・partial 結合: `sycl/src/kernels/cuda/dflash2.dp.cpp:204-236,341-370,473-489`。
- DFlash2 engine から attention への呼び出し: `sycl/src/core/dflash2.cpp:394-400`。
- build 時の SYCL 移植 source 解決と DFlash2 kernel 登録: `sycl/CMakeLists.txt:115-125,245-257`。
- CLI の DFlash2 起動条件: `sycl/src/program/generate.cpp:4370-4375,4423-4431`。
- bench-only chunk setter: `include/strata/kernels/dflash2.hpp:60-63`, `sycl/src/kernels/cuda/dflash2.dp.cpp:735-737`, `sycl/src/kernels/dflash2_bench.cpp:450-451,683-687`。
