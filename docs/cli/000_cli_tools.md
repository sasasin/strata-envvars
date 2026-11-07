# Strata の CLI・実行ファイル・配布物

この文書は、Strata の利用者向け入口、ビルド生成物、GitHub Release の配布物と設置先を整理します。CLI 引数や全ての開発用スクリプトの網羅は対象外です。

> **`strata` の名前に注意:** Python の Strata Terminal は `strata` コマンド（wrapper は `bin/strata` / `bin/strata.cmd` / `bin/strata.ps1`）から `strata.py` を実行します。推論エンジンも CMake ターゲット `strata` で、Linux/macOS では `strata`、Windows では `strata.exe` です。Docker イメージ内にも `/usr/local/bin/strata` が入りますが、これは同梱 Terminal への wrapper（`docker/strata-wrapper.sh`）です。デスクトップアプリは Tauri の GUI で、別の配布物です。

## 利用者向け入口と設置先

| 役割 | ソース上の入口 | 生成・配布経路 | 配布時の名前 | 主な設置・実行場所 |
| --- | --- | --- | --- | --- |
| ソース checkout のセットアップ | `setup.sh` → `setup.py`; Windows は `START-HERE.bat` → `setup.py`。`SETUP.bat` は同 bat を `--setup` 付きで呼ぶ | checkout 同梱。開発・ソース利用向けで、Release 用 GUI installer ではない | `setup.sh`, `START-HERE.bat`, `SETUP.bat` | clone したリポジトリ。通常 `.venv/` または `.venv\Scripts\` を使う |
| checkout 更新・ベンチ補助 | `update.sh`, `UPDATE.bat`, `bench.sh`, `BENCH.bat` | checkout 同梱 | 同名スクリプト | clone したリポジトリ内から実行 |
| Strata Terminal CLI | `strata.py`, `strata_cli/`, `strata_control/`, `serve/`; wrapper は `bin/strata`, `bin/strata.cmd`, `bin/strata.ps1` | ソース checkout では既存 Python 環境を利用。Release installer（`install.sh` / `install.ps1`）は `install-manifest.txt` の行を見て Control archive を選び、SHA-256 を検証して展開し、展開後に署名付き feed を検証する。`install.sh` の GPU 判定は v0.2.10 で強化された（`nvidia-smi` が exit 9 で stdout にエラー文を出した場合をカード無し扱い、`lspci` は PCI クラス名で判定） | コマンド `strata`; POSIX wrapper `bin/strata`, Windows wrapper `strata.cmd` / `strata.ps1`; Release archive は `strata-control-<version>-<platform>.tar.gz`（Windows は `.zip`）。`packaging/package_terminal.py` が作る別名は `strata-terminal-<version>-<target>.tar.gz|zip`（同梱 Control archive の README がその名で展開手順を書いている） | POSIX は既定で `~/.local/share/strata/terminal/<version>/`（`STRATA_DATA_DIR` / `$XDG_DATA_HOME` で変更可）に展開し、`terminal/current` symlink と `~/.local/bin/strata`（既定、`STRATA_BIN_DIR` で変更可）を張る。Windows は `%LOCALAPPDATA%\Strata\terminal\<version>\` に展開し、`terminal\current` を `mklink /J` で作って `%LOCALAPPDATA%\Strata\terminal\current\bin` をユーザー PATH に追加（`STRATA_NO_PATH=1` で抑止）。checkout では repo と `.venv` |
| Strata デスクトップアプリ | Tauri shell `apps/desktop/src-tauri/`; Node App Host/UI は `apps/host/` | Tauri bundle と Release workflow。Windows/Linux installer は engine を含まず、初回起動時に engine component を取得。macOS は小型 Metal engine を `engine-bundle/` に同梱（app 更新 archive にも同梱される構成。今回の `Strata.app.tar.gz` は未展開）。同梱 Node runtime は `apps/desktop/scripts/fetch-node.sh` / `.ps1` が `STRATA_NODE_VERSION` 既定 24.12.0 を取得 | 現行 v0.2.12: `Strata-0.2.12-windows-x64-setup.exe`, `Strata-0.2.12-linux-x86_64.AppImage`, `Strata-0.2.12-macos-arm64.dmg`, 更新用 `Strata.app.tar.gz` | Windows installer は current-user install で既定 `%LOCALAPPDATA%\Programs\Strata`（`nsis/installer.nsi`）。Windows では `host/`, `control/`, `node/`, `harness/`, `engine-bundle/` が exe と同じフォルダに置かれる。macOS は `Strata.app/Contents/Resources/` 直下（現行 app archive は未展開）。Linux deb/AppImage では `<prefix>/lib/Strata`（`src/main.rs` の `packaged_resource_dir`）。ユーザーデータと engine component は別のユーザー領域 |
| 推論エンジン component | CMake target `strata`、入口 `src/program/generate.cpp`（SYCL は `sycl/`、Metal は `metal/`）。全カード分割 engine `strata-split-N` は `src/split/`（v0.2.10 で追加、sFNX 由来） | `setup.py` のソースビルド、`packaging/build_*.sh` / `.bat` と `package_engine.py` による package。Release feed に署名付き engine archive。`strata-split-N` は engine package に同梱する別実行ファイルで（`packaging/build_split_cuda.sh` / `build_split_hip.sh` が作り、`packaging/build_hip_linux.sh` の `SPLIT_DIR` が stage に足す）、独立した Release asset や feed 節は無い | `strata-engine-<version>-<platform>-<backend>[-<variant>].tar.gz`。別の package の DeepSeek engine は `strata-dsv41-<version>-<platform>-<backend>[-<variant>].tar.gz`（Linux AMD 版は `packaging/build_dsv41_hip_linux.sh` が作る）。分割 engine の実行ファイル名は `strata-split-<2|3|4>`（NVIDIA は `strata-split-N-sm<cc>`、AMD は `strata-split-N-<arch>`） | ソース build directory。アプリ/Terminal 利用時は component store の `engine/<version>-<platform>-<backend>[-<variant>]/`。Windows `%LOCALAPPDATA%\Strata\components`、POSIX `$XDG_DATA_HOME/strata/components`（既定 `~/.local/share/strata/components`）。`STRATA_COMPONENTS_DIR` で上書き可。DeepSeek engine は同じ store の `engine-dsv41/` に別領域 |
| Docker イメージ | 既製の engine package を使う `docker/Dockerfile` と、エンジンを作る `Dockerfile`（リポジトリ直下、`docker build -t strata:src .`）。`docker/build.sh`, `docker/publish.sh`, `docker/fetch-engines.py`, `docker/entrypoint.sh`, `docker/strata-wrapper.sh`, `docker/healthcheck.sh`, `docker/smoke-test.sh`, `docker/compose/*.yml` | GitHub Actions `.github/workflows/docker-images.yml` が `docker/publish.sh` を flavor ごとに呼び、ghcr に push。イメージは Release の engine package を signed feed 経由で検証して取り込む | `ghcr.io/niko1221/strata:<version>-<flavor>` と `:latest-<flavor>`。flavor は `cuda13`, `cuda12`, `rocm-gfx120x`, `rocm-gfx110x`, `rocm-gfx1151`, `sycl` | `docker run` で起動。イメージ内は Terminal が `/opt/strata/terminal`、engine が `/opt/strata/components/engine/`（`STRATA_COMPONENTS_DIR=/opt/strata/components`）、`strata` が `/usr/local/bin/strata`。データは volume `/data`、ポート 8080。`docker exec <name> strata ...` で Terminal が使える |
| CMake 診断・開発プログラム | 各 `CMakeLists.txt` の `add_executable`（root だけで 295 件、`sycl/` 39 件、`metal/` 5 件、`src/split/` 5 件） | backend・オプション・テスト設定により build directory に生成。通常の GUI/Terminal 製品コマンドではない | 例: `strata-plan`, `strata-gguf`, `strata-dequant`, 条件付き `strata-device`, `strata-load`, `strata-concurrent`, `strata-overlap`, `strata-q36`, `strata-q36ref`, `strata-dsv41`, `strata_ds4` (Metal), `strata-vision` / `strata-vision-hip` / `strata-vision-sycl`, `src/split/` の開発用 `split_fnx_run`・`split_convert_dump`（製品実行ファイル `strata-split-2/3/4` は上の「推論エンジン component」行） | build directory。Release の archive に入るのは engine package が採るファイルだけ（下記） |

Terminal の `strata` wrapper は同梱 Python runtime（`python/`）を優先し、checkout では `.venv` または PATH の Python 3.10 以上を使います。wrapper 自体は pip install も download も行いません。Release の `install.sh` / `install.ps1` は常駐 CLI ではなく、manifest を読んで Control archive を導入する installer です。モデルと engine は別途管理され、Terminal の `strata launch` は選択した GPU に合う engine を feed から取得します。

Control 自身の更新は component store に入り、`components/control/active.json` が切り替わります（`packaging/UPDATES.md`, `strata_control/updater.py`）。Linux ARM64（NVIDIA DGX Spark）の Terminal は `strata-feed-linux-aarch64.json` を読み、他のマシンは `strata-feed.json` を読みます（`strata_control/feed.py` の `FEED_NAME` / `AARCH64_FEED_NAME`）。

全カード分割 engine（`strata-split-N`）は、エンジン package 内に `strata` と並ぶ実行ファイルとして入っている場合に限り、`strata_control/split_engine.py` がカード数・compute capability・expert 型から起動を判断します。package に無いときは `this engine package has no strata-split-N` を返して通常の layer split に留まり、起動失敗時も `serve/server.py` の "split_fallback" で通常の layer split に戻ります（`strata_control/split_engine.py:1-60,403-497`, `serve/test_split_fallback.py`）。

## 現行 GitHub Release の実物（v0.2.12）

GitHub Releases API の `/repos/Niko1221/Strata/releases/latest` を確認しました。latest は **v0.2.12**（公開 `2026-11-07T08:54:40Z`、asset 42 件）。Strata checkout の HEAD `146df3c468739147f520ac3816de806f71232571` は tag `v0.2.12` と同じ commit です。アプリ / Terminal は 0.2.12、Control と engine は 0.1.58 です。

asset 名・サイズ・API の SHA-256 digest:

| asset | サイズ | digest | 区分 |
| --- | ---: | --- | --- |
| `install-manifest.txt` | 545 B | `sha256:57118596d2b67e9b1fe3927f887402f94706f1b827ed580e02db0cda7d59a55f` | Feed / installer |
| `install.ps1` | 12,124 B | `sha256:322ad52bddc137893b6091f4e8ff989cd87ba968e063e5b08e43e167480343fc` | Feed / installer |
| `install.sh` | 8,646 B | `sha256:d47754af1f74c95bf763e0b8d484232443466decd1a22d0be3208760a2f53822` | Feed / installer |
| `latest.json` | 2,134 B | `sha256:b1df9932d6af755fe6d5a0278c2e4c573cbd2f2122fdadaab39f737e69131578` | Feed / installer |
| `qwen3.8-flash-next-dflash2.strata1.q4_0-bf16sel.pack` | 522,458,112 B | `sha256:34ca17fee701ff088b6069acc35a26661d237953f5d114be0a3f7dae3ec5cda9` | DFlash2 pack |
| `qwen3.8-flash-next-dflash2.strata1.q4_0-selq4.pack` | 339,694,592 B | `sha256:4df2e5ab2b47c064afbe662e16e4f06569877125c2d0e2123a4ac755266c664c` | DFlash2 pack |
| `SHA256SUMS.txt` | 4,394 B | `sha256:2e20d14231c29c0c59692a6b02e547db2d0dd62e093e7216fa8630c56342d565` | Feed / installer |
| `Strata-0.2.12-linux-x86_64.AppImage` | 305,072,632 B | `sha256:364200a5f43bf8d5da37041929589ecb0064014be167e3388470c2d2089c092b` | GUI / updater |
| `Strata-0.2.12-linux-x86_64.AppImage.sig` | 428 B | `sha256:93f5a8a04bd378bb739e59da815d6c349fd7f4773563fb2063bcdd8b5671565e` | GUI / updater |
| `Strata-0.2.12-macos-arm64.dmg` | 168,977,357 B | `sha256:79b83a3e3869b464a7b4a9cecb3895d6aa4bde8bd70f99077be4831db2f6e924` | GUI / updater |
| `Strata-0.2.12-windows-x64-setup.exe` | 113,032,536 B | `sha256:b56eb5692aa826e0aa8ae5d4819ddee1745e1522822738748c3b6c5a7643b1ff` | GUI / updater |
| `Strata-0.2.12-windows-x64-setup.exe.sig` | 428 B | `sha256:eb2f833f47d7e3c520c8533912fc6ab1c68e315731e550ef8dbd75f5adf6526e` | GUI / updater |
| `strata-control-0.1.58-linux-aarch64.tar.gz` | 83,895,276 B | `sha256:8a813e0728e5a563d1d75a2643127cc40a2504240801b53ba9222204acab2f8f` | Control |
| `strata-control-0.1.58-linux-x86_64.tar.gz` | 99,974,029 B | `sha256:fcce4c7b90f59c4f10f16181a7190b3abe79faadbc9eef38278fdc635e028817` | Control |
| `strata-control-0.1.58-macos-arm64.tar.gz` | 51,117,393 B | `sha256:8c8452c578f25f2ca9331db20defd28090eb7a7dd232382cd1538867d48da3f2` | Control |
| `strata-control-0.1.58-windows-x86_64.zip` | 73,442,655 B | `sha256:5a927d2b2ac61a9d6963fb17b46819f0bbd779875d1f9a6ba0e07834b350077b` | Control |
| `strata-dsv41-0.1.58-linux-aarch64-cuda-cuda13.tar.gz` | 554,500,945 B | `sha256:d7d0e21ac5eb72ab046129487734cd8aa22ea199e5292f52ce75c9ebaa28e635` | DeepSeek engine |
| `strata-dsv41-0.1.58-linux-x86_64-cuda-cuda13.tar.gz` | 445,222,950 B | `sha256:8ff96186db086b525c716a92f81e7d59e3cb2a0383aa4198ce0ddf14b7473c43` | DeepSeek engine |
| `strata-dsv41-0.1.58-linux-x86_64-hip-rx9070.tar.gz` | 367,074,126 B | `sha256:22e6f835a97fcb68c36c003b5a33374a80bec5033f9ec393e52bd510139c2f4d` | DeepSeek engine |
| `strata-dsv41-0.1.58-macos-arm64-metal.tar.gz` | 1,806,338 B | `sha256:4141eb6c9650f8b7100b25a64e49ec037c0f7120c7f71975265d17d149675d00` | DeepSeek engine |
| `strata-dsv41-0.1.58-windows-x86_64-cuda-cuda13.tar.gz` | 422,615,818 B | `sha256:7cb13673a6fe809fff327e29f26ef06cb8e9c069ff0330d1d6a67fdc97ced368` | DeepSeek engine |
| `strata-dsv41-0.1.58-windows-x86_64-hip-rdna3.tar.gz` | 137,202,765 B | `sha256:f8c78bdd5462d4a6588b768b722fc03fb381301158141368b7a1f9e93a531479` | DeepSeek engine |
| `strata-engine-0.1.58-linux-aarch64-cuda-cuda13.tar.gz` | 660,847,685 B | `sha256:fa0a587bb686fe54c565f3c109308b0db62f233d6ba50d02929b57a9b3c8ff89` | Engine |
| `strata-engine-0.1.58-linux-x86_64-cuda-cuda12.tar.gz` | 949,795,474 B | `sha256:a0e068d6c79b30a0126ae015e9d61e39ad3b2b2b48d61e6b543bd2fc2dee5d2f` | Engine |
| `strata-engine-0.1.58-linux-x86_64-cuda-cuda13.tar.gz` | 723,463,241 B | `sha256:bbbfa8260125b94591cae30747cb0e4a9cee26d9cb0b2e284e33000c91509d54` | Engine |
| `strata-engine-0.1.58-linux-x86_64-hip-halo.tar.gz` | 248,033,930 B | `sha256:1ce376c443ef662c72cd1fc4f828e093f78f83498c946837ca22cc250eda8861` | Engine |
| `strata-engine-0.1.58-linux-x86_64-hip-rx6000.tar.gz` | 205,715,113 B | `sha256:45d96cb6c04b3c545ff04a8729061eebf64fd7b00f376fe30a68e38f8ac41e34` | Engine |
| `strata-engine-0.1.58-linux-x86_64-hip-rx7900.tar.gz` | 329,339,566 B | `sha256:7d83a7739ae16bc6065b42bb379c667d176aec8fded5fa52153c754adb9c360c` | Engine |
| `strata-engine-0.1.58-linux-x86_64-hip-rx9070.tar.gz` | 674,532,064 B | `sha256:f0bc19645618cfb27986a2c9ee413bd9cd5a00661dee0ff1c08358acda319471` | Engine |
| `strata-engine-0.1.58-linux-x86_64-sycl.tar.gz` | 187,573,672 B | `sha256:2a32d61383327073a8d4d81682d18678cd344fb331d4c5979d57d849d6b6b219` | Engine |
| `strata-engine-0.1.58-macos-arm64-metal.tar.gz` | 5,530,901 B | `sha256:9b2352fb6f4d2597e0e37b02cf13122949a7cf4e23a538b302065d21940890c6` | Engine |
| `strata-engine-0.1.58-windows-x86_64-cuda-cuda12.tar.gz` | 918,773,207 B | `sha256:adf8fd7a2688b1fbca9f67d081e130fed6f17d08f7294991c691fdba22cc1ec0` | Engine |
| `strata-engine-0.1.58-windows-x86_64-cuda-cuda13.tar.gz` | 630,769,464 B | `sha256:3311443ba9172154adc99c48668c4187d60864e3b6cafe5d9aa39b035e4f9f34` | Engine |
| `strata-engine-0.1.58-windows-x86_64-hip-rdna2.tar.gz` | 175,007,482 B | `sha256:d3f38574beca88acede9260adac5d644a7fb140dacd8c05b9f989bb08325109e` | Engine |
| `strata-engine-0.1.58-windows-x86_64-hip-rdna3.tar.gz` | 282,837,701 B | `sha256:e828afca54ef7e59da43d812158bd4b39700ff3a49cbe20cbcd82ed01a167215` | Engine |
| `strata-engine-0.1.58-windows-x86_64-hip-rx9070.tar.gz` | 570,895,877 B | `sha256:4c9d585e1e561e19129f301f5ae516d3ae9f60b959e08b432442095549380a4d` | Engine |
| `strata-feed-linux-aarch64.json` | 2,826 B | `sha256:9f8fd73b1ce71edc95ba3ce7e295d2bf0fe844bb4fe004df050b82c1a6a0fe19` | Feed / installer |
| `strata-feed-linux-aarch64.json.sig` | 151 B | `sha256:29b511ffcb956f82dfb539d0cfec402675d8863b1d00f9806c8865a7ac9ba95d` | Feed / installer |
| `strata-feed.json` | 16,498 B | `sha256:77bf5e7b86bb73abdce88a1159f76f2abef233856f9fc9f10890a7a31cda470d` | Feed / installer |
| `strata-feed.json.sig` | 151 B | `sha256:47a068d404ae051ea514b9d7992f7112eb0493955286ef91b703655b872f7efe` | Feed / installer |
| `Strata.app.tar.gz` | 168,850,410 B | `sha256:2595ad717e622375a3da5fd762207781ccbe38f548b75393d34e9b08f6949b37` | GUI / updater |
| `Strata.app.tar.gz.sig` | 404 B | `sha256:ebd980ad93301e85302044da82982d46aaaa2b813a7fdc873bcf5f3f08bd890c` | GUI / updater |

`install-manifest.txt` は 545 B で Control 0.1.58 の4 platform を列挙し、`latest.json` は 2,134 B で app version 0.2.12 を示します。`strata-feed.json` は 16,498 B、sequence 122、generated_at `2026-11-07T08:11:58Z` で、Control 0.1.58、13 engine packages、5 DeepSeek packages、app 0.2.12 と DFlash2 drafter packages を持ちます。`strata-feed-linux-aarch64.json` は 2,826 B、同 sequence 122 で、DGX Spark 用の Control / engine / DeepSeek package を各1件含みます。`SHA256SUMS.txt` は 4,394 B です。

Release metadata と小さな archive をダウンロードし、API `digest` と全て SHA-256 が一致することを確認しました（`install-manifest.txt`, `latest.json`, `SHA256SUMS.txt`, 両 feed JSON、macOS Control / Engine / DeepSeek archive）。macOS engine archive は 46 entries、DeepSeek archive は 42 entries で、engine archive は `strata`, `strata-vision`, `engine-component.json`, `BUILD.json`, `metal/engine-msl/`, `metal/data/` を含みます。DeepSeek archive の実行ファイルは `strata-dsv41` です。Control archive は 51,117,393 B、4,670 entries でした。Windows / Linux の大容量 installer と engine archives、および `Strata.app.tar.gz` は未展開です。

## Release v0.2.12 と checkout HEAD の差、および直前の索引調査からの変化

前回の索引調査は v0.2.10 Release と tag 後の checkout `9f7d977d…` を対象にしていました。今回は Release tag と HEAD が一致します。API は installer、Control、engine、DeepSeek、feed、署名、2種類の DFlash2 pack を含む42 assetを返しました。Control と engine は 0.1.56 から 0.1.58、app は 0.2.10 から 0.2.12 へ進み、feed sequence は 120 から 122 です。

- Release notes と現行 source は tuned DFlash2 drafter の配布、prompt / engine 更新、Terminal・GUI 修正を含みます。`install-manifest.txt` と feed の実データで component version を照合しました。
- CLI parser 索引で利用者向け command / option の増減はありません。CLI inventory の増加19文字列は packaging helper と bench / test parser に限定されます（詳細は `docs/cli/README.md`）。
- Docker image tag は今回確認していません。Release API の asset 一覧や source の build 手順から公開 image の有無を推測しません。

### 実体を確認できていない項目（推測しない）

- Windows / Linux の GUI installer、AppImage、DMG、`Strata.app.tar.gz` と大容量 engine / DeepSeek archives は展開していません。package 内部のファイル構成は source の staging 規則から Release の実体として断定しません。
- Docker の現行 GHCR tag / manifest digest は未確認です。
- Windows 向け Control archive は未展開です。`install.ps1` の asset digest は API で確認しましたが、展開後の内部構成は確認していません。

## ビルド生成物と配布対象の区別

- root `CMakeLists.txt` は CUDA / HIP を有効にした時にエンジン `strata` を `src/program/generate.cpp` から作ります。`strata-plan`, `strata-gguf`, `strata-dequant` は backend 非依存で定義され、`strata-device`, `strata-load`, `strata-concurrent`, `strata-overlap` は CUDA / HIP が ON のブロック内、`strata-q36ref` / `strata-q36` は Qwen3.5/3.6 のブロック（`NOT STRATA_HIP_GFX906`）、`strata-dsv41` は `option(STRATA_BUILD_DSV41 …)` が ON かつ gfx906 以外の時に定義されます。root には 295 件の `add_executable` があり、`*_parity`, `*_bench`, `*_test` は診断・検証用です。ターゲット定義だけで Release 配布を意味しません。
- backend 別のエンジン入口は別ファイルです: `sycl/CMakeLists.txt` の `add_executable(strata …)`（39 件）、`metal/CMakeLists.txt` の `add_executable(strata …)` と `add_executable(strata_ds4 …)`（`packaging/mac/build_dsv41_engine.sh` が `strata_ds4` を `strata-dsv41` として staging する）。
- 全カード分割 engine は `src/split/CMakeLists.txt` が `STRATA_BUILD_SPLIT` と `STRATA_SPLIT_CARDS` / `STRATA_SPLIT_ARCH` で作ります（`strata-split-2/3/4`）。`STRATA_BUILD_TESTS` が ON の時に `split_*_test`, `split_convert_dump`, `split_moe_tile_test`, `split_fnx_run` が増えます（開発用）。package への取り込みは `packaging/build_split_cuda.sh` / `build_split_hip.sh` が作った実行ファイルを、`package_engine.py` の `--include` グロブ（option 定義 `packaging/package_engine.py:311`、手順コメント `packaging/build_split_cuda.sh:3-4`）で engine package の stage に足すか、`packaging/build_hip_linux.sh:109-110` の `SPLIT_DIR` で `strata-split-*-amd` を copy する経路です。製品 CLI 索引では `strata-split` tool-id として `src/split/tools/sfnx.cpp:72-105` の parser を載せます（`docs/cli/README.md`）。
- 画像読み取りは `tools/vision/CMakeLists.txt` の `strata-vision` で、`STRATA_VISION_HIP` / `STRATA_VISION_SYCL` を付けるとそれぞれ `strata-vision-hip` / `strata-vision-sycl` という別プログラムになります。`package_engine.py` は `strata-vision[.exe]` と `strata-vision-hip[.exe]` を package に取り込みますが、SYCL package には picture reader が入っていません（0.1.55 を展開して実測）。`--no-picture-reader` で意図的に外す経路もあります。
- `packaging/README.md` の target matrix と `packaging/build_*.sh` / `.bat` が backend ごとの engine package 作成手順です。`package_engine.py` が build folder を component package にし、`feed_tool.py` が feed entry と archive 名（`pack-engine --prefix strata-engine` または `strata-dsv41`、`pack-control` で `strata-control-<version>-<platform>`）を作ります。engine package の形は `packaging/ENGINE-COMPONENT.md`（schema 2 の manifest、`<components>/engine/<version>-<platform>-<backend>[-<variant>]/`、`files` の全 SHA-256、署名方針）。
- `apps/desktop/src-tauri/tauri.conf.json` は Tauri の bundle target（`dmg`, `app`, `nsis`, `appimage`, `deb`）と、`host/dist`, `host/server`, `host/package.json`, `node`, `control`, `harness`, `engine-bundle` の resource mapping を定義します。staging は `apps/desktop/scripts/stage-control.py`（Control bundle）と `apps/desktop/scripts/stage-harness.mjs`（DeepSeek Harness）、`apps/desktop/scripts/fetch-node.sh` / `.ps1`（ピン留め Node runtime、既定 24.12.0、`STRATA_NODE_VERSION` で変更可）。実際の Release 名は公開 asset で別途確認します。
- `docs/DOCKER.md`, `docker/`, `.github/workflows/docker-images.yml` は Release とは別の配布経路です。`docker/fetch-engines.py` は Release の engine package を signed feed で検証してからイメージに取り込みます。リポジトリ直下の `Dockerfile` はエンジンをその場でコンパイルする手元ビルド用（`docker build -t strata:src .`）で、`docker/build.sh` が使うのは `docker/Dockerfile`（既製の engine package を展開する方）です。ghcr に上がる flavor は後者です。
- 開発用のスクリプトは多数あります: `sycl/tools/*.sh`, `sycl/serve/strata-sycl.sh`, `metal/setup_mac.py`, `metal/tools/gen_grids.sh`, `tools/**`（`tools/dsv41*`, `tools/hip`, `tools/par`, `tools/trellis`, `tools/dflash2/check_metal_dump.py`, `tools/windows/enable_large_pages.ps1` など）, `apps/host/scripts/*.mjs`, `apps/desktop/scripts/*.mjs`, `packaging/smoke_terminal.py`, `packaging/acceptance_matrix.py`, `packaging/monitor_bundle.py`（portable monitor の zipapp `strata-monitor.pyz`。Release asset には含まれない）。`chat.py` は checkout ルートの簡易ターミナルチャット（サーバ起動後用）、`highlight.py` はその色付けライブラリで、製品 CLI ではありません。全ファイルを利用者向け CLI と数えず、呼び出し元と文書で役割を判断します。

## 調査で確認した主なソース

調査対象: Strata commit `146df3c468739147f520ac3816de806f71232571`、tag `v0.2.12`（2026-11-07）。作業開始時点の checkout は clean で、`git pull --ff-only` 後も最新でした。

- CLI / setup: `strata_cli/cli.py`, `strata_cli/drafting_cmd.py`, `strata_cli/split_cmd.py`, `setup.py`, `metal/setup_mac.py`, `tools/strata_bench.py`, `strata.py`, `bin/strata*`
- Engine / package / install: `CMakeLists.txt`（`add_executable` 295 件）, `sycl/CMakeLists.txt`, `metal/CMakeLists.txt`, `src/split/CMakeLists.txt`, `tools/vision/CMakeLists.txt`, `packaging/package_engine.py`, `packaging/package_terminal.py`, `packaging/feed_tool.py`, `packaging/install.sh`, `packaging/install.ps1`, `strata_control/feed.py`, `strata_control/paths.py`, `strata_control/split_engine.py`
- Desktop: `apps/desktop/package.json`, `apps/host/package.json`, `apps/desktop/src-tauri/Cargo.toml`（いずれも 0.2.12）, `apps/desktop/src-tauri/tauri.conf.json`, `apps/desktop/src-tauri/nsis/installer.nsi`, `apps/desktop/src-tauri/src/main.rs`
- Release 実物: GitHub Releases API `/repos/Niko1221/Strata/releases/latest`（v0.2.12、42 assets、サイズ・digest）、`install-manifest.txt`, `latest.json`, `SHA256SUMS.txt`, 両 feed JSON。macOS Control / Engine / DeepSeek archive を展開し、API digest と SHA-256 が一致することを確認しました。Windows / Linux 大容量 archive と `Strata.app.tar.gz` は未展開です。

## 更新手順と次回の調査指示

> この更新をどの順序で回すか（他の索引との関係、消えた項目の削除、未作成文書の一括作成、突合点検）はスキル `.agents/skills/strata-investigate/SKILL.md` にまとめた。以下は本書単体の手順として残す。

Strata checkout が更新されたら、`/home/sasasin/src/github.com/Niko1221/Strata` を調べ、この一覧をソースと公開 Release の双方に合わせて更新します。前回の説明に追記するだけでなく、削除・改名・統合された入口、GUI installer、Terminal installer、engine package、component/feed 方式、Docker 配布の変更も確認してください。

### 調査手順

1. **対象リビジョンと作業状態を記録する。** Strata リポジトリで `git rev-parse HEAD`、`git status --short`、`git log -1 --format='%h %cs %s'`、`git describe --tags` を確認します。tag と HEAD が同じコミットなら、Release とソースが一致している強い根拠になります。作業ツリーに未コミット変更があれば、それも調査対象に含め、既存変更を上書きしないでください。
2. **前回の調査時点からの差分を見る。** 前回文書に書いた commit に対して `git diff --name-status <prev>..HEAD -- packaging/ bin/ docker/ spark/ apps/desktop/ docs/ .` を使い、入口・配布スクリプト・手順書の追加改名削除だけを拾います（テストやベンチ結果の大量変更で薄まらないようにパスを絞る）。
3. **管理されている CLI 入口を列挙する。** `git ls-files | grep -E '\.(sh|bash|bat|cmd|ps1|py|js|mjs|c|cc|cpp)$'` で Strata ルート、`bin/`、`packaging/`、`apps/`、`docker/`、`spark/`、`tools/`、`sycl/`、`metal/` を確認し、README、`docs/INSTALL.md`、`docs/TERMINAL*.md`、`docs/DOCKER.md`、各サブディレクトリの README で利用者向けと開発用を見分けます。名前だけで分類せず、呼び出し先・ヘルプ・説明コメントを読みます。
4. **ビルド生成物とエントリーポイントを調べる。** `CMakeLists.txt` と `sycl/`, `metal/`, `src/split/`, `tools/vision/` の `CMakeLists.txt` で `add_executable`、ターゲット名、`option(...)` と条件ブロックを確認します。Python/Node/Tauri 側は起動ファイル、`package.json` の scripts、`tauri.conf.json` の bundle target と resources、`packaging/package_terminal.py` / `package_engine.py` / `feed_tool.py` の archive 名生成を読みます。`strata` という同名でも、Python の Terminal CLI wrapper とネイティブ推論エンジン、Docker 内の wrapper を区別し、実際に配布されるファイル名（Windows の `.exe` を含む）を特定します。
5. **設置場所を根拠からたどる。** installer の展開先・symlink/junction・PATH 更新（`packaging/install.sh`, `packaging/install.ps1`, `apps/desktop/src-tauri/nsis/installer.nsi`, `apps/desktop/src-tauri/src/main.rs`）、component store の解決（`strata_control/engine_component.py`, `strata_control/paths.py`, `strata_control/updater.py`, `strata_control/dsv41_engine.py`）、Docker image 内の配置（`docker/Dockerfile`）を読みます。既定値とユーザーが変更できる場所（`STRATA_DATA_DIR`, `STRATA_BIN_DIR`, `STRATA_COMPONENTS_DIR`, `STRATA_FEED`, `STRATA_NO_PATH` など）を分けて記載します。ビルド出力先、checkout 内の実行場所、インストール後の場所を混同しないでください。
6. **Release 配布物を照合する。** GitHub Releases API（`/repos/Niko1221/Strata/releases/latest` と `/releases?per_page=…`）で tag、公開日、asset 名・サイズ・`digest` を取得します。`install-manifest.txt`, `latest.json`, `SHA256SUMS.txt`, `strata-feed.json`, `strata-feed-linux-aarch64.json`, `install.sh`, `install.ps1` は本文を取れます。小さい asset（macOS の engine package、`strata-dsv41-*-metal.tar.gz`、macOS の Control archive、`Strata.app.tar.gz`）は展開して中身とハッシュを確認すると、archive 内の実行ファイル名や `engine-bundle/` の folder 名まで実証できます。Windows/Linux の大きな archive は未取得のままなので、その旨を明記します。`*.ps1` は `.gitattributes` で CRLF 化されるため、asset の SHA-256 は git オブジェクト（LF）と比べます。Docker は `https://ghcr.io/v2/niko1221/strata/tags/list`（anonymous token 付き）で tag 実体を確認できます。ネットワークで最新 Release を確認できなかった場合は、そのことを明記し、ソースの仕様だけで現行 Release の実ファイル名を断定しないでください。
7. **一覧を見直して更新する。** 役割、Git 上の所在、生成・配布経路、配布時のファイル名、clone/build/install 後の場所を、埋められる項目だけ記載します。利用者向け入口、実験・開発用ツール、単なるビルド手順、Release だけで配布する archive 内の実行ファイルを区別します。前回の版から変わった点（platform 追加、`.sig` の追加、版数のずれ）も書きます。CLI 引数の網羅は別作業とし、このファイルは入口と配置の一覧に保ちます。
8. **根拠と更新結果を残す。** 文書末尾の「調査で確認した主なソース」を実際に参照したファイルに合わせて更新し、調査対象 Strata の commit hash、tag、調査日を追記します。Markdown の表が読みやすいこと、パス・コマンド名・拡張子がソース記述と一致することを読み返して確認します。

### 次回の依頼文

次回以降は、次のように依頼してください（`000_cli_tools.md` のこの節を指します）。

> Strata ソースコードが更新されたので、`/home/sasasin/src/github.com/sasasin/strata-envvars/docs/cli/000_cli_tools.md` の「更新手順と次回の調査指示」に従って、`/home/sasasin/src/github.com/Niko1221/Strata` を調査し、`000_cli_tools.md` を最新の内容に更新してください。CLI 入口、ビルド生成物、GitHub Release の配布物、ファイル名、インストール先を根拠となるソースから確認し、現行 Release の実体を確認できない項目は推測で埋めず、その制約を記載してください。
