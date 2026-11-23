# `ZSTD_INC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`ZSTD_INC` は、Hy4-Flash の SYCL 実行ファイルを手動ビルドする `engine/src/hy4flash/sycl/build_hy4_sycl.sh` が、zstd のヘッダーディレクトリをコンパイラの `-I` 検索パスに加えるためのビルド時環境変数です。Strata の実行時機能やモデル処理を直接切り替える変数ではありません。スクリプトは既定の include パスを設定した後、`ZSTD_INC` が空でなければ `-I$ZSTD_INC` を追加します（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:42-43`）。

同スクリプトは `strata_reader.cpp` を `g++` でコンパイルします（同 `:52`）。このソースは `<zstd.h>` を include するため、zstd ヘッダーが標準検索先にない環境で、その場所を追加する用途です（`engine/src/artifact/strata_reader.cpp:1-6`）。

## 値と判定

スクリプトは `${ZSTD_INC:-}` を `-n` で検査します。未設定時は空文字に展開され、明示的な空文字も同じく false となって追加の `-I` は付きません。空でない文字列は値の形式・パスの存在・zstd ヘッダーの有無をスクリプト自身では検証せず、`-I` の後ろに加えます（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:42-43`）。

| 条件 | unset | 設定時に追加される値 | 追加されない値 |
|---|---|---|---|
| SYCL ビルドスクリプト実行時 | `-I` は追加されない | 空でない値。例: `/opt/zstd/include`、`0`、`true` | 空文字（`ZSTD_INC=''`） |

比較は空かどうかだけで、大文字小文字、空白、数値としての妥当性は判定しません。値は引用符付きで `INC` に追加されますが、後続の `g++` / `icpx` コマンドでは `$INC` が引用符なしで展開されます。そのためシェルの単語分割が行われ、空白を含むパスは一つの `-I` 引数としては保持されません（同 `:52-57`, `:64-68`）。

## 有効になる条件

- `engine/src/hy4flash/sycl/build_hy4_sycl.sh` を実行していること。このスクリプトの説明する `strata-hy4-sycl` のビルドに限られます（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-6`）。リポジトリ内でこのスクリプトを呼び出す別の箇所は見つからず、手動実行用です。
- `ZSTD_INC` が非空なら、追加した検索パスがスクリプト内の `g++` による各ホストソースのコンパイルと、`icpx` による SYCL ソースのリンクビルドに渡されます（同 `:42-43`, `:52-68`）。
- 値が未設定または空でも、コンパイラの通常のヘッダー検索先に `zstd.h` があれば、この変数による追加パスは不要です。通常の検索先にヘッダーがなく、指定したディレクトリにも見つからない場合、`strata_reader.cpp` の `<zstd.h>` include を含むコンパイルが失敗します。スクリプトは `set -euo pipefail` で実行されるため、失敗したコンパイルコマンドでスクリプトが終了します（同 `:7`, `:52`、`engine/src/artifact/strata_reader.cpp:4`）。
- 既定のライブラリ指定は別変数 `ZSTD_LIBS` が担います。`ZSTD_INC` はリンクライブラリを指定・検証せず、`ZSTD_LIBS` の既定値を上書きしません（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:60`, `:64-68`）。

## 実行時の詳細

値はスクリプト起動後、`INC` を組み立てる時点でシェルにより一度展開されます。実行中に親環境の値を変更して再評価する処理や cache はありません。子プロセスへの環境変数転送ではなく、コンパイラのコマンドライン引数に変換して渡します（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:42-43`, `:52-68`）。

`ZSTD_INC` 自体に関する警告や独自のエラー表示はありません。ヘッダーが解決できない場合はコンパイラが出すエラーを伴って `set -e` により終了します。スクリプト上の明示的な `icpx not found` や不正な `ARCH_MODE` の終了経路は別条件であり、`ZSTD_INC` の値判定によるものではありません（同 `:16-39`）。

## 根拠

- `engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-7` — ビルドスクリプトの目的・引数・シェル失敗設定。
- `engine/src/hy4flash/sycl/build_hy4_sycl.sh:42-68` — 値の判定、`-I` 追加、コンパイラへの受け渡し、別変数 `ZSTD_LIBS` の既定。
- `engine/src/artifact/strata_reader.cpp:1-6` — コンパイル対象が必要とする zstd ヘッダー。
