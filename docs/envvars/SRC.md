# `SRC`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`SRC` は、Linux 向けの Strata engine / 補助 engine のビルド用シェルスクリプトが、ソース checkout の場所を指定するために読む環境変数です。対象は `packaging/build_hip_linux.sh`、`packaging/build_dsv41_hip_linux.sh`、`packaging/build_dsv41_cuda.sh`、`packaging/build_split_cuda.sh`、`packaging/build_split_hip.sh` です。通常の Strata engine 実行時の設定ではありません。

これらのスクリプトは、値を CMake のソースディレクトリに渡すか、そのディレクトリへ移動してビルドを開始します。`build_hip_linux.sh` は同じ checkout 内の `tools/vision` もビルドします。ソースパスが変わるため、tarball checkout で `COMMIT` を指定している一部の経路では、その checkout の `BUILD_ID` へ build ID を書き込みます（下記「有効になる条件」参照）。

## 値と判定

5 スクリプトとも Bash の `SRC=${SRC:-$(cd "$(dirname "$0")/.." && pwd)}` をスクリプト開始時に評価します（`packaging/build_hip_linux.sh:22-24`、`packaging/build_dsv41_hip_linux.sh:14-17`、`packaging/build_dsv41_cuda.sh:13-17`、`packaging/build_split_cuda.sh:12-16`、`packaging/build_split_hip.sh:17-22`）。

| 入力 | 採用値・結果 |
|---|---|
| unset | 実行中スクリプトの `packaging/` の親ディレクトリを `pwd` で求めたパス |
| 空文字 | unset と同じ既定パス（`:-` は未設定と空文字の両方で右辺を使う） |
| 非空文字列 | 渡された文字列をパスとしてそのまま使う |

文字列を数値や真偽値に変換せず、空白除去・存在確認・絶対パス化も共通処理としては行いません。相対パスはスクリプトを起動した作業ディレクトリ基準です。値はスクリプト内で一度シェル展開され、実行中に環境値を変えても再評価されません。CLI の `SRC` 引数はありません。ほかの build 変数（`B`、`CUDA`、`GG`、`HP`、`LLAMA` 等）は各スクリプトで別途要求・設定されます。

## 有効になる条件

- 適用先は前記 5 つの Linux packaging build script を実行したときだけです。CUDA 系では `cmake -S "$SRC"` に渡されます（`packaging/build_dsv41_cuda.sh:27-32`、`packaging/build_split_cuda.sh:21-25`）。HIP split も同様です（`packaging/build_split_hip.sh:29-34`）。HIP engine / DSV41 は `cd "$SRC"` した後、CMake のソースとして `.` を使います（`packaging/build_hip_linux.sh:58-63`、`packaging/build_dsv41_hip_linux.sh:43-48`）。
- 変数自身に backend や GPU 判定はありません。どのビルドを行うかは実行したスクリプトで決まり、各スクリプトが CUDA または HIP の CMake オプションを指定します。通常の engine 起動、CLI、サーバーの設定には読み取り箇所がありません。
- `packaging/build_dsv41_cuda.sh` は `$SRC/.git` も `$SRC/BUILD_ID` もない場合、非空の `COMMIT` を要求します。なければ stderr に `build_dsv41_cuda.sh: $SRC has no .git and no BUILD_ID: set COMMIT=<hex> so the engine can print its commit` と出して終了コード 2 です（同ファイル 23-25 行）。`COMMIT` がある場合は先頭 9 文字を `$SRC/BUILD_ID` に書きます。
- `packaging/build_hip_linux.sh` と `packaging/build_dsv41_hip_linux.sh` は、`COMMIT` が既定値 `unknown` でなく、かつ `$SRC/.git` と `$SRC/BUILD_ID` が両方ない場合に、先頭 9 文字を `$SRC/BUILD_ID` に書きます（`packaging/build_hip_linux.sh:31,49-51`、`packaging/build_dsv41_hip_linux.sh:23,36-37`）。これらのスクリプトは `cd "$SRC" || exit 1` を使い、移動に失敗すると終了します（`packaging/build_hip_linux.sh:58-59`、`packaging/build_dsv41_hip_linux.sh:43-44`）。
- ほかのパス検査や CMake 設定の成否は各 build script / CMake の処理に委ねられます。`SRC` 専用の clamp、fallback、優先順位上書きはありません。

## 実行時の詳細

環境からの読み取りは各シェルスクリプトの冒頭で一度行われる build-time の選択です。値は CMake の `-S` に渡されるか、`cd` の対象となります。エンジン起動時の設定として `SRC` を明示的に転送する処理はありません（起動元から受け継いだ環境変数が build 子プロセスに継承される場合はあります）。`build_hip_linux.sh` では選択した checkout から engine を構成し、`VISION_ONLY` が空の場合には `strata`（必要なら DSV41）も構成します（`packaging/build_hip_linux.sh:60-80`）。`SRC` が不正な場合、明示的なディレクトリ移動のある HIP engine / DSV41 スクリプトは終了コード 1 で止まり、他のスクリプトは CMake がソースパスを処理する段階で失敗し得ます。

同じ名前は `tests/dsv41/build_dq_test.sh:7-17` にもありますが、これはテスト専用ビルド補助です。候補一覧に現れるその他の `SRC` は、スクリプトが環境値を参照して代入するケースではなく、Windows batch が checkout パスを設定し直す箇所や、Python のローカル変数・CLI の `SRC=DEST` 表記等でした（例: `packaging/build_vision_windows.bat:25`、`tools/hip/build_windows.bat:26`）。それらを環境変数の読み取りとは扱っていません。

## 根拠

- 既定値と未設定・空文字時の分岐: `packaging/build_hip_linux.sh:22-24`、`packaging/build_dsv41_hip_linux.sh:14-17`、`packaging/build_dsv41_cuda.sh:13-17`、`packaging/build_split_cuda.sh:12-16`、`packaging/build_split_hip.sh:17-22`。
- ソースパスの CMake / 作業ディレクトリへの適用: `packaging/build_dsv41_cuda.sh:27-32`、`packaging/build_split_cuda.sh:21-25`、`packaging/build_split_hip.sh:29-34`、`packaging/build_hip_linux.sh:58-63,79-86`、`packaging/build_dsv41_hip_linux.sh:43-48`。
- tarball の build ID 処理と失敗経路: `packaging/build_dsv41_cuda.sh:23-25`、`packaging/build_hip_linux.sh:49-51,58-59`、`packaging/build_dsv41_hip_linux.sh:36-37,43-44`。
