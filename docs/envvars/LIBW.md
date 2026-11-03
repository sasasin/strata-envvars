# `LIBW`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`LIBW` は Linux AMD (HIP) の配布ビルド用 shell script が、ROCm の library root を指定するために読む環境変数です。`packaging/build_hip_linux.sh` と `packaging/build_dsv41_hip_linux.sh` では CMake に渡す prefix と package 化時の library / kernel data の場所に使い、`packaging/build_split_hip.sh` では split engine 用 CMake の prefix に使います。通常の `strata` / `strata-dsv41` の実行時に読む設定ではありません。

## 値と判定

| 状態 | 3 スクリプト共通の扱い |
|---|---|
| 未設定 | `${LIBW:-$HP}` により `HP` を使う |
| 空文字 | 未設定と同じく `HP` を使う（Bash の `:-` 展開） |
| 非空の値 | 文字列をそのまま `LIBW` に代入し、パスの存在・形式・内容をこの段階では検証しない |

数値変換、正規化、範囲判定、CLI 引数による上書きはありません。`HP` は各スクリプトで必須入力です。`LIBW` が空または未設定の場合の fallback 先であるため、`HP` が未設定なら `set -u` と必須値展開によりスクリプトは `LIBW` の後続処理へ進みません（`packaging/build_hip_linux.sh:22-28`; `packaging/build_split_hip.sh:17-22`; `packaging/build_dsv41_hip_linux.sh:14-20`）。

## 有効になる条件

- Linux HIP の `packaging/build_hip_linux.sh` を実行すると、常に CMake 用 `HIPDEFS` に `$HP;$LIBW$SYSDEPS` を組み立てます。`VISION_ONLY` が非空なら engine build と library collection はスキップしますが、CPU/GPU vision reader の configure にも同じ `HIPDEFS` を渡すため、`LIBW` は引き続き CMake 引数に含まれます。通常の collection は `VISION_ONLY` が空のときだけです（同:53-63,78-91,97-104）。
- このスクリプト内で `DSV41=1` と判定されて DSV41 engine を追加 build する場合も同じ CMake prefix と collector の検索先を使います。別の `packaging/build_dsv41_hip_linux.sh` を直接実行する経路では、DSV41 専用 configure と package collection に使われます（`packaging/build_hip_linux.sh:68-76,97-104`; `packaging/build_dsv41_hip_linux.sh:39-50,61-69`）。
- `packaging/build_split_hip.sh` では split engine の CMake configure に使われます。こちらの script は `set -eu` で実行され、CMake 失敗時は後続の build / 検査へ進みません（同:17-34）。

`SYSDEPS` は `$HP/lib/rocm_sysdeps` が存在するときだけ設定され、prefix 文字列に追加されます。`LIBW` の値が他変数や CLI によって後から選び直される処理はありません。どの CMake module が prefix をどう解釈するかは本変数の Strata 側の処理ではありません。

## 実行時の詳細

各 script の起動時に shell parameter expansion で一度読み、以後は shell 変数として使います。実行中に親の環境値を変更して再読込する箇所はありません。Strata の engine 実行ファイルに値を埋め込んだり、起動時に engine へ渡したりする処理は、`LIBW` の参照全体からは確認できません。

`build_hip_linux.sh` と `build_dsv41_hip_linux.sh` は `LIBW` を含む prefix を CMake に渡し、package collection では `$LIBW/lib` を先頭の `--search` directory として渡します。`build_hip_linux.sh` と `build_dsv41_hip_linux.sh` はさらに `$LIBW/lib/rocblas/library` と `$LIBW/lib/hipblaslt/library` を `--data` 引数として渡します。`build_split_hip.sh` は prefix 以外に `LIBW` を使いません（`packaging/build_hip_linux.sh:28,54-57,98-103`; `packaging/build_split_hip.sh:20-34`; `packaging/build_dsv41_hip_linux.sh:20,40-42,66-68`）。

Strata の shell script は `LIBW` 固有の警告を出しません。`build_hip_linux.sh` / `build_dsv41_hip_linux.sh` では CMake configure と library collection の出力をそれぞれ `cfg*.log` / `collect.log` に送り、コマンドが非 0 なら `build.status` に `ABORT ... failed (rc=...)` を記録して終了します。`build_split_hip.sh` は CMake または後続コマンドの失敗で `set -e` により停止します。無効な path が各外部コマンドでどう扱われるかは、Strata のこの変数処理からは断定できません（`packaging/build_hip_linux.sh:45-48,61-65,101-104`; `packaging/build_dsv41_hip_linux.sh:33-35,46-51,66-69`; `packaging/build_split_hip.sh:17,30-39`）。

## 根拠

- `packaging/build_hip_linux.sh:5-18,22-28` — HIP engine package script の入力説明と `LIBW` の fallback。
- `packaging/build_hip_linux.sh:53-63,78-91,97-104` — CMake prefix の組み立て・reader への適用・`VISION_ONLY` 条件・package collection。
- `packaging/build_split_hip.sh:10,17-22,26-34` — split HIP script の入力説明、fallback、CMake への引き渡し。
- `packaging/build_dsv41_hip_linux.sh:8-20,39-50,61-69` — DSV41 HIP script の入力説明、fallback、configure と collection。

候補名 `LIBW` の Strata 内全参照を確認しました。読み取りは上記 3 shell script に限られ、C++ / HIP engine の実行時読み取りは見つかりませんでした。
