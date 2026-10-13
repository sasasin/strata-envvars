# `CUDA_PATH`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strata のセットアップが CUDA エンジンをローカルビルドするとき、CUDA Toolkit の `nvcc` を探す候補ディレクトリを追加します。`CUDA_PATH` 自体を実行エンジンへ渡したり、推論時に読み直したりするコードはありません。セットアップが既製エンジンを取得してビルドツールを探さない経路では、この変数は参照されません。

## 値と判定

`setup.py` の `find_nvcc()` は `os.environ.get("CUDA_PATH")` が truthy の場合だけ候補に加えます。unset と空文字は候補に加わりません。値は空白除去や展開をせず `Path(value) / "bin" / nvcc名` に使います。Windows では `bin/nvcc.exe`、それ以外では `bin/nvcc` を候補にします。パスの存在確認後、その実行ファイルの `--version` 出力から `release <major>.<minor>` を正規表現で探し、版を判定します。存在しない候補や版を読み取れない候補は採用されません。

`CUDA_PATH` は単独の強制指定ではありません。`STRATA_NVCC` が truthy ならそちらだけを調べ、`CUDA_PATH` は候補探索に使われません。そうでなければ PATH 上の `nvcc`、`CUDA_PATH`、`CUDA_HOME`、さらに OS ごとの既定ディレクトリを候補にします。候補の位置ではなく、条件に合う中で最も新しい major/minor 版を選びます。同じ版なら候補順で先に見つかったものが残ります。CUDA 12 用に `below=(13, 0)` が指定された探索では 13.0 以上は候補外です。

根拠: `setup.py:1353-1387`。

## 有効になる条件

- `install_build_tools()` が呼ばれるビルド経路で参照されます。セットアップで engine をビルドする際に呼ばれ、対象 GPU / 選択 toolkit に応じて通常探索または CUDA 13.0 未満に限定した探索を行います。必要な版が見つからないとセットアップは不足を報告し、ツールキットのインストールを案内します。
- `find_nvcc()` の候補が見つかっても、呼び出し元が要求する最低版より古い場合はビルド用として受け入れられません。CUDA 12 経路では GPU に応じて 12.0 または 12.8 以上が必要です。CUDA 13 経路では通常 12.0 以上、sm_120 を含む場合 13.0 以上が必要です。
- `STRATA_NVCC` を設定した場合は専用パスが優先され、`CUDA_PATH` を含む通常探索は行われません（指定先が存在しない場合は警告後、通常探索に戻ります。存在するが `--version` から版を読めない場合は `(None, None)` となり、通常探索へ戻りません）。

## 実行時の詳細

`find_nvcc()` は呼び出されるたびに環境を調べ、結果を static cache しません。`install_build_tools()` が返した `nvcc` のパスは CMake の `-DCMAKE_CUDA_COMPILER=...` と、`/usr` 配下以外では `-DCUDAToolkit_ROOT=...` に使われます。したがって `CUDA_PATH` の直接の効果はビルドに使う compiler / toolkit の選択です。CUDA の実行時ライブラリを環境変数から設定する処理ではありません。

`CUDA_PATH` 候補が不在、または版を読み取れない場合の専用ログはありません。選択した CUDA 版はセットアップが `build tools present (CUDA M.m)` と表示します。必要条件を満たせない場合は、別途不足ツールの案内またはエラーになります。既に一致するローカルビルド済み engine があり再ビルド不要なら、`build_engine()` はツール探索より前に戻るため、その呼び出しでは `CUDA_PATH` は評価されません。

根拠: `setup.py:3211-3245,3279-3286,3381-3423`。

## 文書との照合

`docs/OLDER_GPUS.md:81-82` は CUDA 12 のビルドで `STRATA_NVCC=<path to nvcc>` により Toolkit を指定できると説明しています。`CUDA_PATH` の探索候補としての役割を詳述する文書は確認できませんでした。同文書の指定方法は `find_nvcc()` の実装と一致します。

## 根拠

- `setup.py:1353-1387`: `STRATA_NVCC` の優先、`CUDA_PATH` と他候補の組み立て、版の検査と選択。
- `setup.py:3211-3245,3279-3286`: 対象 GPU / toolkit に応じた探索と最低版確認。
- `setup.py:3381-3423`: 再ビルド要否の判定、compiler と toolkit root を CMake に渡す処理。
- `docs/OLDER_GPUS.md:81-82`: CUDA 12 ビルドの Toolkit 選択に関する説明。
