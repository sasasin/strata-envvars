# `STRATA_METAL_KERNELS`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。対象は Strata 所有の Metal ソース。外部ライブラリや Metal ドライバーの動作は含めない。

## 役割

Metal の実行時コンパイルで、相対パスで指定された `.metal` カーネルソースを探すディレクトリを指定する。Metal の standalone kernel programs（parity/bench 等）と、Metal engine の decode / prompt 経路で使われる。単なる診断フックではなく、engine の共通カーネルソースの読み込み先にも影響する。

## 値と判定

| 値 | 扱い |
|---|---|
| 未設定 | ビルド時の `STRATA_METAL_KERNELS_DEFAULT` を使う。CMake では通常 `${CMAKE_CURRENT_SOURCE_DIR}/kernels`（`metal/kernels`）に定義される。 |
| 設定あり（空文字を含む） | 値をそのまま `kernel_dir` にコピーする。空文字を既定値として扱う特別処理はない。 |
| 相対ファイル名 | `kernel_dir + "/" + ファイル名` を読み込む。値の trim、存在確認、正規化、展開、値域検証は行わない。 |
| `/` で始まるファイル名 | 環境変数を使わず、その絶対パスを直接読む。 |

真偽値や数値への変換はありません。空文字を設定すると相対ファイル名のパスは `/ファイル名` となり、通常は読み込みに失敗するでしょう（実際の成否はその絶対パス上のファイル有無とアクセス権による）。読み込みに失敗すると `mtl: cannot read <path>` を stderr に出し、終了コード 2 でプロセスを終了する。

## 有効になる条件

- `metal/` の Metal プロジェクトをビルドして実行する場合に限る。CMake は macOS 以外では構成を停止する。CUDA / HIP / SYCL のビルド経路はこの変数を参照しない。
- Metal engine をビルドする場合、この変数は共通の相対パス指定カーネル（例: `quant.metal`, `units.metal`, `moe.metal`, `prompt.metal`）の探索先を変える。
- `ple.metal`、`mtp.metal`、`mtp_chain.metal` のように `STRATA_METAL_ENGINE_KERNELS_DEFAULT` を含むパスとして直接指定される engine 専用カーネルは、この変数の対象外。
- 上書き先には、対象プログラムが要求するすべての相対 `.metal` ファイルが必要。どれかを開けない場合は上記の読み込みエラーで終了する。読めても MSL としてコンパイルできない場合は、`mtl: compile failed (...)` を stderr に出して終了コード 3 となる。

## 実行時の詳細

`mtl::Context` のコンストラクターで `std::getenv("STRATA_METAL_KERNELS")` を一度呼び、値が存在すれば `kernel_dir` にコピーし、未設定ならビルド既定値をコピーする。したがって、同じ `Context` では作成後にプロセス環境を変更しても探索先は変わらない。新しく作る `Context` は、その作成時点の環境値を読み取る。

`Context::compile()` は受け取った各ファイル名について、先頭文字が `/` ならそのまま、それ以外なら `kernel_dir + "/" + ファイル名` を `read_file()` に渡し、ソースを連結して Metal の実行時コンパイラーへ渡す。engine の初期化では decode 用ライブラリーや prompt 用ライブラリーの一部をこの方法でコンパイルする。ライブラリーのコンパイルに失敗した場合はエラー詳細を stderr に出し、終了コード 3 で終了する。

## 根拠

- `metal/src/mtl_rt.mm:42-53`: `Context` 作成時の環境読み取りと、未設定時の既定値。
- `metal/src/mtl_rt.mm:19-27,68-98`: ファイルを開けない場合の stderr と終了コード 2、パス構築、実行時コンパイル失敗時の stderr と終了コード 3。
- `metal/src/engine/window.cpp:438-444,2036-2039`: engine の decode と prompt で相対名の共通カーネルと、`STRATA_METAL_ENGINE_KERNELS_DEFAULT` を使う別パスのカーネルをコンパイルする箇所。
- `metal/CMakeLists.txt:16-18,32-39,103-123`: macOS 限定、既定の `metal/kernels` パス、および standalone kernel / engine のビルド構成。
- `docs/MAC.md:203-211`: Metal engine とカーネルの構成説明。`STRATA_METAL_KERNELS` 自体の値や挙動は説明されていない。
