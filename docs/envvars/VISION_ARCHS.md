# `VISION_ARCHS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Windows CUDA パッケージ作成用の `tools/packaging/build_vision_windows.bat` が、画像 reader `strata-vision.exe` をビルドする CUDA architecture のリストを上書きする。エンジン本体の architecture を直接変える設定ではない。reader のビルドと `BUILD.json` の記録に使われ、最終パッケージ作成時には記録された reader architecture がパッケージの `sm_NN` をすべて含むか検査される（`tools/packaging/build_vision_windows.bat:26-33,48-60`、`tools/packaging/package_engine.py:103-120`）。

通常の `build_cuda_windows.py` 経由では、この変数は呼び出し元の値をそのまま使う設定ではない。同スクリプトがエンジン用 `ARCHS`（または variant の既定値）から値を作り、子プロセス環境の `VISION_ARCHS` を上書きしてバッチに渡す（`tools/packaging/build_cuda_windows.py:151-160,186-197`）。このため、呼び出し元が設定した `VISION_ARCHS` がその経路でエンジンと reader の architecture を独立にずらすことはない。

## 値と判定

| 実行経路 | 未設定・空文字 | 設定時に使われる値 | 無効値・境界 |
|---|---|---|---|
| `build_vision_windows.bat` を直接起動 | `if defined VISION_ARCHS` が偽なら variant 既定値を使う。空文字の特別処理や数値 parse はスクリプト内にない（`tools/packaging/build_vision_windows.bat:26-33`）。 | 値を `ARCHS` にそのまま代入する。想定形式はセミコロン区切りの CUDA architecture 番号（例: `75;86;89;120`）。番号ごとに `-real` を付け、最後の番号には `-virtual` も渡す（同 `:48-57`）。 | `VISION_ARCHS` 固有の形式・数値・範囲検証はない。`true`、`0`、`0anything` や不正な番号もコード上は拒否せず、置換後の値を CMake に渡す。受理可否は後続コマンドの結果による。 |
| `build_cuda_windows.py` から起動 | 通常は空にならない。variant 既定値か `ARCHS` から得た architecture 列を渡す（`tools/packaging/build_cuda_windows.py:158-160,189-190`）。 | 親環境の `VISION_ARCHS` ではなく、`archs` タプルを `;` で連結した値が必ず渡される（同 `:189-190`）。親の `ARCHS` は `;`・`,`・空白で分割して整数化され、空リストや整数変換失敗は `build_cuda_windows.py:57-65` の `fail` で終了する。 | `VISION_ARCHS` 自体の境界値検証はない。`ARCHS` 経由で負値・範囲外整数が整数として通っても、その数値範囲を検査するコードはこの parser にない。 |

直接起動時の variant 既定値は `cuda12` が `60;61;70;75;80;86;120;89`、`cuda13` が `75;86;89;120`。値の大文字小文字比較や前後空白の trim は行わない（`tools/packaging/build_vision_windows.bat:26-33,48-57`）。ラッパー経由では Python の `ARCHS` parser が `text.strip()` と `;`, `,`, whitespace 分割、各要素の `int` 変換を行う。値が空または数値でなければ `build_cuda_windows.py:57-65` のエラーになる。

## 有効になる条件

- 直接指定が有効なのは、Windows の CUDA reader build バッチを実行する場合。バッチは `cuda12` または `cuda13` と stage folder を引数に要求する（`tools/packaging/build_vision_windows.bat:21-33,64-66`）。
- `build_cuda_windows.py` 経由なら Windows であること、variant が `cuda12` / `cuda13` であることが必要。同スクリプトは Windows 以外では失敗し、variant 以外の起動引数では usage を表示して終了コード 2 を返す（`tools/packaging/build_cuda_windows.py:151-160`）。
- CUDA toolkit、`nvcc.exe`、MSVC `cl.exe`、CMake、Ninja が必要。欠落時はバッチがメッセージを出して終了コード 1 になる（`tools/packaging/build_vision_windows.bat:34-46`）。
- 親スクリプトで `ARCHS` を設定した場合、その解析結果がエンジンと reader の両方に使われるため、子バッチに渡される `VISION_ARCHS` は同じリストになる（`tools/packaging/build_cuda_windows.py:158-160,174,189-190`）。
- 直接バッチ起動で variant と異なるリストを指定すると reader と engine の対象 architecture がずれる可能性がある。後続の `package_engine.py` は reader 付き CUDA package の `BUILD.json` の `vision_archs` を見て package の全 `sm_NN` を検査し、不足があれば `--allow-stale-vision` がない限り packaging を拒否する（`tools/packaging/package_engine.py:103-120,367-371`）。
- サーバー、通常の Strata CLI 実行、モデル読み込み時にこの変数を読むコードは見つからない。実行時のモデル挙動を制御する変数ではない。

## 実行時の詳細

バッチの実行時に環境値を参照し、設定されていればローカル変数 `ARCHS` に移す。続いて `;` を空白に置き換えた `for` ループで各項目を列挙し、全項目を `-real`、最後の項目を `-virtual` として CMake の `CMAKE_CUDA_ARCHITECTURES` に渡す。reader の build 成功後、`strata-vision.exe` を stage にコピーし、同じ `ARCHS` を `package_engine.py --stamp-vision --vision-archs` に渡して `BUILD.json` に記録する（`tools/packaging/build_vision_windows.bat:48-61`）。

`VISION_ARCHS` はバッチ実行時に読み取られ、プロセス内で後から再評価する cache やリクエスト単位の読み取りはない。`build_cuda_windows.py` の場合は起動時に `ARCHS` を解析し、その値を子プロセス用環境へ設定して `cmd` を起動する（`tools/packaging/build_cuda_windows.py:151-160,189-190`）。実行中に親プロセスの環境を変えても、すでに作られた子プロセス環境には反映されない。

## ログと測定値

測定値に関する記載はない。成功時、バッチは `built: <stage>\strata-vision.exe  (<variant>, archs <ARCHS>)` を表示する（`tools/packaging/build_vision_windows.bat:61`）。CUDA toolkit、`nvcc.exe`、`cl.exe` がない場合のメッセージは同ファイル `:34-46`。CMake configure/build、コピー、metadata stamp のいずれかが失敗するとバッチは終了コード 1 を返す（同 `:54-60`）。形式不正に対する `VISION_ARCHS` 専用の診断はなく、後段コマンドの失敗として現れる。

reader architecture の stamp は、`--vision-archs` から認識した数値をソートして `BUILD.json` の `vision_archs` に書く。認識できる値が一つもない場合は `--stamp-vision needs --vision-archs, for example '60;61;70;75;80;86;89'` と argparse error になる（`tools/packaging/package_engine.py:66-75,123-132,351-355`）。

## 根拠

- `tools/packaging/build_vision_windows.bat:16-19,26-61` — 変数の説明、variant 既定値、上書き、CMake 引数、reader build・stamp。
- `tools/packaging/build_cuda_windows.py:57-65,151-197` — Windows/variant 条件、親側 `ARCHS` parse、子環境での `VISION_ARCHS` 上書きと呼び出し。
- `tools/packaging/package_engine.py:66-75,103-120,123-132,325-355,367-371` — stamp の値変換と、CUDA reader の architecture coverage 検査。
