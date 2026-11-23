# `ARCHS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`ARCHS` は Strata のエンジンや同梱 reader、split engine をビルド・パッケージする一部の Strata 所有スクリプトで、対象 GPU architecture の一覧を指定する環境変数である。通常の `strata` 実行時コードに `ARCHS` を読む箇所はなく、実行中の GPU 選択やモデル動作を変更しない。ビルドスクリプトは値を CMake に渡し、生成物の architecture 一覧やパッケージ metadata にも使う（`tools/packaging/build_cuda_linux.sh:22-23,35-45,70-79`、`tools/packaging/build_hip_linux.sh:33-43,57-65,78-90`、`engine/spark/build_engine.sh:19,48-54,80-87`）。

## 値と判定

| 読み取り経路 | 未設定・空文字 | 設定値の扱いと無効値 |
|---|---|---|
| Linux CUDA release builder (`cuda12` / `cuda13`) | それぞれ `60;61;70;75;80;86;120;89` / `75;86;89;120` | `${ARCHS:-...}` なので未設定または空文字は既定値。非空文字列を数値検証せず受け取り、`;` と `,` を空白に置き換えた各要素を `-real` にし、最後の要素を `-virtual` に付けて CMake に渡す。空白や不正な arch の独自検査はない（`tools/packaging/build_cuda_linux.sh:17-24,35,43-45`）。 |
| Windows CUDA package builder | `os.environ.get("ARCHS")` が空文字または未設定なら variant 既定値（`cuda13`: `75,86,89,120`; `cuda12`: `60,61,70,75,80,86,120,89`） | 非空値を `;`、`,`、空白の連続で分割し、空要素を除いて各要素を Python `int()` で変換する。符号付き整数も変換可能で、正数・範囲・重複の検証はない。数値でない要素は `ARCHS=%r is not a list of numbers like 75;86;89;120` で終了し、区切りだけの値も同じエラーになる。空白だけの値は非空なので parse に進みエラー（`tools/packaging/build_cuda_windows.py:37-42,52-65,155-160`）。 |
| Linux HIP package builder | `rx9070`: `gfx1200;gfx1201`、`rx7900`: `gfx1100;gfx1101;gfx1102`、`rx6000`: `gfx1030;gfx1031;gfx1032`、`halo`: `gfx1151`、`igpu`: `gfx1103;gfx1150`。 | `${ARCHS:-...}` なので空値は variant 既定値。未知の variant では `${ARCHS:?...}` により未設定・空値が `ARCHS=gfx...` の shell parameter error になる。非空値は検証せず、`;` を空白（kernel data 用には `,`）へ置換し、エンジン、HIP reader、metadata に渡す（`tools/packaging/build_hip_linux.sh:33-43,63-65,78-90`）。 |
| Linux HIP split engine builder | 未設定・空文字なら `gfx1201;gfx1200;gfx11-generic` | 非空値を検証せず CMake に渡す。検査ループでは `;` だけを空白に置換して各要素を実行ファイル内で検索するため、欠けた code object があれば `build_split_hip.sh:51-55` のエラーで終了する（`tools/packaging/build_split_hip.sh:26,31-35,51-55`）。 |
| DGX Spark CUDA builder | 未設定・空文字なら `121` | 非空値を検証せず、`,` と `;` を空白に置換して各要素を `-real`、最後の要素を `-virtual` として CMake に渡す（`engine/spark/build_engine.sh:17-19,48-54`）。 |

文字列比較による大文字小文字判定や全リスト共通の数値・範囲検証はない。Windows CUDA のみ区切りを `;` / `,` / 空白として扱い、整数変換する。Linux shell scripts は経路ごとに区切りの置換方法が異なるため、同じ入力が同じように解釈されるとは限らない。

## 有効になる条件

