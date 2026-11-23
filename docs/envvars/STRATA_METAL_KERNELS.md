# `STRATA_METAL_KERNELS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

Metal runtime の `mtl::Context` が相対パスで指定された Metal kernel source (`.metal`) を探すディレクトリを指定する。`Context::compile_try()` はファイル名が `/` で始まらない場合に `kernel_dir + "/" + ファイル名` を読み、絶対パスならそのパスをそのまま使う（`engine/metal/src/mtl_rt.mm:183-193`）。`kernel_dir` は `Context` の構築時にこの環境変数を含む優先順で選ばれる（`engine/metal/src/mtl_rt.mm:139-151`）。

Strata Metal engine は `lib_core()` などが `quant.metal`、`units.metal`、`moe.metal` といった相対ファイル名を渡して実行時コンパイルするため、この変数はそれらの読み込み場所を変える。モデルや kernel の選択方法自体を変える設定ではない（`engine/metal/src/engine/msl_libs.h:25-45`、`engine/metal/src/engine/window.cpp:791-797`）。

## 値と判定

`strata_metal::resource()` は変数名が渡された場合 `std::getenv()` の戻り値が null でないかだけを判定し、null でなければ文字列をそのまま返す。値の parse、空文字の除外、パスの存在確認・正規化はしない（`engine/metal/src/resource_path.h:43-54`）。

| 条件（ビルドなど） | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Metal runtime (`mtl_rt`) | 実行ファイル隣の `metal/kernels` が存在すればそのパス、そうでなければビルド時の `STRATA_METAL_KERNELS_DEFAULT` | 空でない任意の文字列。例: `/opt/strata/kernels`、`relative/kernels`。文字列をそのまま `kernel_dir` にする | 「値として無効」と判定される文字列はない。`""` も有効な設定値として採用され、fallback しない |

この設定は文字列全体の比較や数値変換を行わないため、大文字小文字、空白、`0` / `1` などに特別な意味はない。たとえば `1` は真偽値ではなくディレクトリ名 `1`、`0anything` もそのままのパスとして扱われる（`engine/metal/src/resource_path.h:44-53`）。

空文字は「未設定」扱いにならず、`kernel_dir` を空にする。相対ファイル名はその後 `"/" + ファイル名` となるため、たとえば `quant.metal` は `/quant.metal` として開かれ、開けなければ `read_file()` の失敗経路に入る（`engine/metal/src/resource_path.h:44-47`、`engine/metal/src/mtl_rt.mm:26-35,190-193`）。

## 有効になる条件

- Metal runtime を含む macOS 向けビルド・実行経路であること。`engine/metal/CMakeLists.txt` は Apple 以外では構成を失敗させ、`mtl_rt` をビルドする（`engine/metal/CMakeLists.txt:13-20,34-41`）。
- 呼び出し側が `Context::compile()` / `compile_try()` に相対ファイル名を渡すこと。絶対ファイル名では `kernel_dir` を使わない（`engine/metal/src/mtl_rt.mm:190-193`）。
- パス文字列が実在するディレクトリを指すかは設定時に検証されない。相対パスは `kernel_dir` に連結され、結果のファイル読み込み時に初めて失敗し得る（`engine/metal/src/resource_path.h:44-53`、`engine/metal/src/mtl_rt.mm:26-35,190-193`）。
- 実行ファイル隣の `metal/kernels` が存在する場合、それは未設定時の fallback にだけ使われる。変数が設定されていれば、隣接ディレクトリやビルド時既定値より優先される（`engine/metal/src/resource_path.h:43-54`）。
- `--kernels` 等で呼び出し元が明示的に絶対パスを渡した場合、そのファイル指定は環境変数のディレクトリを通らない。HY4 runner の `--kernels` / `STRATA_HY4_KERNELS` は別設定であり、この環境変数とは別に kernel file path を決める（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1512,1661-1674,1708-1720`）。

## 実行時の詳細

`Context::Context()` の実行時に一度だけ選択し、インスタンスの `kernel_dir` に保存する。優先順位は (1) `STRATA_METAL_KERNELS` が設定済みならその値、(2) `<実行ファイルのディレクトリ>/metal/kernels` が存在すればそのパス、(3) ビルド時定数 `STRATA_METAL_KERNELS_DEFAULT`。実行ファイル位置は `_NSGetExecutablePath()` と `realpath()` で得て、隣接パスの存在判定は `stat()` 成功で行う（`engine/metal/src/resource_path.h:27-41,43-54`、`engine/metal/src/mtl_rt.mm:139-151`）。Metal CMake build では既定値はソース checkout の `engine/metal/kernels`（`engine/metal/CMakeLists.txt:38-41,168-174`）。

この `kernel_dir` は相対 kernel path を `kernel_dir + "/" + file` に変換してから `read_file()` に渡す。ファイルを開けない場合は stderr に `mtl: cannot read <path>` を出してプロセスを終了コード 2 で終了する（`engine/metal/src/mtl_rt.mm:26-35,190-193`）。読み込んだ source の Metal compile が失敗した場合、`compile_try()` は `-1` を返し、`compile()` は `mtl: compile failed (<device>, macOS <version>; <file>):` と compiler error を出して終了コード 3 で終了する（`engine/metal/src/mtl_rt.mm:170-179,219-226`）。

値は `Context` ごとに constructor で読み直す。構築後にプロセス内の環境を変更しても、すでにあるインスタンスの `kernel_dir` は変わらない。CLI option による共通の上書き処理は `mtl::Context` にはなく、呼び出し側が file path を絶対パスとして渡す場合はその指定が使われる（`engine/metal/src/mtl_rt.h:145-150`、`engine/metal/src/mtl_rt.mm:139-151,190-193`）。

## ログと測定値

この変数の値選択やfallback自体について、Strata はログや警告を出さない（`engine/metal/src/resource_path.h:43-54`）。不正なパスで相対 kernel source を開けない場合のログ・終了は「実行時の詳細」に記したとおり。性能測定値は該当するソース資料にない。

## 根拠

- `engine/metal/src/resource_path.h:27-54` — 実行ファイル位置、隣接 `metal/kernels` の存在確認、環境変数・fallback の優先順。
- `engine/metal/src/mtl_rt.mm:26-35,139-151,170-193,219-226` — Context 構築、パス解決、ファイル読み込み、compile の失敗経路。
- `engine/metal/src/engine/msl_libs.h:25-45`、`engine/metal/src/engine/window.cpp:791-797` — Metal engine が相対 kernel 名を使ってコンパイルする呼び出し。
- `engine/metal/CMakeLists.txt:13-20,34-41,168-177` — macOS build 条件と `STRATA_METAL_KERNELS_DEFAULT` の定義。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1512,1661-1674,1708-1720` — HY4 固有の別 kernel path 設定と絶対パス化。
