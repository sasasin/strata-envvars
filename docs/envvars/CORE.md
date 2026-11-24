# `CORE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`CORE` は `tools/packaging/build_hip_linux.sh` が AMD HIP engine component をパッケージ化するときに使う、ROCm core root のパス指定です。Strata の実行ファイルが読む実行時設定ではありません。ビルド時の CMake 設定には `HP` と `LIBW` が渡され、`CORE` は後続の共有ライブラリ収集先と `.kpack` 探索先に使われます。したがって、パッケージ内に収集されるファイルが変わり得ますが、この変数でエンジンの計算やモデルの挙動は制御されません。スクリプトの説明・入力と利用箇所は `tools/packaging/build_hip_linux.sh:2-20,23-29,91-110`。

## 値と判定

スクリプトは `CORE=${CORE:-$HP}` と代入します。Bash の `:-` 展開なので、環境変数が未設定または空文字なら `HP` の値を採用し、空でない文字列ならその文字列を採用します。文字列を数値や真偽値として parse せず、パスとして検証・正規化もしません。空白だけの値も空ではないため採用されます。`CORE` が空で `HP` も未設定または空の場合は、先行する `${HP:?...}` がエラーにしてスクリプトを終了します（`tools/packaging/build_hip_linux.sh:26-29`）。

| 条件 | unset | 設定時に採用される値 | 空文字・その他の値 |
|---|---|---|---|
| `build_hip_linux.sh` | `HP` の値を使用 | 空でない値をそのままパスに使用（例: `/opt/rocm/core`） | `CORE=''` は `HP` に fallback。`0`、`true`、前後空白付き文字列も特別扱いせずパス文字列として採用。存在確認は `.kpack` 探索時など個別箇所のみ |

このスクリプトには `CORE` を指定する CLI 引数はありません。CLI による上書きや他設定との優先順位はなく、`CORE` の空・未設定時だけ `HP` が fallback になります（`tools/packaging/build_hip_linux.sh:26-29,94-109`）。

## 有効になる条件

- 対象は Linux AMD HIP 用の `tools/packaging/build_hip_linux.sh` を実行するパッケージ作成経路です。Strata の通常実行、CUDA / SYCL ビルド、サーバー要求ごとに読み取る設定ではありません（`tools/packaging/build_hip_linux.sh:1-4,91-110`）。
- `HP` は必須です。`CORE` が unset / 空なら検索ルートに `HP` が使われます（`tools/packaging/build_hip_linux.sh:26-29`）。
- `CORE` に指定した場所が実在しなくても、共有ライブラリ検索引数 `--search "$CORE/lib"` 自体は渡されます。`$CORE/lib/llvm/lib/$(uname -m)-unknown-linux-gnu` はディレクトリが存在するときだけ追加検索先になります（`tools/packaging/build_hip_linux.sh:94-99`）。
- `.kpack` 探索では `CORE` は候補の一つです。候補は rocBLAS の位置から得るディレクトリ、`HP`、`CORE`、`LIBW` の順です。同じ対象アーカイブが先行候補にもあれば、後続の `CORE` 側コピーは使われません（`tools/packaging/build_hip_linux.sh:108-118`）。

## 実行時の詳細

値はスクリプト起動時の環境からシェル変数に展開され、その後は関数内 `static` などに cache されるのではなく、シェルスクリプトの一回の実行中に各コマンドの引数を組み立てるために使われます。スクリプトは `CORE` の代入後にソースディレクトリへ `cd` し、その後 `$CORE/lib`、LLVM の追加検索ディレクトリ、`$CORE` の `.kpack` を参照します。従って相対パスを指定した場合、これらの参照は `$SRC` を基準に解決されます（`tools/packaging/build_hip_linux.sh:23-29,58-59,94-110`）。

共有ライブラリ収集では `CORE/lib` と、存在する場合の LLVM のアーキテクチャ別ディレクトリが `collect_libs.py` の反復 `--search` 引数になります。子 Python プロセスは `CORE` 自体を読むのではなく、受け取った検索パスを `ldd` 実行時の `LD_LIBRARY_PATH` の前方に組み立てます（`tools/packaging/build_hip_linux.sh:94-101`; `tools/packaging/collect_libs.py:138-151,154-166`）。`CORE` の値はこのスクリプトから実行される `strata` バイナリへ設定値として渡されません。

## ログと測定値

`collect_libs.py` が見つからない非 driver 依存を検出した場合、`WARNING: <binary> needs <library>, which ldd cannot find` を stderr に出します。収集コマンドの stdout / stderr は `$OUT/collect.log` に追記されます。一方、この警告だけでは `collect_libs.py` は失敗終了せず、成功時はコピーしたライブラリ数などを出力して 0 を返します（`tools/packaging/collect_libs.py:177-180,233-238`; `tools/packaging/build_hip_linux.sh:97-101`）。

収集コマンド自体が非 0 で終了すると、`chk` が `$OUT/build.status` に `collected for <binary> rc=<code>` と `ABORT collected for <binary> failed (rc=<code>)` を記録し、ビルドスクリプトを終了コード 1 で止めます（`tools/packaging/build_hip_linux.sh:44-47,97-101`）。ソース資料に `CORE` による性能測定値はありません。

## 根拠

- `tools/packaging/build_hip_linux.sh:2-20,26-29` — 対象スクリプトの用途、ROCm root の説明、未設定・空時の fallback。
- `tools/packaging/build_hip_linux.sh:58-59,91-110` — 参照時の作業ディレクトリ、ライブラリ・LLVM・`.kpack` の検索パス。
- `tools/packaging/build_hip_linux.sh:44-47,97-101` — 収集失敗時の status 記録と終了。
- `tools/packaging/collect_libs.py:138-151,154-166,177-180,233-238` — `--search` の `LD_LIBRARY_PATH` への使用、欠落依存の警告、成功時出力。
