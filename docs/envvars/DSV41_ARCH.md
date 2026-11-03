# `DSV41_ARCH`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Windows 用 `packaging/build_dsv41_windows.bat` が、DeepSeek-V4.1 専用エンジン (`strata-dsv41.exe`) を構成するときに CUDA の対象アーキテクチャ一覧を指定するビルド用環境変数です。通常の Strata 実行時に読む設定ではありません。このバッチが値を CMake の `CMAKE_CUDA_ARCHITECTURES` 引数へ渡します。

## 値と判定

| 入力 | バッチの扱い |
|---|---|
| 未設定または空文字 | `86-real;89-real;120` に設定して使用 |
| 空白など空でない値 | 値を独自に parse・検証せず、`CMAKE_CUDA_ARCHITECTURES=<値>` として CMake に渡す |

バッチは `%DSV41_ARCH%` が空かどうかだけを調べます。数値変換、区切り文字の検査、許容範囲の確認、大小文字変換、clamp は Strata 側では行いません。たとえば空白だけの値も既定値へ置き換えられず、そのまま渡されます。既定値は sm_86 / sm_89 / sm_120 向けの指定で、コメントは sm_120 の PTX を含む構成と説明しています (`packaging/build_dsv41_windows.bat:5-6,14`)。任意値の受理可否や無効値に対する診断の詳細は、CMake 側の解釈に依存するため、この Strata バッチからは断定できません。

## 有効になる条件

この変数を参照するのは Windows 向けの `packaging/build_dsv41_windows.bat` だけです。バッチに build directory が必要で、`STRATA_GGML_DIR` も設定されている必要があります。ソースディレクトリに `CMakeLists.txt` がある場合、バッチは CUDA 有効・`STRATA_BUILD_DSV41=ON`・Release・portable の CMake 構成と一緒に値を渡し、その後 `strata-dsv41` ターゲットをビルドします (`packaging/build_dsv41_windows.bat:11-20,25`)。したがって、通常の `strata` / `setup.py` 実行、Linux のビルドスクリプト、HIP ビルドにはこの環境変数の参照はありません。

CMake の構成コマンドが失敗すると、バッチは終了コード 1 で終了します (`packaging/build_dsv41_windows.bat:20-21`)。ただし、特定の `DSV41_ARCH` 値が構成に失敗するかどうかや、CMake の具体的なエラー文はソース調査だけでは確定できません。

## 実行時の詳細

値はバッチ実行時に環境から展開されます。既定値を設定した後の CMake 構成コマンドで一度参照され、プロセス内キャッシュや実行中の再読み取りはありません。値を変更する CLI 引数はこのバッチに定義されておらず、アーキテクチャ指定は環境変数から CMake へ転送されます。Strata 独自の `DSV41_ARCH` 警告やログはありません。構成失敗時は終了コード 1 が返り、ビルド後はターゲットのエラーを同様に伝播します (`packaging/build_dsv41_windows.bat:20-21,25-26`)。

## 根拠

- `packaging/build_dsv41_windows.bat:5-6,14` — 変数の用途と既定値。
- `packaging/build_dsv41_windows.bat:11-20` — 必須入力の確認、および値を `CMAKE_CUDA_ARCHITECTURES` に渡す構成処理。
- `packaging/build_dsv41_windows.bat:21,25-26` — CMake 構成・ビルド失敗の終了コード伝播。
- `docs/DEEPSEEK41.md:221-234` — 専用エンジンのビルド説明。Windows では同バッチを使う案内と、アーキテクチャ指定の概要を記載。
