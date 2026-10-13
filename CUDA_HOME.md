# `CUDA_HOME`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数の動作は対象外。

## 役割

`CUDA_HOME` は `setup.py` が CUDA Toolkit 内の `nvcc` を探すための候補ルートです。値を `<CUDA_HOME>/bin/nvcc`（Windows では `nvcc.exe`）へ連結し、そのファイルが実在してバージョンを読み取れた場合にビルド用 compiler 候補として扱います。Strata の実行時推論コードによる読み取りは確認できません。

これはビルド設定です。既製 engine の起動では `CUDA_HOME` を参照せず、ローカル engine のビルドが必要になった場合などに `install_build_tools()` から `find_nvcc()` が呼ばれます。`build_engine()` はそこで得た `nvcc` を CMake の `CMAKE_CUDA_COMPILER` に渡します。RTX 50（sm_120）で CUDA 13.2.0/13.2.1 を検出し、`STRATA_NVCC` が指定されていない場合には、互換性のため古い Toolkit を探す二度目の検索でも同じ候補規則が使われます。

## 値と判定

| 状態 | Strata の処理 |
|---|---|
| 未設定、または空文字 | `CUDA_HOME` 由来の候補を追加しません。通常の自動探索は続きます。 |
| 空でない値 | 値をパスとして扱い、その下の `bin/nvcc`（Windows は `bin/nvcc.exe`）を候補に加えます。 |
| 指定先に `nvcc` がない | 候補ファイルが存在しないため無視されます。`CUDA_HOME` 専用の警告やエラーは出しません。 |
| `nvcc --version` 出力に `release <major>.<minor>` がない | その候補からバージョンを得られず、採用されません。 |

環境変数の値は trim されず、`os.environ.get()` の真偽だけを調べます。したがって空白だけの値も候補になりますが、有効なルートになるとは限りません。相対パスも絶対パス化せず、プロセスの作業ディレクトリから解決されます。値全体の数値 parse や大小文字変換はありません。

`CUDA_HOME` は単独の優先指定ではありません。候補列にはまず `PATH` 上の `nvcc`、続いて `CUDA_PATH`、`CUDA_HOME` の順で追加されます。同じパス文字列は重複排除されます。存在する各候補の `nvcc --version` から major/minor を読み、条件に合うもののうち最も新しいバージョンを選びます。同じバージョンなら先に列挙された候補が残ります。`below` 条件付き検索では `below` より古いバージョンだけが対象です。

## 有効になる条件

- `STRATA_NVCC` が空でない場合は、通常の探索候補（`PATH`、`CUDA_PATH`、`CUDA_HOME`、OS 固有の場所）を検索せず、その指定を使います。指定ファイルが存在しなければ警告を出して通常探索へ進みます。存在しても `--version` からバージョンを得られない場合は `(None, None)` を返し、通常候補には進みません。`below` 条件に合わない場合も警告して候補なしになります。したがってこの場合 `CUDA_HOME` は参照されません。
- Windows では `CUDA_PATH` / `CUDA_HOME` 候補の後に NVIDIA Toolkit の標準インストール先を探索します。非 Windows では `/usr/local/cuda*` と `/opt/cuda*` の各ディレクトリも候補です。これらも含めた候補全体で最も新しい適合バージョンを選ぶため、`CUDA_HOME` が指す Toolkit が選ばれるとは限りません。
- `install_build_tools()` は GPU の architecture と選択中の CUDA 12/13 engine に応じて必要 Toolkit バージョンを確認します。古い GPU 用の CUDA 12 engine では 13.0 未満に絞って探索し、sm_120 を含む通常 engine では CUDA 13.0 以上が必要です。不足時は setup の失敗またはツール導入案内につながります。
- この環境変数は `setup.py` のビルドツール探索で使われます。Strata engine の実行時動作や外部 CUDA ライブラリの探索動作を本調査の根拠から説明するものではありません。

## 実行時の詳細

`find_nvcc()` は `CUDA_PATH` と `CUDA_HOME` を順に読み、非空の値から Toolkit 配下の `nvcc` のパスを組み立てます。候補が存在すると `out([candidate, "--version"])` を実行し、出力中の `release M.m` を正規表現で抽出してバージョン判定します。`below` が指定されたときは上限未満を残し、残った候補の中の最新バージョンを返します。

探索した結果は `install_build_tools()` が要求 Toolkit と比較します。条件を満たす compiler があれば `build_engine()` はそのパスを `-DCMAKE_CUDA_COMPILER=...` として CMake に渡し、さらに `toolkit_root_defs()` でその `nvcc` の親の親を `CUDAToolkit_ROOT` として渡します（ルートが `/usr` の場合を除く）。このため `CUDA_HOME` の主な効果は、ビルドに採用される Toolkit の候補と選択結果です。値は `find_nvcc()` を呼ぶたびに読み直され、プロセス起動後の変更を反映し得ます。子プロセスへの値の伝播を Strata が独自に設定する処理は、この変数について確認できません。

## 根拠

- `setup.py:1353-1387` — `find_nvcc()` の `STRATA_NVCC` 上書き、`CUDA_PATH` / `CUDA_HOME` の取得、候補構築、`--version` の解析、バージョン比較。
- `setup.py:3190-3208` — sm_120 と CUDA 13.2.0/13.2.1 の場合に、明示的な `STRATA_NVCC` がなければ古い compiler を再探索する処理。
- `setup.py:3211-3239,3279-3286` — GPU / Toolkit に応じた `find_nvcc()` の条件、必要バージョンの判定、導入後の再探索。
- `setup.py:3381-3423` — engine がローカルビルドを要する場合の `install_build_tools()` 呼び出しと、CMake への CUDA compiler 指定。
- `setup.py:3352-3359` — 選んだ `nvcc` から `CUDAToolkit_ROOT` を作る処理。
- `tools/test_setup_choices.py:241-270` — `CUDA_PATH` と `CUDA_HOME` を候補として扱う既存テスト。これは候補値の照合に限って参照し、挙動の根拠は本番 `setup.py` としています。
