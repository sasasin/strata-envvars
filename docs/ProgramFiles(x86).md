# `ProgramFiles(x86)`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。Strata 所有ソースのうち、この名前を直接参照する `setup.py`、MCP ツール、Windows 用 HIP ビルドバッチを調査した。外部ツール自身の挙動は対象外。

## 役割

Windows で Visual Studio の `vswhere.exe` を探す基点として使われるほか、Strata MCP サーバーが新しいデータ保存先を検査するとき、システムフォルダーの一つとして扱われます。Windows 用 `tools/hip/build_windows.bat` も同じ環境変数を使って `vswhere.exe` の場所を組み立てます。

## 値と判定

| 読み取り箇所 | 未設定 | 空文字 | 値が設定されている場合 |
|---|---|---|---|
| `setup.py:find_vcvars()` | `C:\Program Files (x86)` を既定値にする | `os.environ.get()` は空文字を返すため既定値にはならず、相対パス `Microsoft Visual Studio/Installer/vswhere.exe` を検査する | 値をそのまま `Path` に渡し、その下の `Microsoft Visual Studio/Installer/vswhere.exe` を検査する |
| `tools/strata_mcp.py:system_folders()` | `None` となり、システムフォルダー一覧にこの場所を追加しない | 偽値として一覧から除外する | パスを正規化して一覧に加える |
| `tools/hip/build_windows.bat` | `%ProgramFiles(x86)%` が空に展開され、`\Microsoft Visual Studio\Installer\vswhere.exe` を探す | 同じく空に展開される | 値を基点に `vswhere.exe` の場所を組み立てる |

いずれの箇所も、この変数の値を数値や真偽値として parse しません。値の存在確認、空値の特別扱い、パスの存在確認は呼び出し箇所ごとに異なります。`setup.py` は値の前後の空白除去、環境変数展開、`~` 展開を行わず、組み立てた `vswhere.exe` のパスに `exists()` を適用します。`STRATA_VCVARS` が空でない場合は先にその値を調べ、存在すればそちらを返します。存在しない場合は `None` を返し、`ProgramFiles(x86)` 側へは進みません。

## 有効になる条件

- `setup.py` の参照は Windows のビルド経路で `find_vcvars()` が呼ばれた場合に使われます。CUDA エンジンのビルドツール確認・再確認と、Windows の CPU vision encoder ビルド時に呼び出しがあります。`STRATA_VCVARS` が非空なら、Visual Studio 自動検出より優先されます。
- MCP の参照は Windows 上で `strata_install` に指定された新しい `data_dir` を検査し、その保存先が既存データ場所などの許可対象外である場合に効きます。正規化した保存先がシステムフォルダー自体、またはその配下なら `data_dir ... is inside a system folder` エラーになります。既に許可された Strata のデータ場所や Strata フォルダーなどは、このシステムフォルダー検査より前に許可されます。
- `tools/hip/build_windows.bat` は HIP 用ビルドを Windows で実行する場合に使います。ここでは `ProgramFiles(x86)` に既定値を補いません。組み立てた `vswhere.exe` が見つからないか、C++ workload を持つ Visual Studio が見つからない場合はビルドを終了します。
- Linux では MCP の `system_folders()` は固定の Unix パス一覧を返すため、この変数を読みません。`setup.py` の `find_vcvars()` 呼び出しも `WIN` 条件の外では行われません。

## 実行時の詳細

`find_vcvars()` はまず非空の `STRATA_VCVARS` を確認し、それがなければこの環境変数を基点に `vswhere.exe` を探します。ファイルがなければ `None` を返します。見つかった場合、CUDA バージョンが渡されていれば `vswhere` に Visual Studio のバージョン範囲を付け、C++ x86/x64 ツールを要求して、インストール先の `VC/Auxiliary/Build/vcvars64.bat` が存在するかを調べます。CUDA バージョンが渡されない呼び出しではバージョン範囲を付けません。見つからない結果は Windows のビルドツール不足として上位のセットアップ処理で扱われます。MCP ツールでは、`ProgramFiles(x86)` を含む Windows のシステムフォルダー一覧を都度構成し、候補 `data_dir` を正規化して各フォルダーと比較します。

Windows HIP バッチでは、`%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe` を組み立てて実行し、見つかったインストール先から `vcvars64.bat` を呼び出します。

## 文書との照合

`docs/DETAILS.md` は、Windows で ready-made engine が適合しない場合に Visual Studio Build Tools と CUDA Toolkit を用意してエンジンをビルドすると説明していますが、`ProgramFiles(x86)` 自体の設定規則は説明していません。実際のパス決定と失敗時の分岐は上記ソースに基づきます。MCP によるデータ保存先の説明は `docs/MCP_SERVER.md` と `docs/DETAILS.md` にありますが、この環境変数を使った Windows のシステムフォルダー判定の詳細は記載されていません。

## 根拠

- `setup.py:1390-1415` — `STRATA_VCVARS` の優先処理、既定パス、`vswhere` 引数、戻り値。
- `setup.py:2697-2705, 3211-3240, 3256-3286` — `find_vcvars()` の呼び出し元とビルドツール確認。
- `tools/strata_mcp.py:376-382, 1130-1154` — Windows のシステムフォルダー一覧と `data_dir` の検査。
- `tools/hip/build_windows.bat:53-58` — Windows HIP ビルドでの `vswhere.exe` と `vcvars64.bat` の検出。
- `docs/DETAILS.md:423-431, 1395-1414` — セットアップと MCP サーバーの概要。
