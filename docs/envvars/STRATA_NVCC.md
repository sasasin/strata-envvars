# `STRATA_NVCC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。作業ツリーは `main...origin/main` で、未コミット変更はありません。外部ライブラリ・GPU driver の挙動は対象外。

## 役割

ソースセットアップが CUDA コンパイラ `nvcc` を探す際、ユーザー指定のパスを候補探索より優先する変数です。値を読むのは `setup.py` で、ビルド用ツールキットの選択および CUDA 画像エンコーダーのビルドに使われます。通常のインストール済みエンジンの実行時設定ではありません。

## 値と判定

`os.environ.get("STRATA_NVCC")` の値を真偽値で判定します。空文字列は未設定と同じく通常探索へ進みます。空白除去や文字列全体の形式検査はせず、非空の値をパスとして `Path.exists()` で確認します。

| 値・条件 | `find_nvcc()` の処理 |
|---|---|
| 未設定、または空文字 | `PATH`、`CUDA_PATH`、`CUDA_HOME`、OS別の標準配置を探索する。 |
| 非空だがパスが存在しない | `STRATA_NVCC=<値>: no such file; looking for a CUDA toolkit as usual` と警告し、通常探索へ進む。 |
| 非空でパスが存在する。`--version` の標準出力に `release 数字.数字` がある | 指定パスと `(major, minor)` を返す。ただし `below` が指定され、その版が `below` 以上なら警告して `(None, None)` を返す。指定パスを拒否した後に別候補へは進まない。 |
| 非空でパスは存在するが、版数を読めない | `(None, None)` を返す。通常候補探索には進まない。 |

版数は `release (\\d+)\\.(\\d+)` の正規表現で標準出力から抽出します。コマンド実行は最大60秒で、`OSError` または timeout 時は空文字列扱いです。`below` の比較は厳密な下限で、たとえば CUDA 12 エンジン用の `(13, 0)` なら 13.0 以上は不適合です。自動探索では候補ごとに同じ形式で版数を読み、条件を満たす候補のうち最も新しい版を選びます。`PATH` の `nvcc`、`CUDA_PATH` / `CUDA_HOME` 配下、Windows の標準 CUDA 配置、または Linux の `/usr/local/cuda*` と `/opt/cuda*` が探索元です。

## 有効になる条件

- Strata のソースセットアップで CUDA 用エンジンのビルドが必要になり、`install_build_tools()` がコンパイラを選ぶときに参照されます。CUDA 12 系エンジンでは 13.0 未満を探し、必要な CUDA 版は GPU architecture に応じて判定されます。選択後の `nvcc` パスは CMake の `CMAKE_CUDA_COMPILER` に渡されます。
- CUDA backend の画像エンジンを新たにビルドする経路でも `find_nvcc()` が呼ばれます。ここでは版の上限指定はなく、見つからなければセットアップを停止します。
- CUDA 13.2 の版が RTX 50（sm_120）向けビルドに選ばれた場合、`nvcc` build 番号が 86 未満または読めないときの自動代替探索は、`STRATA_NVCC` が空でない場合には行われません。指定済みコンパイラを維持して警告を出します。変数が未設定または空なら、13.2 未満の候補を探し、13.0 以上が見つかった場合はそちらを使います。
- 既製エンジンが使われ、CUDA コンパイルが発生しない通常の起動経路では、この選択処理に入りません。HIP ビルド用経路も `STRATA_NVCC` を参照しません。

## 実行時の詳細

値は `find_nvcc()` の呼び出しごとに読み直され、モジュール内キャッシュはありません。したがってセットアップ中に環境が書き換えられれば次の呼び出しでは再評価されます。`nvcc` や CMake などの子プロセスには通常の環境継承がありますが、この変数を子プロセス用に書き換える処理はありません。選択されたパスは `build_engine()` から CMake の `-DCMAKE_CUDA_COMPILER=...` として渡され、CUDA toolkit のルート定義にも使われます。

明示パスが存在しない場合は警告後に自動探索します。指定パスの CUDA 版が `below` 以上の場合は警告し、別候補へ fallback せず `(None, None)` を返します。通常のエンジンビルドでは必要な compiler/toolkit がないとしてインストール案内またはエラー停止に至り得ます。版数が読めない既存パスも `(None, None)` となり、通常探索はされません。CUDA 13.2 の sm_120 向け警告は stdout に `[!]` 付きで出ます。`warn()` と `fail()` は stdout に表示し、`fail()` は `sys.exit(1)` でセットアップを終了します。

ソース内の案内と一致して、`docs/OLDER_GPUS.md` は CUDA 12.x の選択、`docs/TROUBLESHOOTING.md` は特定 toolkit の明示指定を説明しています。`docs/DETAILS.md` は通常の `nvcc` 探索場所を説明していますが、この変数の空文字・無効パス時の詳細は記載していません。

## 根拠

- `setup.py:2215-2249` — 値の取得、空文字を含む真偽判定、明示パスの存在確認と版数抽出、`below` 判定、fallback、自動候補探索。
- `setup.py:1000-1004` — `--version` 実行の timeout と例外時の空出力。
- `setup.py:896-909` — 警告・停止メッセージの出力先と終了動作。
- `setup.py:5022-5031` — CUDA 画像エンジンのコンパイル時にも `find_nvcc()` を呼び、選択パスを CMake に渡す。
- `setup.py:5624-5649` — RTX 50 / sm_120 向け CUDA 13.2 build 判定、変数が未指定の場合だけ行う代替探索と警告。
- `setup.py:5660-5690, 5739-5746` — CUDA toolkit 要件判定、通常・CUDA 12 の compiler 選択、ビルドツール不足時の処理。
- `setup.py:5905-5976` — engine build から `install_build_tools()` へ進み、選択した `nvcc` を CMake へ渡す箇所。
- `setup.py:7772-7804` — 通常のセットアップ engine 経路。既製品がない場合または明示 build の場合にビルドへ進む。
- `docs/OLDER_GPUS.md:111-113`, `docs/TROUBLESHOOTING.md:211-218,288-292`, `docs/DETAILS.md:197-201` — 既存説明との照合。
