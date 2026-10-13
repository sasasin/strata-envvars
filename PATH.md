# `PATH`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

Strata の setup、MCP 起動処理、同梱ユーティリティが、名前だけで指定された外部コマンドを探すときに参照する。Strata 独自の `PATH` 値パーサーや、環境変数を真偽値として扱う処理はない。Python の `shutil.which()` による検索を通じて使われる。

## 値と判定

値はディレクトリ検索パスとして Python の `shutil.which()` に渡される。Strata は区切り文字での分割、空要素、相対パス、重複要素、無効なディレクトリの独自検査や正規化を行わない。したがって `1` / `0` のような有効・無効値の規則はない。unset と空文字の意味は各呼び出し箇所の `shutil.which()` / `env.get()` に委ねられる。

| 経路 | `PATH` の使われ方 |
|---|---|
| `setup.py` の CUDA ビルド | `nvcc` を検索する候補の一つ。`STRATA_NVCC` が空でない場合はその指定を優先し、`PATH` 上の `nvcc` より先に使う。 |
| `setup.py` のビルドツール | `cmake` / `ninja` は PATH 上の実行ファイルを試し、`--version` が成功しない場合は Python 環境隣接のディレクトリ等を探す。`g++`、`c++`、`git`、`winget`、`apt-get` も存在確認に使う。 |
| MCP stdio サーバー | 継承した環境を MCP 設定の `env` で上書きした後、`command` を検索する。見つからなければ、元の `command` 文字列を実行ファイルとして起動しようとする。 |
| Strata MCP 補助ツール | GPU 情報収集時に `rocm-smi` と `nvidia-smi` が見つかるかを確認し、実行可能性の有無を分岐に使う。 |
| ISA ガード確認ツール | `tools/check_isa_guard.py` が、利用可能な `nm` / `objdump` を PATH から探す。これは同梱の診断用ツールであり、エンジンの通常実行時設定ではない。 |

## 有効になる条件

- setup のツール検索は、対応するセットアップまたはビルド経路が実行されたときだけ関係する。CUDA の `nvcc` 探索では、空でない `STRATA_NVCC` が通常候補探索より優先される。`CUDA_PATH` / `CUDA_HOME` 等から組み立てた絶対パスや、OS 固有の既知ディレクトリも別候補となるため、`PATH` に目的の `nvcc` がなくても見つかる場合がある。
- Linux の AMD ソースビルドでは、`build_engine_hip()` が `PATH` の先頭に ROCm の `bin` と `llvm/bin` を加え、元の値を後ろに残す。この後の CMake / Ninja やビルドコマンドの子プロセスにその環境が渡る。Windows の同梱 `tools/hip/build_windows.bat` も同様に ROCm のディレクトリを先頭へ加える。
- MCP 子サーバーでは、設定の `env.PATH` が親プロセスの `PATH` を置き換えられる。サーバーが起動した後は、その起動時に選ばれた実行ファイルと環境が使われる。
- `serve/server.py` のエンジン用 `child_env()` は、設定に `lib_dirs` がある Windows 経路でそれらを `PATH` の先頭に加える。Linux ではこの目的に `LD_LIBRARY_PATH` を使い、`PATH` は変更しない。

## 実行時の詳細

setup の `find_nvcc()` は `shutil.which("nvcc")` の結果を候補として加え、見つかった実行ファイルの `--version` 出力から CUDA バージョンを判定する。候補が PATH 上にあるだけでは採用が確定せず、ファイルの存在とバージョン要件も確認される。`find_tool()` は `shutil.which(name)` で得たパスを `--version` 付きで最大30秒実行し、正常終了しなければ `sys.executable` の隣接 `Scripts` / 実行ファイルディレクトリ、または `~/.local/bin` を探す。CMake / Ninja が最終的に見つからなければ setup は `cmake / ninja not found after installing them` を出して失敗する。

MCP の `StdioTransport.start()` は起動ごとに親環境を複製し、設定の `env` を反映してから `shutil.which(command, path=env.get("PATH"))` を呼ぶ。検索結果がなければ `Popen` に元のコマンド文字列を渡す。プロセス生成時の `OSError` は `could not start ...` の `McpError` になる。MCP 設定はコマンド名や検索 PATH を変えられるが、環境変数の値を Strata が再 parse するわけではない。

同梱の Strata MCP 補助処理では、PATH 上の `rocm-smi` が見つかり、既存の AMD GPU 情報がない場合に `rocm_smi_gpus()` へ進む。また `nvidia-smi` が見つかるかを `hw["nvidia_smi"]` の真偽値として返す。PATH 検索結果がない場合の代替動作は各分岐の範囲に限られ、GPU ドライバーや外部コマンド内部の探索動作はここでは扱わない。

開発・診断用 `tools/check_isa_guard.py` は、必要な `nm` / `objdump` が見つからない場合にそのツールの検査を飛ばす。これはエンジン実行時の設定ではない。

## 文書との照合

`docs/DETAILS.md` は、`nvcc` が PATH または `/usr/local/cuda*` / `/opt/cuda*` から見つかることと、MCP の `npx` / `uvx` / `python` 等が PATH から解決されることを説明している（548-549, 1334-1337行）。これは実装と一致する。文書の説明を超えて、PATH の全利用箇所や Python・OS による検索詳細を Strata 独自の挙動とはみなしていない。

## 根拠

- `setup.py:1353-1383` — `STRATA_NVCC` と `shutil.which("nvcc")` を含む CUDA コンパイラー候補探索。
- `setup.py:1418-1433, 3211-3286, 3289-3310` — PATH 上のツール検索、存在確認、バージョン確認とビルド失敗経路。
- `setup.py:2652-2668` — AMD ビルドのコマンド存在確認、PATH 先頭への ROCm ディレクトリ追加と後続ビルド。
- `setup.py:2332-2338, 5455-5461` — Windows の HIP デバイス確認用子プロセスと同梱エンジン用ライブラリディレクトリ。
- `serve/mcp.py:93-109` — MCP 設定反映後の `PATH` 検索、サブプロセス起動と起動エラー。
- `serve/server.py:2554-2571` — エンジン用子環境を複製し、Windows では DLL 用ディレクトリを PATH に追加。
- `tools/strata_mcp.py:627-644` — `rocm-smi` / `nvidia-smi` の PATH 上の有無による分岐。
- `tools/check_isa_guard.py:76-89` — 開発・診断時に `nm` / `objdump` を検索。
- `tools/hip/build_windows.bat:58-64` — Windows HIP ビルド時の PATH 先頭追加。
- `docs/DETAILS.md:548-549, 1334-1341` — setup と MCP に関する利用者向け説明。
