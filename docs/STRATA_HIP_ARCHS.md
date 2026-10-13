# `STRATA_HIP_ARCHS`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

Windows 用 HIP ビルドスクリプト `tools/hip/build_windows.bat` が読む、パッケージに含める AMD GPU アーキテクチャの `;` 区切りリストです。指定したアーキテクチャごとに TheRock の `device-<arch>` wheel を選び、同じリストを CMake の `CMAKE_HIP_ARCHITECTURES` とパッケージ作成スクリプトへ渡します。したがって、単独の実行エンジンが起動時に読む設定ではありません。Linux の `./setup.sh --backend hip` や通常の CMake ビルドでは、CMake の `CMAKE_HIP_ARCHITECTURES` が入力であり、この名前の環境変数を直接は読みません。

## 値と判定

| 状況 | 処理 |
|---|---|
| `STRATA_HIP_ARCHS` が未定義または空 | Windows バッチが `gfx1100;gfx1101;gfx1102;gfx1200;gfx1201;gfx1030;gfx1031;gfx1151` を設定する。 |
| 値を設定 | バッチは文字列の値をそのまま使い、セミコロンを空白に置換して `device-<arch>` の wheel 選択に使う。また、値を CMake の `-DCMAKE_HIP_ARCHITECTURES=...` およびパッケージ作成時の `--archs` に渡す。 |
| CMake が受け取ったアーキテクチャ | 空白をセミコロンに正規化し、各項目の `:` 以降を除いたベース名で許可リストを検査する。重複するベース名は除去される。 |

Windows スクリプト自体はアーキテクチャ名やリスト形式を検証しません。不正な項目や空リストなどは、後続の wheel インストールまたは CMake の設定で失敗し得ます。HIP CMake 設定で認識されるのは、検証済み `gfx1100`, `gfx1201`、コミュニティ報告あり `gfx1101`, `gfx1200`、未検証扱い `gfx1010`, `gfx1011`, `gfx1012`, `gfx1102`, `gfx1103`, `gfx1030`, `gfx1031`, `gfx1034`, `gfx1150`, `gfx1151`, `gfx1152` です。認識済みでも未検証リストの項目には警告が出ます。これ以外は CMake の設定を fatal error で止めます。`gfx1201:xnack-` のような suffix は判定・実行時照合では落とされます。

## 有効になる条件

- `tools/hip/build_windows.bat` を使って Windows HIP エンジンをビルド・パッケージするときに環境変数として有効です。CUDA ビルドや通常の実行時設定には使われません。
- バッチは `build.ninja` がまだない場合に限って CMake を configure し、そのとき環境変数の値を `CMAKE_HIP_ARCHITECTURES` に渡します。既存のビルドディレクトリではこの値で再 configure しません。一方、ROCm wheel の stamp 判定や最終パッケージ処理はその回の値を読みます。そのため、既存ビルドで値だけを変えて再実行すると、ビルド済み engine の対象 arch とパッケージが選ぶ arch が一致しない可能性があります。
- CMake 直接利用時は `-DCMAKE_HIP_ARCHITECTURES=...` が対象アーキテクチャの入力です。`STRATA_HIP_ARCHS` は CMake 内でその正規化済み結果から生成され、HIP runtime target のコンパイル定義としてバイナリに埋め込まれます。
- `STRATA_HIP_GFX906` の互換ビルドは別経路で、この変数を使いません。

## 実行時の詳細

HIP 対応ビルドでは、埋め込まれたコンパイル定数を使い、選択した GPU の `gcnArchName` から `:` 以降を除いたアーキテクチャがビルド対象リストに完全一致するか、さらに wave size が 32 かを確認します。リストにない GPU または wave32 でない GPU は実行可能性チェックに失敗します。`strata generate` は使用する GPU を事前確認し、不一致理由を stderr に出して終了コード 1 を返します。`strata-device --list-devices` は `cannot run: ...` を表示します。`strata-device` の通常の起動情報では、実 GPU arch とコンパイル対象リストを表示します。

これらは実行時に環境変数を再読込する動作ではなく、ビルド時に埋め込まれたリストの使用です。アプリ起動後の `STRATA_HIP_ARCHS` の変更はこのチェックに影響しません。

## 根拠

- `tools/hip/build_windows.bat:13-23,36-46,64-84` — Windows バッチの既定値、wheel 選択、configure 条件、CMake と package への引き渡し。
- `cmake/hip_backend.cmake:4-43,85-90,128` — `CMAKE_HIP_ARCHITECTURES` の既定値、正規化・許可判定・重複除去、コンパイル定義と configure 時ログ。
- `src/core/device.cu:27-63,68-73,215-231,247-299` — コンパイル定数による HIP GPU arch と wave32 の実行時判定、および不一致時のエラー。
- `src/program/generate.cpp:2448-2462` — generate 起動時の使用 GPU 検査と stderr / 終了コード。
- `src/core/device_main.cpp:43-75` — `--list-devices` の不一致表示と通常起動時のコンパイル対象表示。
- `tools/hip/package_windows.py:68-76,119-140` — バッチから渡る arch リストを使った ROCm kernel / kpack の選択。
- `CMakeLists.txt:125-145` — `STRATA_HIP_GFX906` 互換ビルドが分離された経路であること。
