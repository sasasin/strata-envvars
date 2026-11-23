# `LIBW`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`LIBW` は Linux AMD/HIP 用のビルド・パッケージ作成スクリプトが、ROCm のライブラリ root を指定するために読む環境変数である。実行時の `strata` エンジンが読む変数ではない。未指定または空文字なら `HP` を使い、値がある場合は HIP の CMake prefix に含めるほか、`build_hip_linux.sh` では ROCm ライブラリや BLAS カーネルデータの収集元として使う（`tools/packaging/build_split_hip.sh:17-35`、`tools/packaging/build_hip_linux.sh:21-29,52-56,91-100,109-110`）。

## 値と判定

両スクリプトとも Bash の `${LIBW:-$HP}` で読み取る。未設定と空文字は同じ扱いで `HP` に置き換わる。空でない値はパス文字列としてそのまま採用される。存在確認、絶対パス化、空白除去、値の構文検証はこの代入では行わない。`HP` 自体は必須で、未設定時はスクリプトの `${HP:?...}` によって終了する（`tools/packaging/build_split_hip.sh:19-21`、`tools/packaging/build_hip_linux.sh:21-28`）。

| スクリプト | `LIBW` 未設定 | 空文字 | 受け付ける値の例 | この代入で無効と判定する値 |
|---|---|---|---|---|
| `build_split_hip.sh` | `HP` | `HP` | `/opt/rocm-libraries`、相対パス、空白を含む値 | なし。空でない文字列を採用 |
| `build_hip_linux.sh` | `HP` | `HP` | `/opt/rocm-libraries`、相対パス、空白を含む値 | なし。空でない文字列を採用 |

`0`、`1`、`true`、`false`、`0anything` も特別なフラグや数値として解析されず、空でなければパス文字列として使われる。大文字小文字による判定もない。両スクリプトの代入と利用箇所は `tools/packaging/build_split_hip.sh:21,33`、`tools/packaging/build_hip_linux.sh:28,55,92,98-100,109`。

## 有効になる条件

- Linux AMD/HIP 向けの該当ビルドスクリプトを実行したときに限り使われる。HIP エンジンの実行時設定ではない（`tools/packaging/build_split_hip.sh:1-3,17-35`、`tools/packaging/build_hip_linux.sh:1-3,21-29`）。
- `HP` はどちらのスクリプトでも必須。`LIBW` を省略・空にすると `HP` が ROCm ライブラリ root も兼ねる。
- `build_split_hip.sh` では選ばれた root が `CMAKE_PREFIX_PATH` に入る。ライブラリのステージ収集や kpack 検索はこのスクリプトにはない（`tools/packaging/build_split_hip.sh:31-35`）。
- `build_hip_linux.sh` では選ばれた root が CMake prefix に入るだけでなく、`$LIBW/lib` を共有ライブラリ検索 root、`$LIBW/lib/rocblas/library` と `$LIBW/lib/hipblaslt/library` をデータ収集元、`$LIBW` と rocBLAS の配置先を kpack 検索対象として使う。したがって、指定先に必要な構成がない場合は後続の configure・収集・パッケージ工程に影響しうる（`tools/packaging/build_hip_linux.sh:55-56,91-100,109-118`）。
- `CORE` はライブラリ収集時の別の検索 root として参照されるが、`LIBW` の値を上書きしない（`tools/packaging/build_hip_linux.sh:27-28,94-100,109-110`）。

## 実行時の詳細

両スクリプトの起動時にシェルが代入を評価し、その後の当該ビルド処理で同じ値を参照する。実行中にプロセス環境を変更して再評価する仕組みや cache はない。`build_split_hip.sh` は `CMAKE_PREFIX_PATH` を構成して CMake に渡す（`tools/packaging/build_split_hip.sh:17-35`）。`build_hip_linux.sh` は `HIPDEFS` に prefix を入れ、CMake に渡した後、ステージ作成時のライブラリ・データ収集と kpack の探索にも使う（`tools/packaging/build_hip_linux.sh:21-29,52-56,63-65,91-110`）。

`build_hip_linux.sh` は工程結果を `$OUT/build.status` に記録し、configure/build/収集の失敗を `chk` 経由で `ABORT ... failed (rc=...)` と記録して終了する。`LIBW` 固有のエラー文や事前検査はない（`tools/packaging/build_hip_linux.sh:44-47,63-69,97-102`）。`build_split_hip.sh` は `set -eu` のもとで CMake/Ninja などの失敗時に処理を中断し、生成物がない場合など後段の検査では stderr に `build_split_hip.sh: no strata-split-$n` 等を出して終了するが、これらは `LIBW` 固有の診断ではない（`tools/packaging/build_split_hip.sh:17,31-40`）。

## 根拠

- `tools/packaging/build_split_hip.sh:10,17-35` — 使用例、必須の `HP`、`LIBW` の fallback、`CMAKE_PREFIX_PATH` への伝播。
- `tools/packaging/build_hip_linux.sh:11-12,21-29` — 変数の説明と `LIBW` の fallback。
- `tools/packaging/build_hip_linux.sh:52-56,63-65` — HIP 設定と CMake prefix への伝播。
- `tools/packaging/build_hip_linux.sh:91-110` — ライブラリ・データ収集および kpack 検索への使用。
- `tools/packaging/build_hip_linux.sh:44-47,63-69,97-102`、`tools/packaging/build_split_hip.sh:17,31-40` — build の失敗記録・終了経路。
