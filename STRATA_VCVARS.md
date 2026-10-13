# `STRATA_VCVARS`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Windows で Strata のエンジンまたは画像エンコーダーをソースからビルドするとき、`vcvars64.bat` の自動検出を上書きするパスです。`setup.py` の `find_vcvars()` がこの変数を読みます。環境変数が指定されていて指すパスが存在すれば、そのパスを MSVC のビルド環境を準備するバッチとして使います。

これは setup 時のビルド選択であり、ビルド済み Strata エンジンの実行時動作を変える読み取り箇所は確認できませんでした。候補名の全リポジトリ検索では、製品コードでの直接読み取りは `setup.py:1399` のみです。テストコードにも使用例がありますが、挙動の根拠にはしていません。

## 値と判定

Python の `os.environ.get("STRATA_VCVARS")` で読み、文字列としてパスに渡します。値の trim、正規化、`.bat` 拡張子やファイル種別の検証はありません。

| 値 | 判定と結果 |
|---|---|
| 未設定 | `vswhere.exe` による自動検出へ進む |
| 空文字 | Python では falsy のため、未設定と同じく自動検出へ進む |
| 空でない文字列で、そのパスが存在する | `Path(value)` を返し、自動検出を行わない |
| 空でない文字列で、そのパスが存在しない | `None` を返す。自動検出へは戻らない |

空白だけの値も空文字ではないため手動指定として扱われます。存在確認は `Path.exists()` のみで、ファイルであることや実行可能性は検査しません。手動指定パスには、後述の `vswhere` に対する CUDA バージョン範囲も適用されません。

## 有効になる条件

- `find_vcvars()` の結果を利用するのは Windows のビルド経路です。Linux では CUDA ビルド準備時に `find_vcvars()` を呼ばず、C++ コンパイラーとして `g++` を確認します。
- CUDA エンジンのビルドでは `find_vcvars(cuda_v)` が使われます。手動指定がない場合、`cuda_v` が指定されると `vswhere` に範囲 `[16.0,18.0)`（CUDA 13.3 未満。CUDA 13.0〜13.2を含む）または `[16.0,19.0)`（CUDA 13.3 以降）を要求します。`cuda_v is None` の場合はバージョン範囲を指定しません。
- HIP エンジンに付随する CPU 画像エンコーダーのビルドでも、Windows なら `find_vcvars()` を引数なしで呼びます。この経路では CUDA のバージョン制限はありません。
- 手動指定したパスが見つからない場合、CUDA ビルド準備では Visual Studio の C++ ツールがないものとしてインストール案内・再確認の対象になります。最終的にビルド時にも MSVC 環境がなければエラーになります。CPU 画像エンコーダーの直接ビルドでは `cmake_build()` が同じくパス未検出エラーを出します。

## 実行時の詳細

自動検出では、`ProgramFiles(x86)` が設定されていればその値、未設定なら `C:\Program Files (x86)` を基点に `Microsoft Visual Studio/Installer/vswhere.exe` を探します。`vswhere` がなければ `None` です。存在する場合は `-latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath` を実行し、CUDA の条件があるときは前述の `-version` 範囲を加えます。得たインストール先の `VC/Auxiliary/Build/vcvars64.bat` が存在するときだけ返します。

CUDA ビルドでは `install_build_tools()` がこの結果を使って C++ ツールの有無を判定し、エンジンと画像エンコーダーのビルドに渡します。`cmake_build()` は Windows で `vcvars` が `None` なら `the Visual Studio C++ build tools were not found` で失敗します。値があれば setup が生成する `.bat` ファイルから `call "<vcvars のパス>" >nul` を実行してから CMake の configure/build を実行します。HIP の CPU 画像エンコーダー経路も、Windows では同様にこのバッチを経由します。

値は `find_vcvars()` の呼び出しごとに読み直され、関数内にキャッシュされません。ただし、この読み取りは setup プロセスのビルド準備中に限られます。生成されたビルド用バッチには選ばれたパスが書かれます。

## 文書との照合

`docs/INSTALL.md` は Windows で Visual Studio Build Tools と CUDA Toolkit を使い、必要なら setup がビルドツールを導入してエンジンをコンパイルすると説明しています（27–28行）。`STRATA_VCVARS` による手動パス指定の説明は同文書には見当たりません。現行実装では、手動指定が自動検出より優先され、指定パスの存在だけを確認します。

## 根拠

- 値の読み取り、自動検出、CUDA バージョン条件: `setup.py:1390-1415`
- Windows の CPU 画像エンコーダービルドからの呼び出し: `setup.py:2697-2705`
- CUDA ビルド準備での検出・利用と再確認: `setup.py:3211-3240,3246-3258,3279-3286`
- Visual Studio 環境を呼んで CMake を実行する処理: `setup.py:3289-3307`
- CUDA エンジンと画像エンコーダーのビルドへの引き渡し: `setup.py:3410-3433`
- セットアップでのビルドツールの説明: `docs/INSTALL.md:23-28`
