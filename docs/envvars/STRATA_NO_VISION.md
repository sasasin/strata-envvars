# STRATA_NO_VISION

調査対象: Strata main の HEAD c62d5e3a15b40ea51c96aae9e8d36928965f53ab（2026-11-01 時点）。

## 役割

Windows 向け HIP エンジンのビルドスクリプト tools/hip/build_windows.bat で、CPU 用と HIP 用の画像 reader をビルドして配布 ZIP に入れるかを選びます。Strata のエンジンやサーバーが実行時に読む設定ではありません。このスクリプト以外に候補名の参照はなく、通常の CUDA/Linux/HIP 実行経路を制御する読み取りも確認できませんでした。

## 値と判定

build_windows.bat の 91 行目で、展開した環境変数文字列を "1" と比較します。文字列全体の一致が判定基準です。

| 値 | 動作 |
|---|---|
| 未設定 | 空文字として比較され、一致しないため reader をビルドする |
| 空文字 | "1" と一致せず、reader をビルドする |
| 1 | reader のビルドを省略する |
| その他（例: 0, true, 01, 1 の後に空白） | "1" と一致せず、reader をビルドする |

数値変換、前後空白の除去、真偽値パーサーはありません。コマンドライン引数 tests はテスト対象をビルドするかを決めますが、この環境変数の判定を上書きしません（tools/hip/build_windows.bat:32-33,81-91）。

## 有効になる条件

この設定が作用するのは tools/hip/build_windows.bat を実行して Windows HIP 配布物を作る場合だけです。CUDA や Linux の画像 reader ビルドは別スクリプトで、この名前を参照していません。候補名の完全一致検索でも他の読み取りはありません。

STRATA_NO_VISION が 1 以外なら、スクリプトは tools/vision から CPU reader strata-vision.exe と HIP reader strata-vision-hip.exe をビルドします。STRATA_VISION_HIP_ARCHS が未設定なら STRATA_HIP_ARCHS を使います。これらの arch 設定は reader のビルド条件であり、vision を省くかどうかの条件ではありません（tools/hip/build_windows.bat:89-110）。

## 実行時の詳細

この変数はビルドバッチが reader 段階に到達した時に一度展開・判定されます。キャッシュや再読込処理はありません。値が 1 の場合、reader 用 CMake 構成・ビルドを行わず、VISION_ARGS は空のままです。その後の tools/hip/package_windows.py 呼び出しには --vision-cpu / --vision-hip が渡されません。パッケージャーは stage を作り直し、reader 引数が与えられた場合だけ reader 実行ファイルをコピーするため、この ZIP には画像 reader が入りません。BUILD.json の vision は none になります（tools/hip/build_windows.bat:89-115; tools/hip/package_windows.py:89-103,95-97,172-182）。

値が 1 以外の場合は両 reader のビルド後にそれぞれのパスをパッケージャーへ渡し、BUILD.json に vision: cpu と vision: gpu の reader 情報を設定します（tools/hip/build_windows.bat:91-110; tools/hip/package_windows.py:101-103,178-181）。reader 有効側では llama.cpp の tools/mtmd が見つからない場合、スクリプトは "llama.cpp with tools/mtmd not found ... - set STRATA_GGML_DIR" を表示して終了コード 1 で終了します。CMake 構成・ビルドの失敗も || exit /b 1 で終了します。値が 1 で reader を省略したときにこの reader 用のエラー経路は通りませんが、後続のパッケージ処理自体は実行されます（tools/hip/build_windows.bat:95-109,113-115）。この設定専用の警告やログ出力はありません。

## 根拠

- 環境変数の判定と reader ビルド条件、パッケージ引数: tools/hip/build_windows.bat:87-115
- --vision-cpu / --vision-hip が省略可能で、渡された reader のみをコピーする処理: tools/hip/package_windows.py:82-103
- reader の有無を BUILD.json に記録する処理: tools/hip/package_windows.py:172-182
- 候補名のもう一つの参照は配布内容の説明文であり、環境値の読み取りではない: packaging/ENGINE-COMPONENT.md:107
