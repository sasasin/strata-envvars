# `STRATA_HIP_ARCHS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

これは Strata エンジンの実行時設定ではなく、Windows HIP ビルドスクリプトが読むビルド時の環境変数である。`terminal/tools/hip/build_windows.bat` が未設定なら対象 GPU アーキテクチャ一覧を設定し、その値から TheRock の device wheel 一覧を作り、CMake の `CMAKE_HIP_ARCHITECTURES` と配布スクリプトの `--archs` に渡す（`terminal/tools/hip/build_windows.bat:13-28,43-51,76-84,123-125`）。ビルド済みエンジンでは、この値そのものは環境から読まれない。

CMake は `CMAKE_HIP_ARCHITECTURES` を検証・正規化し、コンパイル定義 `STRATA_HIP_ARCHS` としてアーキテクチャ一覧を実行ファイルへ埋め込む（`engine/cmake/hip_backend.cmake:4-5,18-43,106-109`）。この埋め込み値は HIP デバイスの起動前チェックに使われ、環境変数の実行時変更では変わらない（`engine/src/core/device.cu:41-64,70-75`）。

## 値と判定

| 条件 | unset / 空文字 | 値の扱い | 無効値・境界 |
|---|---|---|---|
| Windows の `terminal/tools/hip/build_windows.bat` | `if not defined` により既定値 `gfx1100;gfx1101;gfx1102;gfx1103;gfx1150;gfx1151;gfx1200;gfx1201;gfx1030;gfx1031` を設定。空文字も未定義扱い | セミコロン区切りの一覧を `for` で区切り、wheel 名を組み立てたうえで、同じ文字列を `-DCMAKE_HIP_ARCHITECTURES=...` と `package_windows.py --archs` に渡す。バッチ自身は真偽値や数値として parse しない（`terminal/tools/hip/build_windows.bat:28,43-44,80,123-125`） | バッチ自身に一覧の検証はない。未知・空要素・不正な arch 名は後段の CMake 構成または wheel / package 処理で問題になり得る。値が空なら上記既定値が使われる（`terminal/tools/hip/build_windows.bat:28,43-44,80`） |
| HIP backend の CMake 構成 | `CMAKE_HIP_ARCHITECTURES` が未定義または空なら `gfx1100` | 空白をセミコロンに直し、各 arch の `:` 以降を除いて検証・重複排除する（`engine/cmake/hip_backend.cmake:4-5,18-37`） | リストが空なら `Strata HIP: CMAKE_HIP_ARCHITECTURES is empty` で configure を失敗させる。検証リスト外なら `message(FATAL_ERROR ...)` で失敗する。無効文字列を黙って fallback する処理はない（同 `:20-40`） |

CMake が受け付けるベース名は、同ファイルの `_strata_hip_validated`、`_strata_hip_community`、`_strata_hip_unvalidated` の一覧に限られる（`engine/cmake/hip_backend.cmake:13-15,24-34`）。分類済み arch は受理され、community 一覧では `Strata HIP: <arch> was validated by community reports (docs/AMD_HIP.md)` の status、unvalidated 一覧では `Strata HIP: <arch> builds, but it is not validated on a real card yet; please report results` の warning が出る。どちらもビルドを止めない。これらのメッセージは CMake の構成時の出力である（同 `:25-33`）。

バッチの「既定一覧」と CMake の「直接 configure 時の既定値」は異なる。前者は Windows ビルド用 wrapper によるもので、後者は `CMAKE_HIP_ARCHITECTURES` 未指定時の `gfx1100` である。CMake にも `STRATA_HIP_ARCHS` という変数がありますが、`hip_backend.cmake` が検証済み `CMAKE_HIP_ARCHITECTURES` から生成する値であり、同名の環境変数を CMake が直接読んでいるわけではない（`engine/cmake/hip_backend.cmake:4-5,35-43`）。

## 有効になる条件

