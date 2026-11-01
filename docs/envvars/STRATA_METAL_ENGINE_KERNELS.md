# `STRATA_METAL_ENGINE_KERNELS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata 所有ソースを対象とし、外部ライブラリの挙動は含めない。

## 役割

Metal engine が実行時にコンパイルする独自 MSL カーネル `ple.metal`、`mtp.metal`、`mtp_chain.metal` の置き場所を指定します。環境変数の値はファイル名ではなくディレクトリとして使われ、各カーネル名が末尾に連結されます。実際に参照するのは Metal backend の `Window` 実装です。

## 値と判定

値の parse、数値変換、真偽判定、空白除去、範囲検査はありません。`resource()` は環境変数が設定されていれば、その文字列をそのままディレクトリとして返します。

| 状態 | 使用するディレクトリ |
|---|---|
| 未設定 | 実行ファイルの隣の `metal/engine-msl` が存在すればそのパス。存在しなければビルド時に定義された `STRATA_METAL_ENGINE_KERNELS_DEFAULT`（通常はソースツリーの `metal/src/engine/msl`） |
| 空文字を設定 | 空文字をそのまま採用し、呼び出し元が `/ple.metal` 等を組み立てる。未設定時の検索へは戻らない |
| その他の文字列 | 文字列をそのまま採用。絶対パスはそのまま使われ、相対パスは `STRATA_METAL_KERNELS` が決める通常カーネルディレクトリの下として扱われる。存在確認や補正はしない |

末尾 `/` の重複や不正なパス文字列も Strata 側では検証しません。`Context::compile()` は、完成したファイルパスが `/` で始まる場合はそのまま読み、それ以外は `STRATA_METAL_KERNELS` が決める通常カーネルディレクトリを前置します。したがって空文字時に組み立てられる `/ple.metal` 等は絶対パスとして読まれます。

## 有効になる条件

- Metal 用 `strata` のビルドでのみ関係します。`metal/CMakeLists.txt` では `STRATA_METAL_ENGINE` が既定で `ON` であり、`OFF` の場合は Metal engine の定義より前に CMake 設定を return します。
- Metal engine の `Window::init()` は幾何条件を通過してモデルを開いた後、`ple.metal` のコンパイルを行います。このため、このパスは通常の window 初期化時に使われます。
- `mtp.metal` は MTP draft model のロード時に使われます。`mtp_chain.metal` はさらに、`STRATA_METAL_MTP_CHAIN` が未設定または文字列全体が `0` 以外で、埋め込み tensor の型が実装の許可リストに含まれる場合にだけコンパイルされます。この別変数は chain 機能の条件であり、カーネルディレクトリの指定値を上書きしません。
- CLI 引数や設定ファイルによるこのパスの上書きは、確認した呼び出し経路にはありません。

## 実行時の詳細

共通 helper `strata_metal::resource(env, sub, compiled)` は、`env` が非 null の場合に `std::getenv(env)` を毎回呼び、設定値があれば即座に返します。未設定なら実行ファイルのパスから隣接リソースを調べ、最後にコンパイル時パスへ進みます。`STRATA_METAL_ENGINE_KERNELS` の値自体を static 変数等へ保存する処理はありません。各 `resource()` 呼び出し時に環境を読みますが、各カーネルパスはそれぞれのコンパイル呼び出しの時点で確定します。

`ple.metal` は `Window::init()` で `lple_` 用にコンパイルされます。MTP ロード時には `mtp.metal` を `lmtp_` 用にコンパイルし、条件が整えば `mtp_chain.metal` もコンパイルします。各 `.metal` ファイルを開くのは `Context::compile()` 内の `read_file()` です。読み取りに失敗すると stderr に `mtl: cannot read <path>` を出し、プロセスを終了コード 2 で終了します。ファイルは読めても Metal のソースコンパイルに失敗した場合は `mtl: compile failed (<device>, macOS <version>; <file>):` とコンパイラのエラーを stderr に出して終了コード 3 になります。環境変数の値そのものに関する警告や fallback はありません。

## 根拠

- `metal/src/resource_path.h:43-54` — 環境値、実行ファイル隣接ディレクトリ、コンパイル時パスの選択順と未設定時の存在確認。
- `metal/CMakeLists.txt:73-80,121-130` — Metal engine の build option と実行ファイルへの組み込み。
- `metal/CMakeLists.txt:123-126` — `STRATA_METAL_ENGINE_KERNELS_DEFAULT` のコンパイル時定義。
- `metal/src/engine/window.cpp:524-542,581-587` — Window 初期化条件と `ple.metal` のパス解決・コンパイル。
- `metal/src/engine/window.cpp:1949-1966` — MTP モデルロード時の `mtp.metal` のパス解決・コンパイル。
- `metal/src/engine/window.cpp:2038-2046` — tensor 型と `STRATA_METAL_MTP_CHAIN` による chain の条件、および `mtp_chain.metal` のコンパイル。
- `metal/src/mtl_rt.mm:32-40,331-361` — 絶対パスと kernel directory の合成、ファイル読み込み失敗時の終了コード 2、Metal compile 失敗時のログと終了コード 3。

候補一覧 `docs/envvars/000_envvers.md:1032` に名前があります。完全一致検索では、上記3つの呼び出しと CMake の既定値定義が確認できました。環境値を直接読む共通 helper は `metal/src/resource_path.h` です。
