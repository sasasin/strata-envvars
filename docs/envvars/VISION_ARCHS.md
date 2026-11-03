# `VISION_ARCHS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Windows CUDA パッケージ用の `strata-vision.exe` をビルドするとき、対象 GPU architecture の一覧を variant の既定値から上書きします。これは `packaging/build_vision_windows.bat` が参照するビルド用の環境変数で、通常の Strata 実行時に読み込まれる設定ではありません。値は Vision reader の CUDA architecture 指定と、stage の `BUILD.json` に記録する `vision_archs` の両方に使われます（`packaging/build_vision_windows.bat:16-19,26-33,57-64`）。

## 値と判定

| 状態 | `ARCHS` の値 |
|---|---|
| `VISION_ARCHS` が未定義 | `cuda12` は `60;61;70;75;80;86;89`、`cuda13` は `75;86;89;120` |
| `VISION_ARCHS` が定義済み | その値を `ARCHS` に代入し、variant の既定値を上書き |

バッチは値を数値として parse したり、一覧を事前検証したりせず、`;` を区切りとして `-real` の列に変換し、最後の要素を `-virtual` として CMake に渡します（`packaging/build_vision_windows.bat:51-60`）。同じ元の値を `package_engine.py --vision-archs` にも渡します。記録処理は数字の architecture（`sm_` / `compute_` 接頭辞や `-real` / `-virtual` 等を含む表記も可）を拾い、数字を一つも認識できない場合は引数エラーになります（`packaging/package_engine.py:68-77,312-313,335-339`）。部分的に認識できる値では、認識できた番号だけが `BUILD.json` に記録されます（`packaging/package_engine.py:125-134`）。

バッチの判定は `if defined VISION_ARCHS` です。空文字専用の処理や空白除去はなく、空文字がこの分岐でどう扱われるかは環境ブロックの状態に依存します。少なくとも空文字を明示的に検証・拒否するコードはありません（`packaging/build_vision_windows.bat:33`）。

## 有効になる条件

- `packaging/build_vision_windows.bat cuda12 <stage>` または `... cuda13 <stage>` の Windows バッチ経路でのみ参照されます。variant と stage の引数がない場合、または variant がこの二つ以外の場合は usage を出して終了コード 2 になります（`packaging/build_vision_windows.bat:21-32,67-69`）。
- 環境変数は variant が設定する既定 `ARCHS` より優先されます。これは engine 本体の architecture を再ビルド・変更する指定ではなく、Vision reader のビルド値と reader 用メタデータを設定します（`packaging/build_vision_windows.bat:26-33,57-64`）。
- CUDA toolkit、`nvcc.exe`、llama.cpp の `tools/mtmd`、MSVC `cl.exe` などの前提が満たされなければ後続処理へ進みません。architecture 指定を上書きしてもこれらの検査は省略されません（`packaging/build_vision_windows.bat:34-49`）。
- パッケージ化時には `package_engine.py` が `BUILD.json` の `vision_archs` を engine の `archs` と照合し、reader がカバーしない CUDA architecture があると通常は拒否します（`packaging/package_engine.py:80-88,105-119`）。したがって独自の値で reader をビルドする場合も、パッケージの対象 architecture をカバーする値にする必要があります。

## 実行時の詳細

環境変数はバッチ実行中、variant の既定値を作った直後に一度だけ参照されます。`setlocal` の範囲内で `ARCHS` にコピーされ、その後は子プロセスへの明示的な引数として CMake の `CMAKE_CUDA_ARCHITECTURES` と `package_engine.py --vision-archs` に渡されます（`packaging/build_vision_windows.bat:20,26-33,57-63`）。バッチは常駐プロセスではないため、Strata の起動後やモデル実行中にこの環境変数を読んだり再評価したりする経路はありません。候補名の全参照検索でも、読み取り箇所はこのバッチの `if defined` と代入だけでした。

CMake configure、compile、成果物 copy、または `BUILD.json` の stamp が失敗すると、バッチはその箇所で終了コード 1 を返します。architecture 指定の形式をこのバッチ自身が事前に検証するわけではなく、configure/build の出力は各コマンド側から出ます。stamp 段階では有効な architecture 番号が一つも認識されない場合に `argparse` がエラーを出します（`packaging/build_vision_windows.bat:57-63`; `packaging/package_engine.py:335-339`）。成功時は stage に reader をコピーして `BUILD.json` を更新し、architecture 一覧を含む `built:` 行を表示します（`packaging/build_vision_windows.bat:62-65`; `packaging/package_engine.py:125-134,338-339`）。

## 根拠

- `packaging/build_vision_windows.bat:16-19,26-33`: 対象変数の説明、variant ごとの既定値、上書き判定。
- `packaging/build_vision_windows.bat:34-49,51-64,67-69`: ビルド前提、architecture の引き渡し、失敗終了、成功ログ、usage。
- `packaging/package_engine.py:68-77,80-88,105-119,125-134,312-339`: architecture 番号の認識、パッケージとの照合、`BUILD.json` 記録と stamp 時のエラー。