- この環境変数を直接読むのは Windows 用 `terminal/tools/hip/build_windows.bat` の経路である。Linux のビルド設定は環境変数名ではなく CMake の `CMAKE_HIP_ARCHITECTURES` を使う。
- Windows バッチでは `build.ninja` がまだない場合に限って CMake configure を実行し、そこで環境変数を `CMAKE_HIP_ARCHITECTURES` に渡す。既存の build tree では configure をスキップするため、値を変えても既存の CMake キャッシュ上のアーキテクチャは更新されない。一方、後続の配布処理にはその時点の環境値が再び `--archs` として渡る（`terminal/tools/hip/build_windows.bat:76-85,123-125`）。
- ROCm wheel の追加インストール判定は、環境値から生成した `EXTRAS` とバージョンを stamp と比較して行う。差があれば通常は pip install と `rocm-sdk init` を実行するが、`STRATA_ROCM_KEEP=1` のときは差があっても更新しない（同 `:43-53`）。
- `STRATA_NO_VISION=1` なら vision reader のビルドと配布引数が省略される。実行される場合、`STRATA_VISION_HIP_ARCHS` が未設定ならこの変数の値が vision HIP build に渡る（同 `:101-120`）。
- CMake の arch 検証を通ることが必要。未知の arch は configure を失敗させる。対応 arch の分類・status/warning は `engine/cmake/hip_backend.cmake:13-40` を参照。
- 生成エンジンでは HIP backend が有効で、実際に使う GPU がコンパイル済み arch の一つであり、かつ `warpSize == 32` である必要がある（`engine/src/core/device.cu:53-64,224-236`; 呼び出し元 `engine/src/program/generate.cpp:4969-4982`）。

## 実行時の詳細

バッチはプロセス起動時に環境値を展開する。スクリプト内の変数へ値を設定した後、wheel の extras、CMake configure、配布スクリプト呼び出しに使う。実行中に環境値を再読込する処理や、エンジン側で値を cache する処理はない（`terminal/tools/hip/build_windows.bat:26-28,43-53,76-84,123-125`）。ただし configure は build directory に `build.ninja` がない場合だけなので、既存 build tree で arch を変更した場合、ビルド済み engine と package に渡す arch リストが食い違う可能性がある（同 `:76-85,123-125`）。

CMake は検証後の一覧をセミコロンからコンマ区切りへ変えてコンパイル定義に埋め込む（`engine/cmake/hip_backend.cmake:41-43,106-109`）。実行時の `arch_problem` はデバイス名と GPU の base arch（`gcnArchName` の `:` 以降を切り落としたもの）を埋め込み一覧と完全一致で照合する。未対応 arch または wave サイズ不一致なら理由文字列を返す（`engine/src/core/device.cu:33-64`）。

`strata generate` は primary GPU と、multi-GPU / remote expert cache で使う GPU を検査し、問題があれば stderr に `strata generate: <理由>` を出して終了コード `1` を返す（`engine/src/program/generate.cpp:4969-4982`）。デバイス一覧経路では `strata-device` が `cannot run: <理由>` を表示する（`engine/src/core/device_main.cpp:52-65`）。HIP device が一台もない場合は `device_info` が `no HIP device is present; this engine was compiled for <埋め込み一覧>` の `CudaError` を投げる（`engine/src/core/device.cu:256-264`）。

パッケージスクリプトは `--archs` を `;`、`,`、空白で分割し、arch 名の集合を使って ROCm の rocBLAS / hipBLASLt kernels と `.kpack` を選び、`BUILD.json` の `archs` に記録する。不足 `.kpack` があれば `missing <path>: install the rocm-sdk-device-<arch> wheel and run rocm-sdk init` で終了する（`terminal/tools/hip/package_windows.py:82-94,147-178,189-201`）。

## 根拠

- `terminal/tools/hip/build_windows.bat:13-28,43-53,76-85,101-125` — Windows wrapper での読み取り、既定値、wheel・CMake・vision・package への転送。
- `engine/cmake/hip_backend.cmake:4-5,13-43,106-109,148` — `CMAKE_HIP_ARCHITECTURES` の既定・検証、コンパイル定義と configure 時ログ。
- `engine/src/core/device.cu:29-64,70-75,224-240,256-264` — compile-time の arch 表と実行時照合、デバイスなし経路。
- `engine/src/program/generate.cpp:4969-4982`、`engine/src/core/device_main.cpp:52-65` — generate 終了とデバイス一覧表示。
- `terminal/tools/hip/package_windows.py:82-94,147-178,189-217` — package 引数の parse、arch ごとの収録物、manifest と出力。
