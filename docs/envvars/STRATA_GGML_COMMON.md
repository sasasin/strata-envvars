# `STRATA_GGML_COMMON`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal の実行時シェーダーコンパイルで、`ggml-common.h` の内容をソースへ追加する際に使うファイルパスを指定します。通常の Strata エンジンでは量子化カーネルを含む Metal ライブラリのコンパイルに使われます。Metal 以外の CUDA/HIP/SYCL 経路でこの変数を読む Strata コードはありません。

## 値と判定

| 環境変数の状態 | `Context` が使うパス | コンパイル時の結果 |
|---|---|---|
| 未設定 | ビルド時の `STRATA_GGML_COMMON_DEFAULT` | 通常はそのファイルを読み込み、Metal ソースへ追加する |
| 空文字を設定 | 空文字 | `ggml-common.h` の追加をスキップする |
| 空でない値を設定 | 値全体をファイルパスとして使用 | 対象ファイルを読み、内容を追加する。読み込みに失敗すると終了する |

値の trim、存在確認、別のパスへの fallback、文字列の追加解釈はありません。空文字は未設定と同じではありません。既定パスは `metal/CMakeLists.txt` が `${STRATA_ROOT}/third_party/ggml/ggml-common.h` として定義し、コンパイル定義で Metal ランタイムへ渡します。

## 有効になる条件

- `metal/` の Metal 実装を使う場合だけです。この CMake プロジェクトは Apple 以外の OS では構成を停止します。
- `Context::compile()` の `prelude` に `NO_GGML_COMMON` という部分文字列がない場合にだけ、パスを読み込みます。これは環境変数ではなく、呼び出し側が渡すコンパイル前置文字列です。
- Strata の Metal エンジンは `quant.metal` などを含む主ライブラリを前置文字列なしでコンパイルするため、通常のエンジン経路ではこの読み込みが行われます。GDN、QSA、サンプラーなど別ライブラリのコンパイルは `NO_GGML_COMMON` を渡して追加を抑止します。
- 空文字で追加を抑止すると、`ggml-common.h` の定数配列を参照するコンパイル経路ではシェーダーのコンパイルが失敗し得ます。すべての Metal ライブラリがこのファイルを必要とするわけではありません。

## 実行時の詳細

環境変数は `mtl::Context` のコンストラクターで一度読み、Context の `ggml_common_path` に保存します。プロセス環境を後から変えても、その Context の保存済みパスは変わりません。エンジンでは `Window::open()` が Context を作成し、その後、通常の量子化カーネル群をコンパイルします。

読み込み対象が開けない場合、`read_file()` は stderr に `mtl: cannot read <path>` を出してプロセスを終了コード 2 で終了します。パスの妥当性は Context 作成時ではなく、`NO_GGML_COMMON` でないコンパイルが実際にファイルを読む時に確認されます。

## 根拠

- `metal/src/mtl_rt.mm:19-27`: ファイルの読み込みと失敗時の stderr、終了コード 2。
- `metal/src/mtl_rt.mm:42-53`: Context 作成時の環境変数読み取りと既定パスへの fallback。
- `metal/src/mtl_rt.mm:68-78`: `NO_GGML_COMMON` による抑止、定義の追加とファイル内容の連結。
- `metal/CMakeLists.txt:16-18,29-39,114-120`: Apple 限定、既定パスの設定とコンパイル定義。
- `metal/src/engine/window.cpp:425-444`: エンジンの Context 作成と、共通ヘッダーあり・なしのライブラリコンパイル。
- `metal/kernels/quant.metal:5-8,65-76`: 共通ヘッダー由来の量子化テーブルを使うカーネル側の根拠。

`docs/DETAILS.md` と `docs/` 内には `STRATA_GGML_COMMON` の説明は見つかりませんでした。性能値はこの変数の役割を説明する根拠として確認できなかったため記載していません。
