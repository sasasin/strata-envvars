# `LD_LIBRARY_PATH`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

Strata のソースでは、この値を実行時に単独で解釈して機能を切り替えるのではなく、主にビルド・起動する子プロセス向けの環境を組み立てる際に使う。既存値を引き継ぎながら ROCm/Vulkan SDK やエンジンパッケージ、設定で指定されたライブラリ用ディレクトリを追加する用途と、Linux AppImage の外部プログラム起動時に AppImage 内のパスを除く用途がある。ライブラリ探索そのものの挙動は OS のローダー側に属するため、ここでは扱わない。

## 値と判定

- Strata の Python コードでは環境辞書の `LD_LIBRARY_PATH` を文字列として読み、存在して非空かを `env.get(...)` で判定する箇所がある。特定の値や数値形式は要求しない。
- 追加パスは `os.pathsep`（Unix では `:`）で連結し、既存値の前または後ろに置く。設定ディレクトリがない場合は、コードにより既存値をそのままにするか、空値を連結した結果から末尾区切りを取り除く。
- `serve/images.py` と `serve/server.py` は Windows では `PATH` を選ぶため、Windows 上では `LD_LIBRARY_PATH` を更新しない。`strata_control.updater.binary_smoke()` は Windows で `PATH`、macOS で `DYLD_LIBRARY_PATH`、それ以外で `LD_LIBRARY_PATH` を選ぶ。一方 `strata_control.tuning.engine_env()` や一部ツールは Windows 以外を `LD_LIBRARY_PATH` として扱う。
- 環境変数名はコード上で大文字小文字を区別して指定される。Strata のコードに、空白除去やパス要素の正規化を一律に行う処理はない。

## 有効になる条件

- セットアップでは ROCm ビルド経路、Vulkan SDK のセットアップ、および HIP の画像エンジン経路で SDK のディレクトリを追加する。これらの処理が選ばれない場合、このセットアップコードによる変更はない（`setup.py:4619-4626,4690-4695,4796-4799,4842-4846`）。
- サーバーと画像処理の子プロセスでは、設定の `lib_dirs` のうち実在するディレクトリがある場合だけ、子プロセス用環境に追加する（`serve/server.py:3528-3537`, `serve/images.py:131-150`）。
- `strata_control.tuning.engine_env()` はエンジンの隣に `engine-component.json` がある場合のみパッケージ用環境を返し、そのフォルダーと `BUILD.json` の相対 `lib_dirs` のうち存在するものを前置する。通常のエンジンでは `None` を返し、呼び出し元環境のままになる（`strata_control/tuning.py:189-202`, `strata_control/engine_component.py:155-171`）。
- Linux AppImage 内から外部プログラムを起動する環境では、元の起動環境が記録されていればそれを使う。記録がない場合は `APPDIR` 以下を指す `LD_LIBRARY_PATH` の要素だけを除き、空になれば変数自体を削除する。AppImage 外では環境をコピーし、変更しない（`apps/host/server/external-env.mjs:43-57,63-71`）。

## 実行時の詳細

- `serve/server.py` と `serve/images.py` は `os.environ`（または渡された基底環境）を複製し、既存の `LD_LIBRARY_PATH` が非空なら設定されたライブラリディレクトリの後ろに連結する。画像処理側ではその後 `cfg.env` の値を反映するため、設定に `LD_LIBRARY_PATH` があれば追加した値を上書きできる（`serve/images.py:134-150`）。サーバー側は HIP 環境ガードなどを続けて適用する（`serve/server.py:3528-3537`）。
- エンジン更新時の `binary_smoke()` はパッケージ内ライブラリディレクトリを既存値の前に連結した環境で `<engine> --version` を実行する。パッケージ化エンジンのチューニング実行も同様に既存値を後ろへ置く（`strata_control/updater.py:746-754`, `strata_control/tuning.py:195-202`）。
- `setup.py` の HIP/Vulkan セットアップは `os.environ` 自体を更新し、その後のビルドやサブプロセスに SDK パスを引き継ぐ。HIP では SDK の `dirs` を既存値より前へ、Vulkan では `VulkanLoader/lib` を前へ置く。HIP の一部では空の既存値を末尾から除去する（`setup.py:4623-4626,4692-4695,4796-4799,4844-4846`）。
- `packaging/collect_libs.py` は `--search` の各パスを先頭にした環境辞書を作り、`ldd` に渡す（`packaging/collect_libs.py:85-89`）。`tools/batch_test.py`, `tools/quant_quality.py`, `tools/trellis/sanity_greedy.py`, `tools/dsv41/tune.py` も設定のライブラリディレクトリを既存値より前に置いた環境で子プロセスを起動する（各ファイル `:56`, `:113,189`, `:39`, `:85-91`）。`tools/dsv41/mkprompts.py` は起動時の値を読み、tokenizer 子プロセスの環境に同じ値を明示して渡す（`:19-26`）。
- `packaging/build_hip_gfx1103.sh` は SDK の `lib`, `lib/rocm_sysdeps/lib`, `lib/llvm/lib` を前置して export する（`:11`）。
- パス追加はそれぞれの関数・スクリプト実行時に行われる。値を読むコードがプロセス起動後に変更された環境変数を監視する処理は確認できない。子プロセスへの適用範囲は、その起動時に `env` として渡された環境に限られる。

## 文書との照合

`docs/STRIX_HALO.md:55-58` は ROCm SDK の3ディレクトリを `LD_LIBRARY_PATH` の前に追加するシェル例を示し、`docs/AMD_HIP.md:614-616` は ROCm ライブラリディレクトリを設定してチューニング実行する例を示す。これらは利用例であり、Strata のコードにおける全ての子プロセス環境構築を列挙する説明ではない。`docs/DETAILS.md` に本変数の詳細な仕様説明は見当たらない。

## 根拠

主な環境の組み立ては `serve/server.py:3528-3537`, `serve/images.py:131-150`, `strata_control/engine_component.py:155-171`, `strata_control/updater.py:746-754`, `strata_control/tuning.py:189-202`。SDK セットアップは `setup.py:4619-4626,4690-4695,4796-4799,4842-4846`、パッケージ検査は `packaging/collect_libs.py:85-89`。AppImage 外部環境の処理は `apps/host/server/external-env.mjs:43-57,63-71`。
