# `STRATA_VCVARS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Windows で Strata のセットアップがローカルビルドを行うとき、Visual Studio の `vcvars64.bat` の場所を指定します。このファイルをビルド用バッチから呼び出し、CMake とビルドに必要な MSVC 環境を用意します。モデルの実行時設定ではありません。

この名前を環境から読むのは `setup.py` の `find_vcvars()` だけです。Strata 本体の C++/GPU 実装やサーバーによる読み取りは見つかりませんでした。`setup.py` 内の呼び出しも Windows 判定付きで、ビルドが必要な経路に限られます。既製エンジンをそのまま使うなど、ローカルビルドが発生しない場合は参照されません（`setup.py:91,4912-4920,5030-5055,5680-5681,7798`）。

## 値と判定

| 環境値 | 判定と結果 |
|---|---|
| 未設定 | `vswhere.exe` で Visual Studio を検索します。 |
| 空文字 | Python の `if override:` が偽になるため、未設定と同じ自動検索です。 |
| 空でない既存パス | `Path(value).exists()` が真なら、そのパスを `vcvars64.bat` として返します。拡張子、ファイル種別、実行可能性は検証しません。 |
| 空でない存在しないパス | `None` を返します。自動検索には進みません。 |

値は文字列のまま `Path` に渡され、空白の trim、環境変数展開、相対パスの解決、値形式の検査はありません。`exists()` による存在確認のみなので、存在するディレクトリなどを指定した場合もここでは拒否されず、後の `call` が失敗し得ます。数値変換や値域・境界値の規則はありません（`setup.py:2261-2265`）。

自動検索では `ProgramFiles(x86)` を使って `vswhere.exe` の場所を決めます（未設定時は `C:\Program Files (x86)`）。`vswhere.exe` がなければ `None` です。CUDA のバージョンを渡された場合は、CUDA 13.3 以上なら Visual Studio 2026 も含む上限、未満ならそれを除く上限で検索します。CUDA バージョンなしの呼び出しではバージョン範囲を指定しません。検索結果の `installationPath` から標準の `VC/Auxiliary/Build/vcvars64.bat` を組み立て、存在する場合だけ返します（`setup.py:2265-2277`）。

## 有効になる条件

- 実際の `find_vcvars()` 呼び出し箇所は Windows（`WIN = os.name == "nt"`）に限定されています。Linux では各呼び出し元が `None` を渡すため、この変数を読みません（`setup.py:91,4912-4919,5030-5051,5680`）。
- 通常の NVIDIA エンジンビルドでは `install_build_tools()` が Visual Studio 環境を確認し、`build_engine()` が必要なとき `cmake_build()` に渡します。コンパイル済みエンジンが利用可能で再ビルドも不要なら、この経路を通りません（`setup.py:5660-5690,5905-5936,5944-5950,7788-7798`）。
- Windows の画像生成エンジンや CPU 画像エンコーダーのローカルビルドでも参照します。画像生成で選ぶ backend により CUDA のバージョン付き検索、またはバージョン範囲なしの検索になります（`setup.py:4912-4920,5004-5055`）。
- 関連する CLI は `--build` で、既製エンジンを避けてローカルビルドする経路があります。`STRATA_VCVARS` 自体に対応する CLI 引数や別の値上書きは見つかりません（`setup.py:9155,7788-7798`）。

## 実行時の詳細

`find_vcvars()` が呼ばれるたびに `os.environ.get()` を実行し、関数内にもモジュール全体にも結果の cache はありません。したがってセットアップの同一プロセス内で環境値が変更されてから再度呼ばれれば、次の呼び出しで読み直されます。CLI 引数による値の上書きもありません（`setup.py:2252-2265`）。

空でない override が存在すればそれを返し、存在しない override なら `None` を返します。`ProgramFiles(x86)` による自動検索は override が未設定または空文字のときだけです。`setup.py` の `run()` がコマンドごとに環境を子プロセスへ渡す一般処理はありますが、`STRATA_VCVARS` を別値にして転送する処理は見つかりません。VC 環境の設定は、`cmake_build()` が生成するバッチファイル内で `call "<vcvars path>" >nul` と実行することで行います（`setup.py:959-973,5800-5819`）。

Windows で `cmake_build()` に `None` が渡ると、次のエラーと案内を表示してセットアップを終了コード 1 で停止します。

```text
[X]  the Visual Studio 2022 C++ build tools were not found (Visual Studio 2019 is too old: the sources are C++20)
       install Visual Studio 2022 Build Tools (workload 'Desktop development with C++'), then run setup again; a ready-made engine needs no compiler: `strata update` fetches it
Setup stopped. Fix the item above and run it again - everything already done is kept and skipped.
```

存在するが `vcvars64.bat` として使えないパスの場合、この事前エラーは回避され、生成バッチの `call` または後続コマンドで失敗する可能性があります。`run()` は非ゼロ終了を `command failed (exit N): cmd` として報告し、既定の `check=True` ではセットアップを停止します（`setup.py:904-909,974-978,5809-5819`）。変数そのものについての専用警告ログはありません。

## 根拠

- 直接読み取り、override の分岐、自動検出、CUDA バージョン範囲: `setup.py:2252-2277`
- Windows 判定と代表的な呼び出し元: `setup.py:91,4912-4920,5004-5055,5660-5690,5905-5950`
- VC 環境をバッチに設定する処理と失敗経路: `setup.py:904-909,959-978,5800-5824`
- ユーザー向けセットアップ説明: `docs/SOURCE_INSTALL.md:39-44`。環境変数は指定されたファイルが存在する場合だけ使われ、誤ったパスはビルドツール未検出として扱われる、と説明されています。
