# `STRATA_HIP_ARCH_LIST`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`STRATA_HIP_ARCH_LIST` は実行時環境変数ではなく、HIP backend の CMake configure 時に `CMAKE_HIP_ARCHITECTURES` から作られる内部 CMake リストです。したがって、プロセス環境へ `STRATA_HIP_ARCH_LIST` を設定しても、この実装がそれを読み取る箇所はありません。

このリストは重複を除いた HIP 対象アーキテクチャを保持します。`;` 区切りのリストから `:` 以降の feature suffix を除いた各 arch を検証して追加します。後でカンマ区切りの `STRATA_HIP_ARCHS` に変換され、HIP runtime target の compile definition としてバイナリに埋め込まれます。

## 値と判定

| 入力・条件 | CMake の処理 |
|---|---|
| `CMAKE_HIP_ARCHITECTURES` が未定義または空 | `gfx1100` を既定値として設定します。 |
| arch の区切り | CMake の `;` に加えて、入力中の空白を `;` に置換して分割します。空要素は読み飛ばします。 |
| arch に `:suffix` がある | 最初の `:` 以降を削り、base arch を検証・追加します。 |
| 対応リストにない base arch | configure を `FATAL_ERROR` で停止します。 |
| 重複 arch | `list(REMOVE_DUPLICATES)` で除去します。 |
| 処理後のリストが空 | `FATAL_ERROR` で停止します。 |

検証済み arch は `gfx1100`, `gfx1201`、コミュニティ報告で動作確認された arch は `gfx1101`, `gfx1200` です。別の許可リストにある arch は未検証として warning を出して受け入れます。リスト外はエラーです。CMake の `IN_LIST` による照合で、大文字小文字を変換する処理はありません。

## 有効になる条件

トップレベル CMake が `STRATA_ENABLE_HIP` のときだけ `cmake/hip_backend.cmake` を include し、このリストを構築します。これは configure/build 時の条件で、環境変数や通常の CUDA・gfx906 compat backend の設定ではありません。

`CMAKE_HIP_ARCHITECTURES` は CMake 変数です。Strata のセットアップやビルド呼び出しが `-DCMAKE_HIP_ARCHITECTURES=...` として渡す経路があります。候補名そのものの `STRATA_HIP_ARCH_LIST` については、リポジトリ内で `cmake/hip_backend.cmake` の代入・変換以外に参照はありません。なお、`STRATA_HIP_ARCHS` は別名で、Windows HIP build script が環境変数として読み、CMake 変数へ渡すものです。

## 実行時の詳細

configure 時に作った arch 一覧は、`;` を `,` に変換した後、`strata_hip_runtime` の compile definition `STRATA_HIP_ARCHS` として HIP target に渡されます。実行時には `src/core/device.cu` が埋め込み済み一覧と GPU の base arch を照合します。一覧にない arch、または wave size が 32 でない GPU は `arch_problem()` が理由文字列を返し、device 初期化側でエラーになります。実行時に `STRATA_HIP_ARCH_LIST` 環境変数を変更しても、このコンパイル済み一覧は変化しません。

## 根拠

- `CMakeLists.txt:115-117` — HIP backend 有効時に限り CMake module を include。
- `cmake/hip_backend.cmake:4-6,13-43` — 入力の既定値、区切り正規化、suffix 除去、許可リスト判定、重複除去、空リスト判定、派生 arch 文字列。
- `cmake/hip_backend.cmake:94-98,137` — runtime target の定義と configure status 表示。
- `src/core/device.cu:29-64,70-75` — コンパイル時 arch 一覧の必須チェックと GPU arch / wave32 の照合。
- `tools/hip/build_windows.bat:14,26,75` — 別名 `STRATA_HIP_ARCHS` を環境から受け取り、`CMAKE_HIP_ARCHITECTURES` に渡すビルドラッパーの例。

候補一覧の `STRATA_HIP_ARCH_LIST` は、環境変数名と CMake 内部変数名を区別しない検索で候補に入ったものと判断できます。この文書はその名前を実行時環境変数として説明するものではありません。
