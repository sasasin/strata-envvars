# `--build`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`./setup.sh`、`START-HERE.bat` などから起動） |
| オプション | `--build` |
| 別名 | なし |
| 値 | 値を取らないフラグ。既定値は `False` |

## 役割

通常の Linux/Windows setup で、利用可能な既製 Strata エンジンを選ぶ代わりに、この checkout のソースから GPU エンジンをコンパイルします。画像 encoder が必要な場合はそれもビルドします。CMake build にはテストを含めません（`setup.py:5570-5575`, `setup.py:5608-5614`）。

## 使い方

Linux では次のように指定できます。初回 setup を行い、エンジンとモデルの準備後にサーバーを起動せず終了します。

```sh
./setup.sh --build --no-start
```

Windows では `START-HERE.bat --build --no-start` を使います。`setup.sh` は引数を `setup.py` にそのまま渡し、Windows wrapper も同様に `%*` を渡します（`setup.sh:7-12,76`, `START-HERE.bat:44-55`）。

## 値と既定値

`argparse` の `action="store_true"` で定義されるため、値は不要で、未指定時は偽です。値の範囲や数値 validation はありません（`setup.py:8501-8501`）。

## 実行時の動作

- 通常の NVIDIA 経路では `--build` が真なら既製エンジンの取得を行わず、`build_engine()` に進みます。AMD HIP 経路（Linux）も同様にローカルビルドへ進みます（`setup.py:7383-7409`）。
- NVIDIA のビルドは選択 GPU のアーキテクチャに合わせて CMake/Ninja の `strata` target をビルドし、生成エンジンと必要なライブラリを `engine/` または CUDA 12 用 `engine-cuda12/` に置き、`BUILD.json` にソース fingerprint などを記録します（`setup.py:5570-5586`, `setup.py:5600-5641`）。HIP は `build-hip/` から実行ファイルを `engine/` にコピーし、build metadata を記録します（`setup.py:4510-4564`）。画像 encoder も要求されていて未ビルドなら、別の CMake target として作成されます（`setup.py:5624-5639`）。
- CUDA toolkit の選択は `--cuda`（または `STRATA_CUDA`）と GPU 世代に従います。`--prebuilt` は既製エンジンの場所を指定する設定ですが、通常経路では `--build` がその取得を迂回します（`setup.py:8509-8514`, `setup.py:7398-7409`）。
- ビルドツールが不足している場合、NVIDIA 経路は Windows で `winget`、Ubuntu/Debian で apt を使った導入を案内・実行し、その他の Linux では手動導入を要求します。CMake/Ninja が不足している場合は build 用 Python package の導入を試みます。`--yes` は推奨回答を受け入れ、確認を省くための別フラグです（`setup.py:5410-5458`, `setup.py:5464-5475`）。
- `--update` と併用した場合は、`update_install()` が `--build` を見て既製エンジン更新をスキップしますが、同関数内でコンパイルは実行しません（`setup.py:6682-6708`, `setup.py:8614-8619`）。

## 適用条件と副作用

- NVIDIA のコンパイルには CUDA Toolkit と C++ build tools が必要です。Windows では Visual Studio C++ build environment も必要です。HIP ビルドは Linux のみで、ROCm 環境・C++ compiler・git を必要とします（`setup.py:4532-4553`, `setup.py:5487-5501`, `setup.py:5410-5458`）。
- コンパイルは `build/`、`build-cuda12/`、`build-hip/` などの build directory と `engine/` または `engine-cuda12/` に成果物・metadata を書き込みます。足りないツールの導入では OS package manager や Python package の取得が起きます（`setup.py:5479-5501`, `setup.py:5602-5641`）。
- CPU に AVX2 がない場合は、通常の engine 選択に関わらず setup が `a.build = True` として互換 CPU 向けにコンパイルします。AVX2 非対応 CPU のサポートはソース上で experimental とされています（`setup.py:8845-8859`）。
- Windows の AMD HIP は `--build` を指定してもローカルコンパイルしません。既製 engine が選ばれずエラーとなり、Linux でのビルドまたは別途 `tools\hip\build_windows.bat` で作成した package の利用を案内します（`setup.py:7390-7396`）。
- `--backend sycl` は `sycl/setup_intel.py` へ処理を委譲します。SYCL engine は setup.py の `--build` で生成されず、事前に存在する `build-sycl-aot/strata` または `build-sycl/strata` を必要とします（`setup.py:8561-8564`, `setup.py:7321-7344`, `sycl/setup_intel.py:98-105`, `sycl/setup_intel.py:391-398`）。
- アプリ内 setup（`CONTROL`）の Mac 経路はエンジンをコンポーネントとして扱い、ここではビルドしません（`setup.py:8561-8562`, `setup.py:8236-8241`, `setup.py:7386-7388`）。
- DeepSeek-V4.1 の固有 engine 経路では、`--build` は配布 engine の取得・更新を抑止しますが、setup.py はその engine をコンパイルしません。既存の engine がなければ engine 不在で失敗し、既存の engine があればそれを使います（`setup.py:7947-7951`, `setup.py:8041-8058`）。

## 出力とエラー

通常経路では setup が手順・コマンドを表示します。ビルドコマンドが失敗すると一度再試行し、再試行も失敗した場合は `run()` が失敗コマンドと終了コードを表示して `Setup stopped` を出し、終了コード 1 で停止します（`setup.py:5485-5501`, `setup.py:880-899`, `setup.py:825-830`）。ビルド後に既存の古いバイナリが残っていると判定された場合も、engine を入れ替えず失敗します（`setup.py:5615-5618`）。

## 根拠

- parser と既定値: `setup.py:8501`
- ラッパーからの引数委譲: `setup.sh:7-12,76`, `START-HERE.bat:44-55`
- CUDA/HIP の既製版選択と build dispatch: `setup.py:7383-7415`
- CUDA build、metadata、成果物配置: `setup.py:5570-5641`
- HIP build と成果物配置: `setup.py:4510-4564`
- build helper、再試行、失敗の終了コード: `setup.py:5479-5501`, `setup.py:880-899`, `setup.py:825-830`
- 特殊経路（update、Mac、SYCL、DeepSeek）: `setup.py:6682-6708`, `setup.py:8236-8241`, `setup.py:7321-7344`, `setup.py:7947-8058`

調査範囲は上記 revision の checkout 内の `setup.py` と該当 wrapper / SYCL setup 実装です。実機での build、各 OS の toolchain 導入結果、GPU 実行は確認していません。
