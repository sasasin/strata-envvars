# `I8_ESIMD`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`I8_ESIMD` は SYCL エンジンのビルド時設定です。`sycl/tools/build.sh` が値を CMake 変数 `STRATA_SYCL_I8_ESIMD` に渡し、fused int8 ESIMD expert kernel を実装するバイナリを含めるか決めます。Strata のエンジン起動時にこの名前を読む箇所はなく、実行中に変更しても既にビルドされたエンジンには反映されません（`sycl/tools/build.sh:40-44`, `sycl/CMakeLists.txt:58-71`）。

## 値と判定

シェルの変数展開は unset と空文字を同じく「値なし」として扱う箇所があります。CMake が受け付ける値は大文字の `AUTO`、`ON`、`OFF` のみで、空文字や別の綴りは有効値ではありません（`sycl/tools/build.sh:40-43`, `sycl/CMakeLists.txt:58-68`）。

| 入力・状態 | ビルドスクリプトが渡す値／扱い |
| --- | --- |
| unset または空文字、新しい build directory | `AUTO` を CMake に渡す |
| unset または空文字、既存 `build.ninja` がある | 再設定を行わず、CMake cache の値を維持 |
| 非空文字、既存 `build.ninja` がある | その文字列を `-DSTRATA_SYCL_I8_ESIMD=...` で再設定 |
| `AUTO` | JIT ビルドと `bmg` / `lnl` AOT ではカーネルを含める。それ以外の AOT では含めない |
| `ON` | AOT ターゲットに関係なくカーネルを含める |
| `OFF` | カーネルを含めない |
| その他の非空文字列（例: `off`, `1`） | CMake の `FATAL_ERROR`。`AUTO` への自動変換はしない |

CMake の `AUTO` 判定における `bmg` / `lnl` は `STRATA_SYCL_AOT` の先頭に一致するターゲット名です。`OFF` の場合、または `AUTO` で対象外 AOT の場合、`STRATA_I8_NO_ESIMD=1` を定義してスタブ実装に切り替えます（`sycl/CMakeLists.txt:48-71`, `sycl/src/prefill/esimd_moe.dp.cpp:41-57`）。

## 有効になる条件

この設定が作用するのは `sycl/tools/build.sh` を使って行う SYCL CMake configure/build です。CUDA/HIP のビルドや、既に存在する実行ファイルの起動設定としては参照されません（`sycl/tools/build.sh:1-6,38-44`）。

コンパイルされたカーネルがあっても、実行時に使えるとは限りません。SYCL device が `ext_intel_esimd` を持ち、int8×int8 の matrix combination に `nsize=16` と `ksize=32` があることが `available()` の条件です。さらに `STRATA_I8_FORCE` の先頭文字が `0` なら利用不可とされ、その結果は device ごとに初回判定後 cache されます（`sycl/src/prefill/esimd_moe.dp.cpp:836-854`）。`STRATA_I8_NO_ESIMD` ビルドでは `available()` が常に false です（同 `:41-52`）。

実際の prompt expert 処理では、これらに加えて native expert layout、対応する gate/up と down の形式、`n_ff=640` / `n_embd=2560`、MMQ 経路でないことなどを満たす必要があります。`STRATA_PREFILL_MMQ`（空または未設定なら `STRATA_PF_I8` が代替）が int8 経路の選択に関わりますが、ESIMD カーネルがビルドされていない場合は利用可能性条件を通りません（`sycl/src/prefill/prefill.cpp:284-295,4343-4352`）。

## 実行時の詳細

ビルドスクリプトは `AOT` が `bmg` / `lnl` で始まり、`I8_ESIMD` が厳密に `OFF` ではなく、`ALLOW_BAD_OCLOC` が厳密に `1` でもない場合、`ocloc --version` の最初の数値バージョンを確認します。バージョンが `26.22.38646` またはその接尾辞付きなら、コンパイル前に stderr へ既知の問題と対処を表示し、終了コード 2 で停止します。`I8_ESIMD=OFF` はこの事前停止を回避し、`ALLOW_BAD_OCLOC=1` もビルド続行を許します。unset/空文字、`off`、`0` はこの判定では `OFF` と見なされません。該当する ocloc が見つからない場合、この事前停止は起きません（`sycl/tools/build.sh:15-35`）。

新しい build directory の初回 configure では unset/空文字は `AUTO` に展開されます。`build.ninja` が既にある場合は、非空の `I8_ESIMD` だけが CMake cache を更新し、unset/空文字では既存設定を使います。configure のあと `cmake --build` を実行し、`BUILD EXIT <code>` を出力します。スクリプトは `set -e` を有効にしていないため、configure エラーの後も後続処理へ進むことがあります。既存 cache に無効値を渡したときは再 configure の診断が抑制され、その後の build 結果だけでは設定更新の成否が分かりにくい場合があります（`sycl/tools/build.sh:7,38-50`; CMake の値検証は `sycl/CMakeLists.txt:60-61`）。

無効化されたビルドでは、prompt の該当 expert は fused int8 経路ではなく既存の FP16 / XMX 経路に進みます。実行時の適用条件が不足する場合や int8 呼び出しが失敗した場合も FP16 chain に fallback します。prompt 処理は `STRATA_PREFILL_MMQ` またはその代替 `STRATA_PF_I8` に非空値があるとき、対象 format ごとの int8 経路選択を stderr に `strata: layer ... -> int8 path yes/no` と表示します。`I8_ESIMD` 自体を表示する実行時ログは確認できません（`sycl/src/prefill/prefill.cpp:4353-4358,4419-4432`）。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:677`。
- シェルでの参照、ocloc guard、CMake への引き渡し: `sycl/tools/build.sh:5,15-50`。
- CMake cache の既定値、値の検証、AOT 条件、compile definition: `sycl/CMakeLists.txt:53-71`。
- ESIMD を外した場合の stub 実装: `sycl/src/prefill/esimd_moe.dp.cpp:41-57`。
- 実行時の device 判定と cache: `sycl/src/prefill/esimd_moe.dp.cpp:836-854`。
- prompt 経路の追加条件、ログ、FP16 fallback: `sycl/src/prefill/prefill.cpp:284-295,4343-4358,4419-4432`。
