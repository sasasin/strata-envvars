# `VISION_BUILD_DIR`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Windows 用の vision reader (`strata-vision.exe`) を engine package 向けにビルドするとき、CMake の build directory を指定します。対象は `packaging/build_vision_windows.bat` による packaging/build 経路です。Strata の実行時エンジンや vision reader がこの変数を読む箇所は見つかりませんでした。

## 値と判定

| 環境の状態 | バッチの処理 |
|---|---|
| 未設定、または `if not defined` で未定義として扱われる状態 | `VISION_BUILD_DIR` に `%SRC%\build-vision-%VARIANT%-win` を設定します。`VARIANT` は第 1 引数 (`cuda12` または `cuda13`) です。 |
| 設定あり | 値を変換・数値化・正規化せず、build directory のパスとして使います。 |

既定値の設定後、値は引用符付きで `cmake -B`、`cmake --build`、成果物の `copy` の各パスに展開されます。バッチ内に空白を含むパスを拒否する処理はありません。値の存在確認や専用の無効値判定もありません。コマンドライン引数に build directory を指定する入口はなく、ここで確認できる指定元は環境変数と未設定時の既定値です。

根拠: `packaging/build_vision_windows.bat:20-24,40,57-62`。

## 有効になる条件

- Windows 上で `packaging/build_vision_windows.bat cuda12 <stage folder>` または `... cuda13 <stage folder>` を実行する経路です。variant と stage folder のどちらかが空なら usage を表示して終了コード 2 で終わります (`packaging/build_vision_windows.bat:21-24,67-69`)。
- この変数は CUDA 12/13 の vision reader をビルドする build directory にだけ使われます。variant に応じて `ARCHS` と任意の `CUDA_PATH_V12_9` / `CUDA_PATH_V13_0` が選択されます (`packaging/build_vision_windows.bat:26-32`)。
- build directory の指定があっても、CUDA toolkit の `CUDA_PATH`、`nvcc.exe`、llama.cpp の `tools/mtmd`、MSVC `cl.exe` などの前提が満たされないと先へ進みません (`packaging/build_vision_windows.bat:34-39,43-49`)。
- Linux/macOS の vision build script や Strata の通常の実行時設定に適用される根拠はありません。

## 実行時の詳細

バッチは `setlocal` の後に variant と stage folder を位置引数から読み、`VISION_BUILD_DIR` が未定義の場合だけ variant 付き既定値を設定します。その値を `cmake -G Ninja -S "%SRC%\tools\vision" -B "%VISION_BUILD_DIR%" ...` に渡し、成功後に同じ directory から `strata-vision.exe` を stage folder へコピーします。値を一度決めてから別の build directory に切り替える分岐や、Strata の実行プロセスに設定を転送する処理はありません (`packaging/build_vision_windows.bat:20-24,40,57-64`)。

`VISION_BUILD_DIR` 専用の警告や値検証はありません。CMake configure、build、copy のいずれかが失敗すると、そのコマンドの出力に続いてバッチは `exit /b 1` で終了します (`packaging/build_vision_windows.bat:57-63`)。不正なパスで CMake が出す具体的なエラー文言はこのバッチでは規定していません。

## 根拠

- `packaging/build_vision_windows.bat:16-17`: `VISION_BUILD_DIR` を build folder として任意設定に列挙。
- `packaging/build_vision_windows.bat:40`: 未設定時の既定値。
- `packaging/build_vision_windows.bat:57-62`: CMake build directory としての使用、build、stage 先への copy、および失敗時の終了。

