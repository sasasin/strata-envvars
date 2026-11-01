# `CUDA_HOME`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。外部ライブラリと GPU driver 自身の環境変数動作は対象外です。

## 役割

`CUDA_HOME` は Strata の Python セットアップ `setup.py` が CUDA Toolkit の `nvcc` を探す際に、Toolkit ルートの候補として参照します。実行エンジンの通常起動では読まれません。エンジンをソースからビルドする場合と、CUDA backend の画像生成エンジンをビルドする場合に、セットアップが `find_nvcc()` を呼ぶ経路で関係します。既製エンジンを使い、画像生成エンジンも既に用意されている場合は、この変数による探索は行われません（`setup.py:2215-2249, 5014-5022, 5931-5938, 7772-7798`）。

この変数の値で CUDA 12 / 13 のどちらを選ぶかは決まりません。CUDA の世代は GPU と `--cuda`（省略時は `STRATA_CUDA`）から決まり、その条件に合う `nvcc` を探索します（`setup.py:9163-9166, 9475-9478, 5663-5685`）。

## 値と判定

Python の `os.environ.get(var)` を使い、値を strip したり解析したりせず、空でない文字列だけを候補に追加します。候補は `$CUDA_HOME/bin/nvcc`（Windows は `CUDA_HOME\bin\nvcc.exe`）です（`setup.py:2231-2235`）。

| `CUDA_HOME` | 判定と結果 |
|---|---|
| 未設定 | この候補を追加しません。PATH や標準ディレクトリの探索は続きます。 |
| 空文字 | Python では偽と判定され、未設定と同様に候補を追加しません。 |
| 空でない値 | その文字列を Toolkit ルートとして `bin/nvcc`（Windows は `bin/nvcc.exe`）を候補にします。数値、空白、大文字小文字などの検証はしません。 |
| 指定先に `nvcc` がない | 候補としては作られますが、`Path.exists()` を通らず採用されません。個別の警告は出ず、ほかの候補を調べます。 |
| `nvcc --version` の stdout に `release major.minor` がない | version を認識できず、この候補は採用されません。実行失敗または 60 秒 timeout の場合、`out()` は空文字を返します。 |

`find_nvcc()` は `nvcc --version` の stdout から `release 数字.数字` を正規表現で探し、version を整数の `(major, minor)` にします。プロセスの終了コード自体は `out()` で判定していません。CUDA 世代の条件がある呼び出しでは `below` 未満の version だけが対象です（`setup.py:1000-1004, 2242-2249`）。

## 有効になる条件

- **エンジンのビルド**: CUDA を使うセットアップで既製エンジンが使えずビルドへ進む場合、または `--build` を指定した場合に `build_engine()` が `install_build_tools()` を呼び、`find_nvcc()` を実行します。すでにソース一致のローカルエンジンがあり再ビルド不要なら探索しません（`setup.py:7788-7798, 5905-5937`）。
- **画像生成エンジンのビルド**: `build_image_engine()` が CUDA backend をビルドする経路で探索します。該当エンジンが既に存在し build stamp が一致する場合は関数が探索前に戻ります（`setup.py:5004-5026`）。
- **GPU / toolkit 条件**: `install_build_tools()` は GPU architecture と `--cuda` の選択に応じて `find_nvcc(below=(13, 0))` または制限なしの `find_nvcc()` を呼びます。見つかった version が必要な下限未満ならビルド要件を満たしません（`setup.py:5663-5685`）。CUDA 世代の選択は `CUDA_HOME` より `--cuda`、または既定値となる `STRATA_CUDA` が担います（`setup.py:9163-9166, 9475-9478`）。
- **OS**: Windows では `.exe` を探索し、Windows の標準インストール先も候補に加えます。Linux では `nvcc` を探索し、`/usr/local/cuda*` と `/opt/cuda*` も候補に加えます（`setup.py:2231-2241`）。
- **他の指定との優先順位**: truthy な `STRATA_NVCC` があれば、それだけを調べて通常候補の探索を打ち切ります。指定ファイルが存在しない場合は警告後に通常探索へ進みます。ファイルは存在するが version を読めない場合、または `below` 条件に合わない場合は `(None, None)` を返して打ち切るため、`CUDA_HOME` へ fallback しません（`setup.py:2215-2230`）。

通常探索では PATH 上の `nvcc`、`CUDA_PATH`、`CUDA_HOME`、OS ごとの標準ディレクトリを候補にします。version 条件を満たす候補のうち**最も新しい version**を選びます。version が同じなら比較が厳密な `>` のため先に見つけた候補が残ります（`setup.py:2231-2249`）。したがって PATH や `CUDA_PATH` は同じ version の `CUDA_HOME` より先に採用されますが、より新しい version の `CUDA_HOME` があればそれが選ばれます。

## 実行時の詳細

値は `find_nvcc()` が呼ばれるたびに読み直され、関数内やモジュール内でキャッシュされません。通常のセットアップでは起動後の toolkit 検出時に評価されます。ツールが見つかれば、エンジン構築では選ばれた `nvcc` を `-DCMAKE_CUDA_COMPILER` に渡し、そこから Toolkit root を導出して `CUDAToolkit_ROOT` も設定します（root が `/usr` の場合は後者を省略）。CUDA 画像エンジンも選ばれた `nvcc` と root を CMake に渡します（`setup.py:5864-5870, 5936-5949, 5960-5968`）。CMake や CUDA compiler 側の環境変数解釈は Strata の挙動として扱いません。

有効な `nvcc` が見つからない場合、画像エンジンの CUDA ビルドは `compiling the image generator for NVIDIA needs the CUDA Toolkit (nvcc)` と案内し、セットアップを終了コード 1 で停止します（`setup.py:5021-5026, 904-909`）。エンジンビルドでは必要な build tools がない旨を表示し、確認でインストールを拒否すると `the build tools are needed` で停止します。インストール後も Toolkit が見つからない、または必要 version 未満の場合は `the CUDA Toolkit did not install` で停止します（`setup.py:5681-5695, 5739-5746`）。`CUDA_HOME` 自体が無効という警告は出しません。

## 根拠

- `setup.py:2215-2249` — `STRATA_NVCC` の先行指定、候補生成、`CUDA_PATH` / `CUDA_HOME` の読み取り、version 比較と選択。
- `setup.py:1000-1004` — `nvcc --version` 実行の timeout / OS error と stdout の取得。
- `setup.py:5660-5695, 5739-5746` — GPU・CUDA 世代に応じた toolkit の要件、build tools の案内と失敗経路。
- `setup.py:5905-5949, 5960-5975` — ローカルエンジンの再ビルド条件と CMake への compiler / Toolkit root の指定。
- `setup.py:5004-5026` — CUDA 画像エンジンの再利用条件と `nvcc` 探索・失敗経路。
- `setup.py:7772-7798` — 既製エンジン取得とビルドへの分岐。
- `setup.py:9163-9166, 9475-9478` — `--cuda` / `STRATA_CUDA` による CUDA 世代選択。
