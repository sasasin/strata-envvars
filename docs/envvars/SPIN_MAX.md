# `SPIN_MAX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`SPIN_MAX` は `engine/sycl/tools/build.sh` が読む SYCL エンジンの**ビルド時**環境変数で、値を CMake キャッシュ変数 `STRATA_SYCL_SPIN_MAX` に渡す。CMake は空でない値をコンパイル定義 `STRATA_SYCL_SPIN_MAX=<値>u` にし、SYCL のホスト・デバイス間 doorbell wait に渡す spin read 上限を全デバイスで固定する。エンジン実行時に `SPIN_MAX` を読む箇所はなく、実行時上書き用の別の名前は `STRATA_SPIN_MAX` である（`engine/sycl/tools/build.sh:38-44`、`engine/sycl/CMakeLists.txt:59-70`、`engine/sycl/include/strata/sycl_doorbell.hpp:153-172`）。

## 値と判定

`build.sh` は `${SPIN_MAX:-}` をそのまま `-DSTRATA_SYCL_SPIN_MAX=...` に渡し、値を数値変換しない。CMake の `if(STRATA_SYCL_SPIN_MAX)` が真の場合に末尾 `u` を付けたコンパイル定義を生成する。`0`、`OFF`、`NO`、`FALSE`、`N`、`IGNORE`、`NOTFOUND`（および `-NOTFOUND` で終わる値）は偽として扱われ、それ以外の非空値は真として扱われる。真偽判定は大文字小文字を区別しない（`engine/sycl/tools/build.sh:40-41`、`engine/sycl/CMakeLists.txt:62,69-70`）。

| `build.sh` 実行時の値 | CMake / コンパイル定義 | 結果 |
|---|---|---|
| 未設定または空文字 | 空。定義なし | ビルド時固定値を使わず、SYCL 実行時のデバイス別選択へ進む。 |
| `0`、`false`、`OFF` など CMake の偽定数 | CMake の条件が偽。定義なし | 同じくデバイス別選択へ進む。偽定数の判定は大文字小文字を区別しない。 |
| `1`、`2000000`、`true` など | 値をそのままキャッシュし、`STRATA_SYCL_SPIN_MAX=<値>u` を定義 | CMake はこれらを真とするが、コンパイル定義が C++ 整数定数でなければ build は通らない。 |
| `0anything`、`abc` など | 値をそのままコンパイル定義へ渡す | `SPIN_MAX` を数値として検証・変換しない。`0anythingu` / `abcu` のような定義を Strata が拒否・fallback する処理はなく、コンパイル可否は値の構文による。 |

`build.sh` の build directory に `build.ninja` が既にあると、同スクリプトは CMake の初期構成を飛ばし、`SPIN_MAX` を再設定しない（`I8_ESIMD` だけは別途再設定する）。したがって、既存 build directory で環境変数だけを変更しても、その値は CMake に渡らず、保存済み cache の値が使われる（`engine/sycl/tools/build.sh:38-44`）。

実行時の別変数 `STRATA_SPIN_MAX` は `std::atol` で変換され、正の数ならビルド時固定値より優先する。未設定・空文字・数値変換結果が 0 以下の場合は override されず、ビルド時固定値（定義されていれば）またはデバイス別値が選ばれる。これは `SPIN_MAX` 自身の実行時判定ではない（`engine/sycl/include/strata/sycl_doorbell.hpp:153-162,169-172`）。

## 有効になる条件

- `engine/sycl/tools/build.sh` 経由で SYCL build を構成するときに使われる。通常の実行時環境に `SPIN_MAX` を設定するだけでは、既にビルドされたエンジンの値は変わらない（`engine/sycl/tools/build.sh:38-44`）。
- 初回構成時に値が空でなければ CMake cache に保存される。既存の `build.ninja` がある build directory では、スクリプトは値を渡し直さない（同上）。
- CMake が `STRATA_SYCL_SPIN_MAX` を compile definition として生成できる SYCL build が対象。CUDA/HIP や別の build 経路について、この変数の参照は確認できない（`engine/sycl/CMakeLists.txt:59-70`）。
- 固定値を埋め込んだ後も、実行時に `STRATA_SPIN_MAX` が正の数へ変換されるとその値が優先される（`engine/sycl/include/strata/sycl_doorbell.hpp:153-162`）。
- 固定値を使わない場合の既定値は SYCL 実行時に選ばれる。driver が `xe` の場合は host wait の有無で 20,000 / 1,000,000 reads、driver 名がなく Battlemage の場合は `--spec` の長ドラフト状態で 20,000 / 2,000,000 reads、それ以外は 2,000,000 reads（`engine/sycl/include/strata/sycl_doorbell.hpp:153-162`）。

## 実行時の詳細

`SPIN_MAX` 自体は build script の起動時に shell 展開され、CMake の初期構成時にキャッシュされる。実行時にはコンパイル定義が `spin_bound_for` の分岐に入り、正の `STRATA_SPIN_MAX` override がなければ全デバイスに同じ固定 bound を返す。固定定義がない場合は driver、Battlemage 判定、host wait、long-drafts flag から bound を選ぶ（`engine/sycl/tools/build.sh:40-44`、`engine/sycl/CMakeLists.txt:62-70`、`engine/sycl/include/strata/sycl_doorbell.hpp:153-172`）。

各 `spin_max(queue)` 呼び出しは実行時の `STRATA_SPIN_MAX` を読み直して bound を計算する。デバイス別 map は最後に使った値をログ抑制用に記録するもので、bound の値を固定する cache ではない。選ばれた bound は SYCL の elementwise / verify kernel launchers に渡される（`engine/sycl/include/strata/sycl_doorbell.hpp:164-179`、`engine/sycl/src/kernels/cuda/elementwise.dp.cpp:409`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2833,2895`）。

## ログと測定値

通常、デバイスの初回 bound 選択時はログを出さない。`STRATA_SPIN_LOG` が設定されている場合は初回にも、また同じデバイスの bound が変わった場合にも stderr に `strata: GPU wait bound %u reads on a device%s` を出す（`engine/sycl/include/strata/sycl_doorbell.hpp:173-177`）。`SPIN_MAX` 固有の警告やエラー文言は確認できない。CMake / コンパイラの失敗は build script の一般的な build 出力経路を通る（`engine/sycl/tools/build.sh:40-50`）。

## 根拠

- `engine/sycl/tools/build.sh:38-44` — `SPIN_MAX` の展開、CMake 初期構成の条件、既存 build directory での再設定有無。
- `engine/sycl/CMakeLists.txt:59-70` — 固定 bound の CMake cache と compile definition。
- `engine/sycl/include/strata/sycl_doorbell.hpp:115-162` — bound の役割、実行時 override とデバイス別条件。
- `engine/sycl/include/strata/sycl_doorbell.hpp:164-179` — 実行時読み取り、ログ用 map、stderr 文言。
- `engine/sycl/src/kernels/cuda/elementwise.dp.cpp:409`、`engine/sycl/src/kernels/cuda/verify_kernels.dp.cpp:2833,2895` — bound を kernel launcher から取得。
