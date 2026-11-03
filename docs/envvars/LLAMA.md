# `LLAMA`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Linux AMD/HIP 向けのパッケージ作成スクリプトが参照する、llama.cpp checkout のディレクトリです。Strata の実行時設定ではなく、ビルド時に CMake の `STRATA_GGML_DIR` または `LLAMA_DIR` へ渡す入力です。`packaging/build_hip_linux.sh` はエンジンと CPU/GPU vision reader を構成し、`packaging/build_dsv41_hip_linux.sh` は DeepSeek-V4.1 エンジンを構成します（`packaging/build_hip_linux.sh:5-18,25,60-86`; `packaging/build_dsv41_hip_linux.sh:2-13,17,46-48`）。

## 値と判定

両スクリプトは Bash の `${LLAMA:?...}` を使います。値を数値や真偽値として parse せず、ディレクトリのパスとして後続の CMake 引数に展開します。

| 状態 | 判定と結果 |
|---|---|
| 未設定 | 必須パラメーター展開が失敗し、Bash が指定された案内文字列を含む診断を出してスクリプトを終了します。 |
| 空文字 | 未設定と同じく展開が失敗します。 |
| 空でない値 | パスとしてそのまま保持し、引用した CMake 引数に渡します。スクリプト内でパスの存在、checkout の commit、指定 commit との一致は検証しません。 |

既定値や別環境変数からの fallback はありません。`build_hip_linux.sh` では `VISION_ONLY` が設定されてエンジン構成を飛ばす場合も、`LLAMA` の必須チェックは先に実行され、vision reader の構成に使われます（`packaging/build_hip_linux.sh:22-25,60-64,78-86`）。

## 有効になる条件

- `LLAMA` の読み取りは Linux HIP パッケージ用の `packaging/build_hip_linux.sh` と `packaging/build_dsv41_hip_linux.sh` を実行したときに限られます。OS/backend は各スクリプトの対象に由来し、Strata の通常実行やサーバー起動で読む環境変数ではありません（`packaging/build_hip_linux.sh:1-4`; `packaging/build_dsv41_hip_linux.sh:1-4,14-18`）。
- `build_hip_linux.sh` は通常のエンジン構成で `-DSTRATA_GGML_DIR="$LLAMA"` を渡し、vision reader の CPU/HIP 両構成で `-DLLAMA_DIR="$LLAMA"` を渡します。`VISION_ONLY` が空でない場合は通常エンジン構成を省略しますが、CPU/HIP reader は引き続き構成します（`packaging/build_hip_linux.sh:60-64,78-86`）。
- 同スクリプト内で DSV41 を追加構成するときも `STRATA_GGML_DIR` に渡されます。その経路は `DSV41=1` のときです（`packaging/build_hip_linux.sh:42,68-75`）。
- `build_dsv41_hip_linux.sh` は DSV41 エンジンを HIP で構成し、`STRATA_NATIVE_EXPERTS=ON` と `STRATA_GGML_DIR` を渡します（`packaging/build_dsv41_hip_linux.sh:46-50`）。

CMake は `STRATA_GGML_DIR` が空でなければその下の `ggml` を追加し、空なら pin された llama.cpp commit を FetchContent します。標準 CMake の既定は `STRATA_NATIVE_EXPERTS=ON` です（`CMakeLists.txt:176,2045-2050,2057,2104-2116`）。vision 側は `LLAMA_DIR` を既定でリポジトリ内の `third_party/llama.cpp` にしますが、これらのパッケージスクリプトは `-DLLAMA_DIR="$LLAMA"` を明示してその既定を置き換えます（`tools/vision/CMakeLists.txt:17,94`; `packaging/build_hip_linux.sh:79,85`）。

スクリプトのコメントは pinned commit の checkout を指定するよう案内していますが、スクリプト自身はその commit を照合しません。実際のパスが必要な構成であること、対象ライブラリ側のビルド結果などは CMake/後続ビルドに委ねられます（`packaging/build_hip_linux.sh:10,25,62`; `packaging/build_dsv41_hip_linux.sh:8,17,47`）。

## 実行時の詳細

各スクリプトの冒頭で一度シェル変数 `LLAMA` に展開します。以後は実行中の環境変更を読み直す処理はなく、実行中に環境変数を書き換えても、この値の展開結果は変わりません。値は CMake の `-D` 引数に埋め込まれ、エンジン側では `STRATA_GGML_DIR/ggml`、vision 側では `LLAMA_DIR` のソースディレクトリとして使われます（`packaging/build_hip_linux.sh:25,62,79,85`; `packaging/build_dsv41_hip_linux.sh:17,47`; `CMakeLists.txt:2050,2104-2105`; `tools/vision/CMakeLists.txt:17,94`）。

未設定または空文字なら CMake 起動前にシェルが失敗します。指定パスが構成に使えず CMake が非ゼロで終わる場合、通常エンジン構成は `cfg.log`、DSV41 構成は `cfg-dsv41.log` に出力を保存し、`chk` が `build.status` に失敗段階と終了コードを記録して終了します。vision 構成のログは `cfg-vision.log` / `cfg-vision-hip.log` に保存され、後続のビルド失敗は同じ `chk` に記録されます（`packaging/build_hip_linux.sh:47-48,61-66,79-89`; `packaging/build_dsv41_hip_linux.sh:33-35,46-51`）。

`LLAMA` という綴りの他の参照には、CMake 関数引数、テスト用 CMake 変数、リポジトリ内のパス定数、Windows バッチ内で `STRATA_GGML_DIR` から作られるローカル変数があります。それらは `LLAMA` という名前の環境変数を独立に読む箇所ではありません。この調査では実環境読み取りを上記2スクリプトの必須パラメーター展開に確認しました。

## 根拠

- `packaging/build_hip_linux.sh:5-18,22-25,42,47-48,60-89` — ビルド用途、必須値、エンジン/vision/DSV41 への受け渡し、失敗記録。
- `packaging/build_dsv41_hip_linux.sh:8-18,33-35,43-51` — DSV41 用の必須値、受け渡し、失敗記録。
- `CMakeLists.txt:176,2045-2050,2057,2104-2116` — `STRATA_GGML_DIR` の既定、ローカル ggml と pinned FetchContent の分岐。
- `tools/vision/CMakeLists.txt:17,94` — `LLAMA_DIR` の既定と llama.cpp ソースの追加。
