# `STRATA_HIP_ARCHS`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

`STRATA_HIP_ARCHS` は、Strata の Windows HIP ビルドスクリプトが使う任意のビルド時環境変数である。HIP エンジンをどの AMD GPU アーキテクチャ向けにビルドするかを指定し、対応する ROCm デバイス用パッケージと演算ライブラリを配布 ZIP に含めるためにも使う。実行時の Strata プログラムはこの名前の環境変数を読み取らない。ビルド時に値から作られた `STRATA_HIP_ARCHS` コンパイル定義を使って、実行中の GPU がバイナリに含まれるアーキテクチャかを検査する。

Linux の手動 HIP ビルドでは、文書は `CMAKE_HIP_ARCHITECTURES` を直接指定する方法を案内しており、この環境変数を経由しない（`docs/AMD_HIP.md:131-144`）。

## 値と判定

| 状況 | 処理 |
|---|---|
| Windows ビルドスクリプト起動時に未設定または空 | `gfx1100;gfx1101;gfx1102;gfx1200;gfx1201;gfx1030;gfx1031;gfx1151` を既定値として設定する。 |
| 1つ以上のアーキテクチャを指定 | セミコロン区切りの値を、ROCm デバイス用 wheel の選択、`CMAKE_HIP_ARCHITECTURES`、ZIP パッケージ処理へ渡す。 |
| 空要素だけの値 | CMake 側で空要素を読み飛ばし、アーキテクチャが1つも残らなければ `Strata HIP: CMAKE_HIP_ARCHITECTURES is empty` で構成を失敗させる。 |
| 未対応アーキテクチャを含む値 | HIP 構成時に `CMAKE_HIP_ARCHITECTURES` の値と対応対象を示す fatal error で失敗する。 |

Windows スクリプトの既定値は任意設定で上書きできる。CMake はセミコロンに加えて空白もリスト区切りとして扱い、`gfx1201:sramecc-:xnack-` のような要素はコロン以降を落とした `gfx1201` で検証・記録する。同じ基本アーキテクチャの重複は除かれる。検証対象は大文字小文字を含め完全一致であり、認定済み (`gfx1100`, `gfx1201`)、コミュニティ報告で検証 (`gfx1101`, `gfx1200`)、未検証だがビルド可能な一覧に応じて、通常続行、STATUS、WARNING のいずれかになる。どの一覧にもない値は失敗する（`cmake/hip_backend.cmake:13-40`）。

## 有効になる条件

- この環境変数を直接参照するのは `tools/hip/build_windows.bat`。Windows HIP エンジンと ZIP を作る経路で使われる（`tools/hip/build_windows.bat:13-23`）。
- `STRATA_HIP_ARCHS` は `build.ninja` がまだない場合にだけ `CMAKE_HIP_ARCHITECTURES` として CMake 初回構成へ渡される。既存のビルドディレクトリではスクリプトが再構成を行わないため、後から環境変数だけを変えても、既存ビルドの対象アーキテクチャは更新されない（`tools/hip/build_windows.bat:64-80`）。
- HIP のアーキテクチャ許可リストにあることは、ハードウェア上での検証済みを意味しない。CMake は検証区分をログまたは警告に出しつつ、許可された未検証アーキテクチャのビルドも続ける（`cmake/hip_backend.cmake:7-15,25-34`）。
- HIP 以外のバックエンドには、この変数による実行時の GPU 判定は適用されない。

## 実行時の詳細

Windows バッチは未設定時の既定値を設定し、リスト内の各アーキテクチャに対応する `device-<arch>` wheel を ROCm のインストール指定へ加える。初回構成では同じ値を `-DCMAKE_HIP_ARCHITECTURES=...` として渡す（`tools/hip/build_windows.bat:21,35-46,67-74`）。CMake は許可された基本アーキテクチャを重複なしのリストにし、カンマ区切りの文字列を `STRATA_HIP_ARCHS` コンパイル定義として HIP ターゲットへ設定する（`cmake/hip_backend.cmake:18-43,85-90`）。

ビルド後のパッケージ処理にもバッチが現在の環境変数を `--archs` で渡す。パッケージャーは指定されたアーキテクチャ分の rocBLAS/hipBLASLt カーネルと `.kpack` ファイルを ZIP に含め、同じ一覧を `BUILD.json` に記録する（`tools/hip/build_windows.bat:82-84`; `tools/hip/package_windows.py:119-158`）。したがって既存 `build.ninja` を使って環境変数だけを変更した場合、エンジンがコンパイルされた一覧とパッケージャーが使う一覧が食い違う可能性がある。

HIP 実行ファイルは環境変数を再読込せず、コンパイル定義に埋め込まれたカンマ区切りリストと GPU の `gcnArchName`（コロン以降の機能サフィックスを除去）を完全一致で照合する。対象 GPU がリストになければ「この Strata engine がビルドされたアーキテクチャではない」とする理由を返し、wave サイズが32以外でも HIP カーネルが必要とする wave32 ではない旨を返す（`src/core/device.cu:33-64`）。`strata generate` は実際に使用する GPU を確認し、不一致なら stderr に `strata generate: ...` を出して終了コード1で戻る。`strata-device --list-devices` は該当 GPU に `cannot run: ...` を表示する（`src/program/generate.cpp:2507-2521`; `src/core/device_main.cpp:49-62`）。

同じ HIP 実行時チェックのソース複製が `sycl/src/core/device.dp.cpp:45-88,257-277` にある。そちらもコンパイル定義を使い、実行時の `STRATA_HIP_ARCHS` 環境変数読み取りは行わない。

## 根拠

- `tools/hip/build_windows.bat:13-23,35-46,64-84` — Windows ビルドでの環境変数、既定値、ROCm wheel 選択、CMake とパッケージャーへの引き渡し。
- `cmake/hip_backend.cmake:4-43,85-90` — CMake の既定値、アーキテクチャ一覧と判定、コンパイル定義。
- `src/core/device.cu:29-64,70-75,217-233` — 実行ファイルに埋め込まれた一覧と GPU アーキテクチャ・wave32 検査。
- `sycl/src/core/device.dp.cpp:45-88,257-277` — HIP 実行時チェックのソース複製。
- `src/program/generate.cpp:2507-2521`; `src/core/device_main.cpp:49-62` — 不一致時の生成エラーとデバイス一覧表示。
- `tools/hip/package_windows.py:119-158` — 指定アーキテクチャ用ファイルの同梱と `BUILD.json` の記録。
- `docs/AMD_HIP.md:118-144,451-455` — Windows HIP ビルドでの環境変数利用と、手動ビルドで `CMAKE_HIP_ARCHITECTURES` を使う説明。
