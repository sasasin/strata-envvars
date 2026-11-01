# `BUILD_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`BUILD_DIR` は Strata の通常のモデル実行時設定ではなく、同梱された SYCL/HIP ビルドスクリプトで CMake のビルドディレクトリを指定する環境変数です。SYCL、Linux HIP の DeepSeek-V4.1 用ビルド、Windows HIP の DeepSeek-V4.1 用ビルド、および Windows HIP エンジンのビルドで参照されます。生成済みエンジンが実行時にこの変数を読む箇所は、調査した Strata ソース内では確認できません。

## 値と判定

値は数値や真偽値として parse されず、パス文字列として使われます。存在確認や正規化などの独自検証もありません。

| スクリプト | 未設定または空文字 | 非空の値 |
|---|---|---|
| `sycl/tools/build.sh` | `REPO` の値（未設定なら `git rev-parse --show-toplevel` の結果）に `/build-sycl` を付けたパス | そのまま `b` に代入し、CMake の `-B`、build、ログ出力先に使う |
| `tools/dsv41/build_hip_linux.sh` | スクリプトが求めたリポジトリルートに `/build-dsv41-hip` を付けたパス | そのまま `B` に代入し、CMake の `-B` と build に使う |
| `tools/dsv41/win/build_hip_win.bat` | `%SRC%\build-dsv41-hip` | そのまま `BUILD_DIR` に設定し、CMake の `-B` と build に使う |
| `tools/hip/build_windows.bat` | `%SRC%\build-hip-win` | そのまま `BUILD_DIR` に設定し、CMake の `-B`、build、パッケージ入力に使う |

Bash の `${BUILD_DIR:-default}` は未設定と空文字の両方で既定値を選びます。Windows バッチの `if not defined BUILD_DIR` も未定義または空のとき既定値を設定します。空白だけの値は空ではない値として扱われ、空白・不正なパスの拒否や代替はありません。値の範囲や境界値はありません。

SYCL スクリプトは変数を引用符なしで CMake・build・ログの各コマンドに展開するため、空白を含むパスはシェルで分割され得ます。他の3スクリプトでは該当するパス展開を引用符で囲んでいます。

## 有効になる条件

- SYCL 用スクリプトを実行した場合に使われます。既定値の親パスは `REPO` が指定されていればその値、なければ Git が返す作業ツリーのトップです。CLI 引数は build target を指定しますが、`BUILD_DIR` を上書きしません（`sycl/tools/build.sh:37-43`）。
- Linux の DeepSeek-V4.1 HIP スクリプトでは、OS・backend の条件は Linux/HIP のスクリプト実行自体で決まり、`BUILD_DIR` は出力先を選びます。CLI 引数は build target を選択し、出力先の優先順位には入りません（`tools/dsv41/build_hip_linux.sh:9-14,19-27`）。
- Windows の DeepSeek-V4.1 HIP スクリプトと Windows HIP エンジンビルドでは、同じ環境変数名に対してそれぞれ異なる既定パスを設定します。CLI 引数は前者の build target、後者の `tests` モードを選び、どちらも `BUILD_DIR` の設定値は変更しません（`tools/dsv41/win/build_hip_win.bat:15-18,34-43`; `tools/hip/build_windows.bat:30-34,72-85`）。
- 選択したディレクトリに既に `build.ninja` があると、これらのスクリプトは CMake の初回 configure を省略して既存ビルドの設定を使います。変数自体は設定を更新しません（`sycl/tools/build.sh:39-42`; `tools/dsv41/build_hip_linux.sh:19-27`; `tools/dsv41/win/build_hip_win.bat:34-43`; `tools/hip/build_windows.bat:72-85`）。

## 実行時の詳細

各スクリプトの開始時に環境変数をローカルの `b` または `B` に取り込むか、Windows バッチ内で既定値を設定します。そのパスは CMake の `-B` で configure 対象に選ばれ、`cmake --build` の対象にもなります。Windows HIP エンジンのスクリプトでは、その配下の llama.cpp checkout を既定探索先にし、最後に `package_windows.py --build` へ渡します（`tools/hip/build_windows.bat:89-95,113-115`）。プロセス起動後に環境変数を変更して再評価する仕組みはありません。

未設定・空文字が既定値になる以外に優先順位の分岐はありません。build target や `tests` の CLI 選択、`REPO`、他の環境変数はビルド内容や既定値の親を決めますが、非空の `BUILD_DIR` を上書きしません。

不正なパスに対する `BUILD_DIR` 固有の警告やエラー処理はありません。失敗は後続コマンドに現れます。SYCL スクリプトは `build.log` に build 出力を記録し、`BUILD EXIT <status>` と `errors: <count>` を出力します（`sycl/tools/build.sh:43-50`）。Linux HIP の DeepSeek-V4.1 ビルドは `set -e` で失敗したコマンド時に終了し、成功時は `built in <path>` を出力します（`tools/dsv41/build_hip_linux.sh:9,19-28`）。Windows の DeepSeek-V4.1 HIP スクリプトは `BUILD-EXIT <status>` を表示します（`tools/dsv41/win/build_hip_win.bat:43-45`）。Windows HIP エンジンビルドは configure・build・package の失敗時に終了コード 1 で抜け、完了時に zip の出力先を表示します（`tools/hip/build_windows.bat:72-85,113-117`）。

## 根拠

- SYCL の既定値、configure/build への適用、ログ: `sycl/tools/build.sh:37-50`。既存ビルドは cache を維持する旨も同ファイル `:41-42` にあります。
- Linux HIP / DeepSeek-V4.1: `tools/dsv41/build_hip_linux.sh:9-28`。
- Windows HIP / DeepSeek-V4.1: `tools/dsv41/win/build_hip_win.bat:11-18,34-45`。
- Windows HIP エンジンと package への引き渡し: `tools/hip/build_windows.bat:24-34,69-85,89-95,113-117`。
- SYCL 利用例は `docs/INTEL.md:68-83` および `docs/INTEL_ARC.md:67-74` にあります。これはスクリプトの使い方の説明であり、判定規則は上記実装に基づきます。

候補一覧の同名表記には、環境変数ではない用法も含まれます。`packaging/build_dsv41_windows.bat` の `BUILD_DIR` は第1位置引数を示す文書上の名前で、実装は `%~1` を `BD` に読みます（`packaging/build_dsv41_windows.bat:5-11,20`）。また `CMakeLists.txt` の `STRATA_ORACLE_BUILD_DIR` は別名の CMake cache 設定です（`CMakeLists.txt:655-674`）。これらを環境変数 `BUILD_DIR` の読み取り箇所には数えていません。
