# `CUDA_HOME`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`CUDA_HOME` は Strata の `terminal/setup.py` が CUDA Toolkit の `nvcc` を探すときの候補ディレクトリとして使われる。`CUDA_HOME/bin/nvcc`（Windows では `CUDA_HOME/bin/nvcc.exe`）が存在し、`nvcc --version` の出力からバージョンを読めた場合、他の候補と比較して採用される可能性がある。実行時のエンジンや GPU 動作を切り替える環境変数ではない。読み取りは `find_nvcc()` 内のセットアップ処理で行われる（`terminal/setup.py:2595-2629`）。

## 値と判定

`os.environ.get("CUDA_HOME")` の真偽値だけを確認する。未設定と空文字は候補に加えず、それ以外は値をパスとしてそのまま連結する。空白の除去、文字列形式の検証、環境変数値自体のバージョン解釈は行わない。候補のファイルが存在する場合に `nvcc --version` を実行し、標準出力の `release 数字.数字` に正規表現が一致すればその major/minor を読む。コマンド実行が OS エラーまたは 60 秒 timeout になった場合は空出力として扱う（`terminal/setup.py:1192-1196, 2611-2629`）。

| 条件 | `CUDA_HOME` | 結果 |
|---|---|---|
| 未設定または空文字 | 候補にしない | PATH、`CUDA_PATH`、OS ごとの標準候補を調べる |
| 非空で `bin/nvcc`（Windows は `bin/nvcc.exe`）が存在し、バージョン出力に一致 | 候補にする | 他の候補のバージョンと比較し、新しい適合バージョンが選ばれる |
| 非空だが実行ファイルがない、または出力からバージョンを読めない | 実質不採用 | 警告なしで次の候補へ進む |
| `0`、`1`、`true`、`false`、`0anything` など | 特別な値判定なし | いずれも非空ならパス文字列として扱うだけ |

`CUDA_HOME` と `CUDA_PATH` の候補順よりもバージョン比較が優先される。候補順は PATH 上の `nvcc`、`CUDA_PATH`、`CUDA_HOME`、OS 固有の標準パス。適合したバージョンが同じ場合は、先に現れた候補が残る（更新条件が `>`）。`below` が指定された探索では、その値未満のバージョンだけを候補にする（`terminal/setup.py:2611-2629`）。

## 有効になる条件

- `terminal/setup.py` がローカル CUDA ビルド用に Toolkit を探索するときに参照される。エンジンのビルドが必要な場合は `build_engine()` から `install_build_tools()` に進み、画像生成器の CUDA backend でも `find_nvcc()` を呼ぶ（`terminal/setup.py:5840-5844, 6818-6849`）。既存エンジンが再利用される場合、または CUDA 以外の画像 backend では、この探索経路を通らない。
- 非空の `STRATA_NVCC` がある場合は、そちらが優先され、通常候補（`CUDA_HOME` を含む）は探索されない。指定先が存在しない場合に限り警告して通常探索へ進む。存在するがバージョンを読めない場合、または `below` 条件以上のバージョンだった場合は `find_nvcc()` が `(None, None)` を返し、通常候補へ戻らない（`terminal/setup.py:2599-2610`）。
- `CUDA_PATH` も同じ探索の候補である。PATH 上や標準パスにある、より新しく条件に合う Toolkit があれば `CUDA_HOME` の Toolkit が選ばれないことがある（`terminal/setup.py:2611-2629`）。
- 必要な Toolkit のバージョン条件は対象 GPU と CUDA 12/13 の選択で変わる。CUDA 12 経路は 13.0 未満を検索し、GPU archs の最大値が 120 以上なら最低 12.8、それ以外は最低 12.0 を要求する。通常経路は最大値が 120 以上なら最低 13.0、それ以外は最低 12.0 を要求する（`terminal/setup.py:6524-6546`）。`--cuda` は Toolkit 系統を選ぶ入力であり、`CUDA_HOME` のパスを直接指定する CLI 引数ではない（`terminal/setup.py:11328-11331`）。
- sm_120 かつ CUDA 13.2.0/13.2.1 のコンパイラでは、build number を調べて古い 13.x を推奨探索する場合がある。`STRATA_NVCC` が空なら `find_nvcc(below=(13, 2))` が再度候補を調べるため `CUDA_HOME` も候補になる。13.2.2 相当以上、sm_120 未満、または明示的 `STRATA_NVCC` の場合はこの再探索条件に入らない（`terminal/setup.py:6479-6508`）。

## 実行時の詳細

通常候補を探索する `find_nvcc()` の呼び出しごとに `CUDA_HOME` を環境から読み直し、関数内やモジュール内に cache しない。setup プロセスの実行中に環境を書き換えた後の通常探索には新しい値が使われる。ただし有効な `STRATA_NVCC` が通常探索を置き換える場合は `CUDA_HOME` を読み取らない。候補パスで `nvcc --version` を実行し、その出力から Toolkit の major/minor を取得して、必要なバージョン条件を満たす候補のうち最も新しいものを選ぶ。したがって `CUDA_HOME` を指定しても、それだけで選択が固定されたり、Toolkit の最低バージョン条件が変わったりはしない（`terminal/setup.py:1192-1196, 2595-2629, 6531-6549`）。

適合する `nvcc` が見つからない場合、画像生成器の CUDA backend は `compiling the image generator for NVIDIA needs the CUDA Toolkit (nvcc)` で setup を停止する（`terminal/setup.py:5840-5844`）。エンジンのビルドでは必要な build tools を案内して確認し、拒否された場合は `the build tools are needed` で停止する。Ubuntu/Debian 以外で自動導入対象外の場合なども `fail()` 経由で終了コード 1 になる（`terminal/setup.py:6543-6555, 6569-6582`; `fail()` は `terminal/setup.py:1049-1056`）。候補が不適合でも `CUDA_HOME` 固有の警告はなく、`STRATA_NVCC` の不在パスの場合だけ `STRATA_NVCC=...: no such file; looking for a CUDA toolkit as usual` が出る（`terminal/setup.py:2600-2603`）。

`tools/nix/flake.nix` の devShell は `CUDA_HOME` と `CUDA_PATH` を同じ Toolkit root に設定する（`tools/nix/flake.nix:18-23, 39-42`）。これは setup の探索候補に値を供給する Strata の設定である。一方、`terminal/tools/par/e00.py` の `CUDA_HOME` は第 2 位置引数名であり、環境変数の読み取りではない（`terminal/tools/par/e00.py:2, 5-7, 18`）。third-party の `ggml/cmake/FindNCCL.cmake` にも名前は現れるが、外部依存の実装は本調査の対象外である。

## 根拠

- `terminal/setup.py:2595-2629` — `find_nvcc()` の優先指定、候補の追加、バージョン抽出と選択。
- `terminal/setup.py:1192-1196` — `nvcc --version` 実行時の例外・timeout 処理。
- `terminal/setup.py:5840-5849, 6818-6849` — 画像 CUDA backend とエンジン build からの探索呼び出し。
- `terminal/setup.py:6479-6508, 6520-6555, 6569-6606` — sm_120 の再探索、Toolkit 条件、欠落時の処理。
- `terminal/setup.py:11328-11331` — `--cuda` の選択肢。
- `tools/nix/flake.nix:18-23, 39-44` — devShell が `CUDA_HOME` と `CUDA_PATH` を設定する箇所。
- `terminal/tools/par/e00.py:2, 5-7, 18` — 同名の位置引数と既定値。環境変数ではない。