- `tools/packaging/build_cuda_linux.sh` は Linux CUDA release build で `VARIANT=cuda12` または `cuda13` を選んだときに読む。対応する CUDA toolkit が `nvcc` から見つからない、または variant と toolkit の major version が合わない場合は `ARCHS` 処理後に builder 自身の診断を stderr に出して終了する（`tools/packaging/build_cuda_linux.sh:17-33`）。
- `tools/packaging/build_cuda_windows.py` は Windows 上で variant 引数が `cuda12` / `cuda13` のときに読む。非 Windows では `this builds the Windows engine; on Linux use tools/packaging/build_cuda_linux.sh` で終了する。variant は CLI 引数で選び、`ARCHS` がその variant の既定リストを上書きする（`tools/packaging/build_cuda_windows.py:151-160`）。
- `tools/packaging/build_hip_linux.sh` は `VARIANT` で選んだ HIP package builder に限る。既知 variant ではカスタム `ARCHS` を受け、未知 variant では `ARCHS` が必須である（`tools/packaging/build_hip_linux.sh:22,33-40`）。
- `tools/packaging/build_split_hip.sh` は Linux AMD split engine build 専用である。architecture list が生成物に含まれない場合、明示的なチェックで build を失敗させる（`tools/packaging/build_split_hip.sh:2-16,51-55`）。
- `engine/spark/build_engine.sh` は Linux arm64 (`aarch64` / `arm64`) 上の DGX Spark build 専用で、他の OS / CPU では `this builds on arm64 Linux (the DGX Spark)` を stderr に出して終了する（`engine/spark/build_engine.sh:29-32`）。
- Windows CUDA builder は選んだ archs を `VISION_ARCHS` として reader の batch builder に渡す。batch builder は自身の `ARCHS` を variant の既定値で初期化した後、`VISION_ARCHS` が定義されていれば置き換えるため、reader build ではこの内部転送値が使われる（`tools/packaging/build_cuda_windows.py:189-190`、`tools/packaging/build_vision_windows.bat:26-33,48-61`）。
- これらはビルド・パッケージ経路の設定である。Strata engine の runtime、サーバーモード、CLI 推論経路から `ARCHS` を読む箇所は確認できない。`000_envvers.md` の候補名は、ここでは実際に値を読む Strata 同梱の build scripts に対応している。

## 実行時の詳細

各スクリプトの開始時または `main()` 実行時にプロセス環境から読み、その後ローカル変数へ保持して CMake configure、reader build、または package metadata に渡す。関数内 cache やリクエストごとの再読込はないため、実行中に環境を変更しても既に読み込んだ値は変わらない（Linux CUDA: `tools/packaging/build_cuda_linux.sh:17-23`、HIP: `tools/packaging/build_hip_linux.sh:22,33-43`、split HIP: `tools/packaging/build_split_hip.sh:17-26`、Spark: `engine/spark/build_engine.sh:17-20`、Windows CUDA: `tools/packaging/build_cuda_windows.py:151-160`）。

値が各 build に到達する形は異なる。Linux CUDA と Spark では各 arch に machine code (`-real`) を指定し、リスト末尾の arch に PTX (`-virtual`) も指定する。Linux HIP では engine と HIP vision reader の CMake architecture、および package の arch / kernel data metadata に渡す。Windows CUDA は `int` の tuple から同じく全 arch の `-real` と最後の `-virtual` を構成し、package の `--arch` 引数と BUILD.json に記録する（`tools/packaging/build_cuda_linux.sh:35-36,43-45,72-80`、`tools/packaging/build_hip_linux.sh:42-43,63-65,78-90`、`tools/packaging/build_cuda_windows.py:52-55,68-78,174-195`、`engine/spark/build_engine.sh:48-54,80-87`）。

Linux CUDA の不正値は事前検査されず、CMake configure や後続 package 処理が失敗すれば `set -e` によりそこで止まる。HIP builder は configure/build のログを `$OUT/cfg*.log` / `$OUT/build*.log` に記録し、`chk` が失敗段階と return code を `$OUT/build.status` に記録して終了する。Windows CUDA は parse エラーを `SystemExit` として出す。ここで個別に列挙した以外の CMake、compiler、packager のエラー文言や終了条件はそれぞれの下流処理による（`tools/packaging/build_cuda_linux.sh:16,43-45`、`tools/packaging/build_hip_linux.sh:44-47,63-84`、`tools/packaging/build_cuda_windows.py:48-50,59-65`）。

## ログと測定値

Windows CUDA builder の数値リスト parse エラーは `build_cuda_windows.py:64` の文言を `build_cuda_windows.py:49` の `build_cuda_windows.py: ` prefix 付きで終了理由として出す。Linux HIP は `$OUT/build.status` に開始時の variant と architecture list、および失敗段階・return code を記録する（`tools/packaging/build_hip_linux.sh:44-47,57,66,76,81,84`）。Linux CUDA と Spark は `ARCHS` 固有の形式検査・警告を実装していない。性能測定値は該当しない。

## 根拠

- `tools/packaging/build_cuda_linux.sh:17-45,70-80` — CUDA Linux での既定値、変換、CMake と package への受け渡し。
- `tools/packaging/build_cuda_windows.py:37-42,52-65,151-160,174-195` — variant 既定値、Windows の parse と検査、engine / reader / package への受け渡し。
- `tools/packaging/build_vision_windows.bat:26-33,48-61` — Windows reader builder の variant 既定値と `VISION_ARCHS` による上書き。
- `tools/packaging/build_hip_linux.sh:21-43,57-90` — HIP Linux の variant ごとの既定値、変換、build / metadata / ログ。
- `tools/packaging/build_split_hip.sh:17-35,51-55` — split HIP の既定値、CMake への受け渡し、生成物の architecture 確認。
- `engine/spark/build_engine.sh:17-19,29-54,67-87` — Spark build の platform gate、既定値、CMake / metadata への受け渡し。
