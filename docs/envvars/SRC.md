# `SRC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`SRC` は実行時の Strata 設定ではなく、Linux 向け packaging/build スクリプトがソース checkout のルートを指定するための入力である。`tools/packaging/build_split_hip.sh` と `build_split_cuda.sh` は `$SRC/engine` を CMake のソースディレクトリに渡す。`build_hip_linux.sh` は `$SRC` を作業ディレクトリにし、エンジンと vision reader の構成・ビルド、同梱ファイルの参照に使う（`tools/packaging/build_split_hip.sh:17-35`、`tools/packaging/build_split_cuda.sh:12-26`、`tools/packaging/build_hip_linux.sh:21-25,48-59,63-84,120-140`）。

## 値と判定

3 本の Bash スクリプトはいずれも `SRC=${SRC:-$(cd "$(dirname "$0")/../.." && pwd)}` と評価する。Bash の `:-` 展開なので、未設定と空文字は同じ扱いで、スクリプトの位置から求めた checkout ルートに置き換わる。空でない値は文字列の parse・検証・正規化をせずそのまま使う。したがって `0`、`true`、`0anything`、空白を含むパスも値判定では拒否されず（パスとしての成否は後続コマンド次第）、数値境界や大文字小文字の規則はない（各スクリプトの代入行と、その後の引用されたパス引数: `tools/packaging/build_split_hip.sh:18,31`、`tools/packaging/build_split_cuda.sh:13,23`、`tools/packaging/build_hip_linux.sh:23,58-59`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Linux Bash packaging/build スクリプト | スクリプト位置から checkout ルートを算出 | 空でない任意の文字列（例: `/work/Strata`、`0`、`0anything`）をソースルートとして使用 | `SRC` 自体の無効値判定はない。空文字は無効値扱いではなく既定値へ置換 |

Windows の `tools/packaging/build_vision_windows.bat` と `terminal/tools/hip/build_windows.bat` にも `SRC` というローカル変数名があるが、どちらも `%~dp0` から値を設定している。呼び出し元から渡された `SRC` を読み取る環境入力ではない（`tools/packaging/build_vision_windows.bat:20-25`、`terminal/tools/hip/build_windows.bat:26-33`）。

## 有効になる条件

- 対象はリポジトリ内の Linux packaging/build スクリプトを起動したときだけで、エンジン実行時や CLI/server の設定ではない（各スクリプトの使い方コメント: `tools/packaging/build_split_hip.sh:1-10`、`tools/packaging/build_split_cuda.sh:1-6`、`tools/packaging/build_hip_linux.sh:1-16`）。
- `build_split_hip.sh` と `build_split_cuda.sh` では空でない `SRC` の下に `engine` が必要。指定先は `cmake -S` に渡され、その後の構成・ビルドがそこを使う（`tools/packaging/build_split_hip.sh:31-38`、`tools/packaging/build_split_cuda.sh:23-30`）。
- `build_hip_linux.sh` では指定先に `tools/packaging/shape_build.sh` などの期待する checkout 内容が必要で、`cd "$SRC"` に失敗すると終了コード 1 で停止する（`tools/packaging/build_hip_linux.sh:58-59`）。また `COMMIT` が `unknown` 以外で、`$SRC/.git` と `$SRC/BUILD_ID` がどちらも存在しない場合は `$SRC/BUILD_ID` に commit の先頭 9 文字を書き込む（同: `31,48-50`）。
- ほかの必須入力（例: `B` と `HP`、または `B` と `CUDA`）が不足してもスクリプトは停止するが、それらは `SRC` の判定条件ではない（`tools/packaging/build_split_hip.sh:19-20`、`tools/packaging/build_split_cuda.sh:14-15`）。

## 実行時の詳細

値は各スクリプト冒頭で一度シェル変数 `SRC` に代入され、当該スクリプトの後続処理ではこの値が使われる。環境を実行途中に変更して再読込する処理や cache helper はない（`tools/packaging/build_split_hip.sh:17-18`、`tools/packaging/build_split_cuda.sh:12-13`、`tools/packaging/build_hip_linux.sh:21-24`）。CLI 引数から `SRC` を上書きする処理もない。明示した値はビルド出力先 `B` / `OUT` とは独立で、`SRC` はソース側の基準パスとして使われる。

`build_split_hip.sh` と `build_split_cuda.sh` は、未設定または空のときにスクリプトのディレクトリから 2 階層上を既定ルートとして求める。パスに空白がある場合も代入後の主な参照は引用されている。指定先が誤っている場合、Split 用スクリプトは `set -e` の下で失敗した CMake/Ninja コマンドから停止する。`build_hip_linux.sh` は `set -u` を有効にし、まず `cd` し、構成・ビルドの失敗を `chk` で記録して停止する（`tools/packaging/build_split_hip.sh:17-18,30-40`、`tools/packaging/build_split_cuda.sh:12-13,22-31`、`tools/packaging/build_hip_linux.sh:21,44-47,58-69`）。

## ログと測定値

`SRC` の値を表示する専用ログや警告はない。`build_hip_linux.sh` は作業記録を `$OUT/build.status` に追記し、CMake の設定・ビルド出力を `$OUT/cfg.log`、`$OUT/build.log` などへリダイレクトする。`cd` の失敗は `SRC` 固有の説明文を出さずに終了コード 1 となる（`tools/packaging/build_hip_linux.sh:44-47,58,63-68`）。2 本の Split スクリプトでは CMake/Ninja 等の失敗が標準エラーと終了コードに現れるほか、生成物検査の失敗時には `build_split_hip.sh:40-54`、`build_split_cuda.sh:31-35` にある固定文言を出すが、これらは `SRC` の値そのものを診断するログではない。

## 根拠

- `tools/packaging/build_split_hip.sh:17-18,30-40` — 既定値、必須入力、CMake へのソースルート引き渡しと後続 build。
- `tools/packaging/build_split_cuda.sh:12-13,22-31` — 既定値、CMake への引き渡し、後続 build。
- `tools/packaging/build_hip_linux.sh:21-25,31,44-59,63-84,120-140` — 既定値、条件付き `BUILD_ID` 書き込み、作業ディレクトリ、ビルドと packaging のパス。
- `tools/packaging/build_vision_windows.bat:20-25,37,54`、`terminal/tools/hip/build_windows.bat:26-33,77-84` — 同名変数はスクリプト位置から設定され、呼び出し元の `SRC` を読まない。
