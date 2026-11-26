# `SYMBOLS_DIR`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（`2026-11-26` 時点）。

## 役割

Strata の実行時設定ではなく、リリース用ビルドスクリプトがデバッグシンボルの保存先を指定する変数です。Linux の CUDA（x86_64 / AArch64）、HIP、SYCL、macOS Metal の各パッケージ作成スクリプトは共通 helper に値を渡し、Windows CUDA のビルドスクリプトは同じ目的の保存先を組み立てます。シンボルはパッケージの外に保存され、通常の Strata 実行ファイルがこの変数を読む箇所はありません（`tools/packaging/symbols_build.sh:15-20`、`tools/packaging/build_cuda_windows.py:185-189`）。

## 値と判定

| 読み取り経路 | 未設定・空文字 | 非空の設定値 | 形式検査・無効値 |
|---|---|---|---|
| POSIX shell helper | `${SYMBOLS_DIR:-$_sk_repo/symbols}` により、未設定と空文字は対象 checkout の `symbols` を使う | 値をそのまま保存先の親ディレクトリとして使い、その下にパッケージ名を追加する | 値の parse、空白除去、相対パスの解決、書き込み可能性の事前検査はない。`0`、`true`、空白だけの値もパスとして扱う |
| Windows CUDA Python | `os.environ.get("SYMBOLS_DIR") or src / "symbols"` により、未設定と空文字は `src/symbols` を使う | `Path` に渡し、その下にパッケージ名を追加する | 真偽値による未設定相当の判定以外に形式検査や正規化はない。非空文字列は値の内容にかかわらずパスとして扱う |

したがって、値を有効化する特別な文字列や数値境界はありません。シェル経路では引用されたパスとして展開され、Windows 経路では `Path` が解釈します。相対パスは各プロセスの作業ディレクトリを基準にします（各 Unix ビルドスクリプトは helper 呼び出し前に checkout へ `cd` します。`tools/packaging/build_cuda_linux.sh:37-40`、`tools/packaging/build_sycl_linux.sh:40-42`、`tools/packaging/mac/build_engine.sh:54-57`）。

## 有効になる条件

- `SYMBOLS_DIR` は配布ビルド用のシンボル保存処理が走るときだけ使われます。参照する経路は Linux CUDA x86_64（`tools/packaging/build_cuda_linux.sh:40,74-75`）、Linux CUDA AArch64（`tools/packaging/build_cuda_linux_aarch64.sh:29-38`）、Linux HIP（`tools/packaging/build_hip_linux.sh:60,125-128`）、Linux SYCL（`tools/packaging/build_sycl_linux.sh:40-42,71`）、macOS Metal（`tools/packaging/mac/build_engine.sh:56-57,78-84`）、Windows CUDA（`tools/packaging/build_cuda_windows.py:185-189,202-207`）です。
- POSIX helper は `STRATA_KEEP_SYMBOLS` が文字列 `0` のとき `sym_cmake` を空にし、`symbols_keep` が何もせず戻るため、`SYMBOLS_DIR` を展開しません。未設定・空文字は既定の `1` と同じくシンボル収集を有効にし、`0` 以外の文字列も無効化しません（`tools/packaging/symbols_build.sh:12-19`）。Windows CUDA は `os.environ.get("STRATA_KEEP_SYMBOLS", "1") != "0"` で判定するため、未設定・空文字・`0` 以外は収集を有効にします。無効時も保存先 `Path` 自体は先に計算しますが、シンボル収集には使いません（`tools/packaging/build_cuda_windows.py:83-85,185-189`）。
- `SYMBOLS_DIR` が指定されていても、シンボル収集のビルド条件が満たされなければ保存処理は成功しません。Linux / macOS は helper が `-DSTRATA_KEEP_SYMBOLS=ON` を CMake に渡し、Windows は同設定を configure と vision ビルドに渡します（`tools/packaging/symbols_build.sh:12-13`、`tools/packaging/build_cuda_windows.py:68-80,202-207`）。
- CLI 引数や別の保存先設定による `SYMBOLS_DIR` の上書きはありません。呼び出し側はパッケージ名を加えた保存先を helper または `keep_symbols.py --out` に渡します。

## 実行時の詳細

ここでいう「実行時」はビルドスクリプトの実行時です。POSIX shell では `symbols_build.sh` を source したときに `STRATA_KEEP_SYMBOLS` を読み、`SYMBOLS_DIR` は `symbols_keep` 呼び出し時に展開します。関数は `keep_symbols.py` を起動して `--out <保存先>/<パッケージ名>` を渡します（`tools/packaging/symbols_build.sh:12-20`）。Windows CUDA は `main` 内でビルド後に `SYMBOLS_DIR` を読み、パッケージ名を加えた `Path` を作って、engine と vision のシンボル収集に使います（`tools/packaging/build_cuda_windows.py:158-185,186-207`）。いずれも対象の保存先をプロセス内で一度決めて後続処理に渡し、Strata エンジンの起動後に読み直すものではありません。

保存先のディレクトリ作成は `keep_symbols.py` の ELF / PE / Mach-O 処理内で行います（`tools/packaging/keep_symbols.py:105-108,182-185,246-249`）。変数値の検証や既定先への fallback はなく、保存先を作成できない場合はシンボル処理が失敗します。Unix 側は呼び出し元のシェルスクリプトが失敗を扱い、HIP は `build.status` に出力を追記して `chk` で異常終了します（`tools/packaging/build_hip_linux.sh:128`）。Windows 側は子プロセスの失敗を `run` が検出してビルドを失敗させます（`tools/packaging/build_cuda_windows.py:152-155,188-189`）。

## ログと測定値

`SYMBOLS_DIR` 固有のログや測定値はありません。シンボル収集が成功すると helper は `kept <binary> -> <保存先> ...` を出力し、必要なデバッグ情報がない場合は `no debug information`（ELF）、`no CodeView record`（PE）、または `dsymutil produced no DWARF (built without -g?)`（Mach-O）を出力して、`--require` により失敗します（`tools/packaging/keep_symbols.py:115-119,129-132,191-196,221-225,251-265,267-270`）。Unix HIP 経路ではこれらの出力は `$OUT/build.status` に追記されます（`tools/packaging/build_hip_linux.sh:128`）。

## 根拠

- 共通 shell helper の有効化判定、早期 return、保存先引数: `tools/packaging/symbols_build.sh:12-20`
- Windows CUDA の環境変数判定・保存先・シンボル収集呼び出し: `tools/packaging/build_cuda_windows.py:83-85,181-189,202-207`
- Linux CUDA / SYCL の helper 使用と保存処理: `tools/packaging/build_cuda_linux.sh:37-40,74-75`、`tools/packaging/build_sycl_linux.sh:40-42,71`
- Linux CUDA AArch64 と HIP の保存処理: `tools/packaging/build_cuda_linux_aarch64.sh:29-38`、`tools/packaging/build_hip_linux.sh:60,125-128`
- macOS Metal の helper 使用と保存処理: `tools/packaging/mac/build_engine.sh:54-57,78-84`
- 出力先作成、ログ、`--require` による失敗: `tools/packaging/keep_symbols.py:105-132,182-225,246-270`
