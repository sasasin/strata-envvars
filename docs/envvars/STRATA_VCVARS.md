# `STRATA_VCVARS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Windows で Strata のセットアップ処理が C++ ビルドに使う Visual Studio の `vcvars64.bat` を手動指定する変数。`terminal/setup.py` の `find_vcvars()` が値を読み、設定された既存パスを自動の `vswhere` 探索より優先する。エンジン実行時の設定ではなく、セットアップ時のビルドツール選択に使われる（`terminal/setup.py:2674-2687`, `terminal/setup.py:6624-6629`）。

## 値と判定

Python の `os.environ.get("STRATA_VCVARS")` で文字列を取得し、文字列が truthy なら `Path(override).exists()` だけを確認する。値の正規化、ファイル種別、バッチの内容、Visual Studio/CUDA との互換性はこの override 分岐では検査しない。未設定または空文字列は自動探索へ進む。空白だけの文字列は truthy なので、その文字列をパスとして検査し、通常は存在せず `None` になる。パス比較の大小文字変換や環境変数値の trim は行わない（`terminal/setup.py:2683-2687`）。

| 条件 | unset | 設定時に受理される値 | 無効になる値 |
|---|---|---|---|
| Windows のセットアップ呼び出し | `vswhere` による自動探索へ進む | 空でない文字列で、`Path` が指すパスが存在すればその `Path` を返す。例: 存在する `.../vcvars64.bat` | 空文字列は unset と同じ。存在しないパスは `None` を返し、自動探索へは戻らない。例: `missing.bat`、存在しない空白パス |
| 非 Windows | 本番の呼び出し側が `find_vcvars()` を呼ばず `None` を渡す | 通常のセットアップ経路では読み取られない | 該当なし |

数値・真偽値としては解釈しない。`1`、`true`、`false`、`0anything` も、同名のパスが存在する場合だけ受理されるパス文字列であり、存在しなければ override の結果は `None`。値が設定されているだけで有効になるわけではない（`terminal/setup.py:2683-2687`, `terminal/setup.py:111`）。

## 有効になる条件

- `WIN` が真（`os.name == "nt"`）のセットアップで、C++ ビルド用に `find_vcvars()` が呼ばれること（`terminal/setup.py:111`, `terminal/setup.py:5790-5793`, `terminal/setup.py:5932-5957`, `terminal/setup.py:6624-6629`）。
- override が空でない場合、そのパスが存在すること。存在しない override は自動探索を抑止して `None` となる（`terminal/setup.py:2683-2687`）。
- 選択した値が `cmake_build()` に渡るビルド経路であること。Windows の CUDA エンジン、CPU 画像エンコーダー、画像生成器などのセットアップビルドが該当する（`terminal/setup.py:5790-5793`, `terminal/setup.py:5922-5957`, `terminal/setup.py:6933-6965`）。
- 通常のセットアップ実行で使われる。ソース上の直接参照は `terminal/setup.py` のみで、エンジンの実行時設定や Strata サーバーモードから読む箇所はない。

override が存在すれば、`find_vcvars(cuda_v)` は CUDA バージョンに応じた `vswhere` の Visual Studio バージョン絞り込みを通らず、そのまま返す。自動探索では CUDA 13.0–13.2 用に `[17.0,18.0)`、CUDA 13.3 以降用に `[17.0,19.0)` を `vswhere` に渡す一方、CUDA なしの呼び出しではバージョン範囲を付けない（`terminal/setup.py:2690-2699`）。したがって、指定パスが存在することは、その構成でコンパイル可能であることの保証ではない。

## 実行時の詳細

`find_vcvars()` は呼び出しごとに環境を読み直し、結果を cache しない。プロセス起動後に環境を変更すれば以後の呼び出しには反映されるが、すでに返された値や開始済みビルドには遡及しない（`terminal/setup.py:2674-2687`）。CLI のセットアップ経路がビルド対象を選び、Windows では CUDA ビルドツール確認（`install_build_tools()`）、画像エンコーダー、画像生成器などからこの関数を呼ぶ（`terminal/setup.py:5790-5793`, `terminal/setup.py:5900-5957`, `terminal/setup.py:6604-6652`, `terminal/setup.py:6683-6690`）。

選択されたパスは `cmake_build()` に渡され、Windows ではセットアップが一時的な `.bat` を書き、`call "<vcvars>" >nul` の後に CMake configure/build を実行する（`terminal/setup.py:6793-6815`）。`find_vcvars()` 自体は override の不在・無効を警告しない。値が `None` のまま Windows ビルドに到達すると、`cmake_build()` が `the Visual Studio 2022 C++ build tools were not found (Visual Studio 2019 is too old: the sources are C++20)` と表示し、`fail()` がセットアップを終了コード 1 で止める（`terminal/setup.py:6805-6809`, `terminal/setup.py:1049-1056`）。CUDA のツール確認経路では、その前に不足ツールとして扱われ、インストールを尋ねるか、処理後に `the C++ build tools did not install` で停止する場合もある（`terminal/setup.py:6624-6639`, `terminal/setup.py:6683-6685`）。

## ログと測定値

変数の読み取り・有効化だけを知らせるログはない。存在しない指定先も `find_vcvars()` では無言で `None` になり、後続のビルド経路が上記のエラーを出す。`docs/SOURCE_INSTALL.md:40-45` は手動指定例と「存在する場合だけ使う」説明を記載しており、実装と一致する。測定値は該当しない。

## 根拠

- `terminal/setup.py:2674-2699` — override の読み取り、存在確認、自動探索への分岐、CUDA バージョン別 `vswhere` 条件。
- `terminal/setup.py:5790-5793`, `terminal/setup.py:5900-5957`, `terminal/setup.py:6604-6690` — Windows セットアップの呼び出し元と C++ ツール判定。
- `terminal/setup.py:6793-6815` — vcvars バッチの呼び出しとビルド実行。
- `terminal/setup.py:1044-1056`, `terminal/setup.py:6805-6809` — 警告・停止の表示と終了コード。
- `docs/SOURCE_INSTALL.md:40-45` — 実装との照合に使ったセットアップ説明。
