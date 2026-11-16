# `SRC`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`SRC` は Strata 本体の実行時設定ではなく、Linux 向け packaging 用 shell script がビルド対象の Strata checkout のルートを指定するために読む。`packaging/build_split_cuda.sh`、`packaging/build_split_hip.sh`、`packaging/build_hip_linux.sh` の3本で参照される。どのスクリプトでも、選ばれたパスを CMake のソースディレクトリに渡す。HIP の2本はその後も `SRC` を `cd`、相対ファイルの参照や出力先に使う（`packaging/build_split_cuda.sh:13,23`、`packaging/build_split_hip.sh:18,31`、`packaging/build_hip_linux.sh:23,50,58-59,63`）。

## 値と判定

各スクリプトは Bash の `${SRC:-既定値}` を使う。この形式では未設定または空文字のとき既定値となり、非空文字列はそのまま採用される。パスとしての検証、正規化、空白除去は `SRC` の代入時には行われない（`packaging/build_split_cuda.sh:13`、`packaging/build_split_hip.sh:18`、`packaging/build_hip_linux.sh:23`）。

| 条件（script） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux CUDA split / HIP split / HIP package | `$(cd "$(dirname "$0")/.." && pwd)` | 非空の checkout パス。例: `/work/Strata` | 空文字は設定値として使われず既定値に戻る。存在しないパスや Strata 以外のパスも代入段階では拒否されないが、後続コマンドが失敗し得る |

値の大文字小文字や数値としての妥当性は判定しない。`SRC` に空白を含むパスは代入後は引用されて利用されるが、値自体を検査する処理はない。`SRC` に関する CLI 引数や別環境変数との優先順位はなく、3本のスクリプトでは `SRC` が非空なら環境値、未設定または空ならスクリプト位置から計算した既定値を使う（同上）。

## 有効になる条件

- `SRC` が使われるのは、上記の Linux packaging script を起動した場合に限られる。Strata engine の通常実行や Windows packaging の外部設定として読む箇所は見つからなかった。
- `build_split_cuda.sh` はさらに `B` と `CUDA`、`build_split_hip.sh` は `B` と `HP`、`build_hip_linux.sh` は `VARIANT` と `HP` を要求する。これらがない場合、それぞれの script の必須変数展開が処理を止める（`packaging/build_split_cuda.sh:14-15`、`packaging/build_split_hip.sh:19-20`、`packaging/build_hip_linux.sh:22,26`）。
- パスが不正または必要なソースツリーを含まない場合の専用 `SRC` エラー処理はない。後続の `cmake`、`cd`、`. "$SRC/packaging/shape_build.sh"` などの失敗として現れる（`packaging/build_split_cuda.sh:23`、`packaging/build_split_hip.sh:31`、`packaging/build_hip_linux.sh:58-65`）。
- `packaging/build_vision_windows.bat` と `tools/hip/build_windows.bat` は `SRC` を環境から読むのではなく、それぞれ `%~dp0` からローカル変数として設定する（`packaging/build_vision_windows.bat:20,25`、`tools/hip/build_windows.bat:25-32`）。

## 実行時の詳細

値は各 shell script の冒頭で一度展開され、代入後の `SRC` は CMake の `-S` 引数や shell のパス引数として使われる（`packaging/build_split_cuda.sh:13,23`、`packaging/build_split_hip.sh:18,31`、`packaging/build_hip_linux.sh:23,50,58-59,63`）。

CUDA split script は `SRC` を CMake のソースパスにのみ使用する。HIP split script も CMake の `-S` に渡す。HIP package script はさらに `SRC/.git` と `SRC/BUILD_ID` を調べ、条件を満たす場合は `BUILD_ID` を書き、`SRC` に移動して `packaging/shape_build.sh` を読み込む。この処理は `SRC` の指す checkout にファイルを書き込む場合がある（`packaging/build_hip_linux.sh:48-50,58-59`）。

## ログと測定値

`SRC` の値自体を表示する専用ログや警告は確認できなかった。ビルド失敗時は各後続コマンドのエラー経路となる。`build_split_cuda.sh` と `build_split_hip.sh` は生成バイナリが見つからない場合にそれぞれ `build_split_cuda.sh: no strata-split-$n`、`build_split_hip.sh: no strata-split-$n` を stderr に出して終了するが、これらは `SRC` の検証ログではない（`packaging/build_split_cuda.sh:29-31`、`packaging/build_split_hip.sh:38-40`）。性能測定値は該当しない。

## 根拠

- `packaging/build_split_cuda.sh:6,13-16,23` — 使用例、既定値、CMake への引き渡し。
- `packaging/build_split_hip.sh:10,18-23,31` — 使用例、既定値、CMake への引き渡し。
- `packaging/build_hip_linux.sh:9,23-26,48-50,58-65` — 使用例、既定値、checkout 内の参照・書き込みと CMake 呼び出し。
- `packaging/build_vision_windows.bat:20-25`、`tools/hip/build_windows.bat:25-32` — `SRC` を環境から読まず、スクリプト位置をもとに設定。
