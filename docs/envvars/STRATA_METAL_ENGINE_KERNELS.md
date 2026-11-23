# `STRATA_METAL_ENGINE_KERNELS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Metal engine が実行時にコンパイルする engine 固有 MSL ソース（`ple.metal`、`mtp.metal`、`mtp_chain.metal`、`dflash2.metal`）のディレクトリを指定する。通常は実行ファイル横のパッケージ資材、またはビルド時に埋め込まれた `engine/metal/src/engine/msl` を使い、この変数が設定されるとその探索より優先して指定パスを使う。コアの `metal/kernels/*.metal` の場所を指定する変数ではない（`engine/metal/src/engine/window.cpp:67, 797, 2516, 2604`、`engine/metal/src/engine/dflash2.inc:31`、`engine/metal/src/engine/msl_libs.h:25-38`、`engine/metal/src/mtl_rt.mm:148-150, 190-192`）。

## 値と判定

`strata_metal::resource()` は `env != nullptr` のとき `std::getenv(env)` を呼び、返り値が null でなければその文字列をそのまま返す。文字列の解析、空文字判定、存在確認、正規化はしない（`engine/metal/src/resource_path.h:44-54`）。

| 条件 | unset | 設定時に使われる値 | パスが使えない場合 |
|---|---|---|---|
| Metal engine build | 実行ファイル横の `metal/engine-msl` が存在すればそれ、なければ CMake の `STRATA_METAL_ENGINE_KERNELS_DEFAULT`（ソースツリーの `engine/metal/src/engine/msl`） | 空でない値は内容を問わず採用。`/opt/strata/msl` のような絶対パスが直接使われる | 指定値へのフォールバックはせず、MSL ファイル読み込みで失敗する |

空文字も「設定あり」として採用され、engine MSL のファイル名は `/ple.metal` などになる。`0`、`1`、`true`、`false`、`0anything` も真偽値ではなく各文字列をディレクトリ名として扱う。相対パスは絶対パスと同様には直接開かれず、`Context::compile()` がコア kernel ディレクトリ `kernel_dir` の下に連結するため、たとえば `custom` は `kernel_dir/custom/ple.metal` として解決される。先頭・末尾の空白や大文字小文字にも特別扱いはない（`engine/metal/src/resource_path.h:44-53`、`engine/metal/src/mtl_rt.mm:190-192`）。

## 有効になる条件

- `engine/metal/CMakeLists.txt` は macOS 以外では Metal build を拒否し、`METAL_CPP_DIR` に Metal C++ headers がなければ device runtime と engine を組み立てず、engine 自体も `STRATA_METAL_ENGINE` が有効なときに組み立てられる（`engine/metal/CMakeLists.txt:18-20, 82-87, 103-108`）。この環境変数を読むのは `engine_msl_dir()` を含む Metal engine 経路である。
- `Window::init()` は decode window の初期化時に PLE library をコンパイルするため、Metal engine の window を初期化する経路では MTP/DFlash2 を使わなくても engine MSL ディレクトリが参照される（`engine/metal/src/engine/window.cpp:714-737, 791-798`）。
- MTP model を読み込む経路では `mtp.metal` が追加で使われる。`mtp_chain.metal` は MTP 読み込み後、`STRATA_METAL_MTP_CHAIN=0` でなく、かつ token embedding の型が許可リストにある場合に使われる（`engine/metal/src/engine/window.cpp:2516-2517, 2595-2605`）。
- DFlash2 の tapped layer を有効にする経路では `dflash2.metal` が使われる（`engine/metal/src/engine/dflash2.inc:19-38, 995-1009`）。
- CLI 引数や別環境変数によるパス上書きはこの選択処理にはない。`STRATA_METAL_KERNELS` は別の core kernel directory 用であり、engine MSL path には合成されない（`engine/metal/src/engine/window.cpp:67`、`engine/metal/src/resource_path.h:44-54`、`engine/metal/src/mtl_rt.mm:148-150`）。

## 実行時の詳細

`engine_msl_dir()` はキャッシュせず、呼ばれるたびに `resource()` が環境を読み直す。最初は window 初期化の PLE compile で評価され、MTP と DFlash2 は各機能の初期化時にも同じ helper を通る。したがって、後続の呼び出し前にプロセス環境が変更されていれば後続 library のパスに反映されるが、すでに読み込んだファイルやコンパイル済み library は切り替わらない（`engine/metal/src/engine/window.cpp:67, 791-798, 2516-2517, 2604-2605`、`engine/metal/src/engine/dflash2.inc:31-32`）。Strata ソース内にこの名前への `setenv` / `putenv` / `unsetenv` はない。

選ばれたディレクトリを `lib_ple` / `lib_mtp` / `lib_mtp_chain` / `lib_dflash2` が各 `.metal` ファイル名に連結する。`Context::compile()` は `/` 始まりのファイル名をそのまま開き、それ以外は core kernel directory を前置する。`read_file()` が開けないと stderr に `mtl: cannot read <path>` を出して終了コード 2 で終了する。ファイルが読めても Metal source compile 自体が失敗した場合は `mtl: compile failed (<device>, macOS <version>; <file>):` とコンパイラの説明を stderr に出し、終了コード 3 で終了する（`engine/metal/src/engine/msl_libs.h:33-38`、`engine/metal/src/mtl_rt.mm:26-35, 170-192`）。

## ログと測定値

変数の読み取りや有効化を知らせる専用ログはない。誤った場所で MSL ファイルを開けない場合の `mtl: cannot read <path>`、または Metal source compile 失敗時の `mtl: compile failed (...)` が観測可能な結果となる（`engine/metal/src/mtl_rt.mm:26-35, 170-179`）。この変数についての測定値は、調査対象ソースおよび `docs/DETAILS.md` では確認できなかった。

## 根拠

- `engine/metal/src/resource_path.h:44-54` — 環境値の有無判定、実行ファイル横の資材確認、ビルド時既定値への順序。
- `engine/metal/src/engine/window.cpp:67, 714-737, 791-798, 2516-2517, 2595-2605` — helper、window 初期化、MTP と MTP chain の利用箇所。
- `engine/metal/src/engine/dflash2.inc:19-38, 995-1009` — DFlash2 kernel のコンパイルと有効化経路。
- `engine/metal/src/engine/msl_libs.h:33-38` — engine directory から参照する MSL ファイル。
- `engine/metal/src/mtl_rt.mm:26-35, 148-150, 170-192` — ファイル解決、読み取り失敗、compile 失敗のログと終了経路。
- `engine/metal/CMakeLists.txt:18-20, 82-87, 103-108, 168-174` — macOS / headers / engine build 条件と既定パス。
