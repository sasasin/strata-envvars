# `SPIN_MAX`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`SPIN_MAX` は、同梱ビルドスクリプト `sycl/tools/build.sh` が SYCL エンジンを構成するときに読むシェル環境変数です。値は CMake キャッシュ変数 `STRATA_SYCL_SPIN_MAX` に渡され、指定されると SYCL device kernel の host flag spin 上限をビルド時に固定します。Strata 実行ファイルが直接読む実行時環境変数は別名の `STRATA_SPIN_MAX` です。

## 値と判定

| `SPIN_MAX` の状態 | ビルドスクリプトの処理 | 結果 |
|---|---|---|
| 未設定または空文字 | `${SPIN_MAX:-}` が空に展開される | `STRATA_SYCL_SPIN_MAX` を空で CMake に渡し、CMake は固定値の compile definition を追加しない。実行時にデバイス別の既定値を選ぶ |
| 非空文字列 | 文字列をそのまま `-DSTRATA_SYCL_SPIN_MAX="..."` に渡す | CMake は値が truthy の場合に限り `STRATA_SYCL_SPIN_MAX=<値>u` を compile definition として追加する |

ビルドスクリプトや CMake に数値としての検証・clamp・警告はありません。したがって、この変数には C++ の整数 compile definition として使える正の値を指定する必要があります。非数値文字列や不適切な値を指定した場合の成否・診断はコンパイラ側に委ねられています。`sycl/tools/build.sh:40-41`、`sycl/CMakeLists.txt:43-45`。

## 有効になる条件

- SYCL ビルドを `sycl/tools/build.sh` で構成し、ビルドディレクトリに `build.ninja` がまだない場合、現在の `SPIN_MAX` が初回 CMake 構成へ渡されます。
- すでに `build.ninja` がある場合、スクリプトは通常の実行では CMake を再構成しません。既存の CMake cache に保存された `STRATA_SYCL_SPIN_MAX` が使われ、今回の `SPIN_MAX` は反映されません。スクリプト内で明示的に再構成するのは `I8_ESIMD` の場合だけです（`sycl/tools/build.sh:40-43`）。
- CMake の `STRATA_SYCL_SPIN_MAX` が空なら、`SPIN_MAX` による固定値はビルドへ入りません。実行時に `STRATA_SPIN_MAX` が正の数として読めればそれが優先されます。そうでなければ、ビルド macro が定義されている場合は macro 値が使われます（`sycl/CMakeLists.txt:43-45`、`sycl/include/strata/sycl_doorbell.hpp:142-145`）。
- `STRATA_SYCL_SPIN_MAX` の macro も実行時 override もない場合、xe driver は 20,000、driver 名が空で Battlemage の場合は通常 20,000（`spin_drafts_need_long_bound(true)` 済みなら 2,000,000）、その他は 2,000,000 を使います（`sycl/include/strata/sycl_doorbell.hpp:146-149`）。

## 実行時の詳細

`sycl/tools/build.sh` は未設定・空文字を同じ空値として CMake に渡します。非空値は `STRATA_SYCL_SPIN_MAX` の cache string となり、CMake が空でない場合にだけ `<値>u` を定義します。CMake の説明文字列にも、空なら実行時にデバイスごとに選択するとあります（`sycl/tools/build.sh:40-43`、`sycl/CMakeLists.txt:40-45`）。

実行ファイル内の `spin_max(queue)` は各 `sycl::device` について最初の呼び出しで上限を決め、device ごとの `unordered_map` に cache します。実行中に環境を変更しても、すでに決定済みの device の上限は再評価されません。`STRATA_SPIN_MAX` は `std::atol` で変換し、結果が `> 0` の場合だけ採用します。従って未設定、空文字、先頭が数値でない文字列、ゼロ、負値では実行時 override にならず、ビルド macro またはデバイス別既定値へ進みます。数値の後ろに文字が続く場合も `atol` が変換する数値接頭部が正なら採用されます。採用値は `uint32_t` に変換されます（`sycl/include/strata/sycl_doorbell.hpp:134-152`）。

device 上で使う複数の kernel launcher は `spin_max(queue)` の結果を `spin_max` 引数として渡します（例: `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2488,2547`、`sycl/src/kernels/cuda/elementwise.dp.cpp:400`）。この値は spin の反復上限です。ここでの `SPIN_MAX` / `STRATA_SPIN_MAX` の説明は Strata がビルド値を転送し、実行時に上限を選択・渡す処理に限ります。

ビルド中の失敗は `cmake` / `cmake --build` の出力を build log に記録し、スクリプトは `BUILD EXIT <status>` を表示します（`sycl/tools/build.sh:44-46`）。`SPIN_MAX` 固有の警告や値の fallback ログは実装にありません。

## 根拠

- `sycl/tools/build.sh:40-43` — 初回 CMake 構成への `SPIN_MAX` の転送と、既存 build directory の扱い。
- `sycl/CMakeLists.txt:40-45` — `STRATA_SYCL_SPIN_MAX` の空時の意味と compile definition。
- `sycl/include/strata/sycl_doorbell.hpp:114-152` — device spin の目的、実行時値の変換・優先順位、デバイス別既定値、device 単位の cache。
- `sycl/src/kernels/cuda/verify_kernels.dp.cpp:2488,2547`、`sycl/src/kernels/cuda/elementwise.dp.cpp:400` — 上限を launcher から渡す例。
- `docs/INTEL.md:85-90,149-151` — SYCL build script の `SPIN_MAX` 入力と bounded spin に関する利用者向け記載。
