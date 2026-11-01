# Strata の CLI・実行ファイル・配布物

この文書は、Strata の利用者向け入口、ビルド生成物、GitHub Release の配布物と設置先を整理します。CLI 引数や全ての開発用スクリプトの網羅は対象外です。

> **`strata` の名前に注意:** Python の Strata Terminal は `strata` コマンド（wrapper は `bin/strata` / `bin/strata.cmd` / `bin/strata.ps1`）から `strata.py` を実行します。推論エンジンも CMake ターゲット `strata` で、Linux/macOS では `strata`、Windows では `strata.exe` です。Docker イメージ内にも `/usr/local/bin/strata` が入りますが、これは同梱 Terminal への wrapper（`docker/strata-wrapper.sh`）です。デスクトップアプリは Tauri の GUI で、別の配布物です。

## 利用者向け入口と設置先

| 役割 | ソース上の入口 | 生成・配布経路 | 配布時の名前 | 主な設置・実行場所 |
| --- | --- | --- | --- | --- |
| ソース checkout のセットアップ | `setup.sh` → `setup.py`; Windows は `START-HERE.bat` → `setup.py`。`SETUP.bat` は同 bat を `--setup` 付きで呼ぶ | checkout 同梱。開発・ソース利用向けで、Release 用 GUI installer ではない | `setup.sh`, `START-HERE.bat`, `SETUP.bat` | clone したリポジトリ。通常 `.venv/` または `.venv\Scripts\` を使う |
| checkout 更新・ベンチ補助 | `update.sh`, `UPDATE.bat`, `bench.sh`, `BENCH.bat` | checkout 同梱 | 同名スクリプト | clone したリポジトリ内から実行 |
| Strata Terminal CLI | `strata.py`, `strata_cli/`, `strata_control/`, `serve/`; wrapper は `bin/strata`, `bin/strata.cmd`, `bin/strata.ps1` | ソース checkout では既存 Python 環境を利用。Release installer（`install.sh` / `install.ps1`）は `install-manifest.txt` の行を見て Control archive を選び、SHA-256 を検証して展開し、展開後に署名付き feed を検証する | コマンド `strata`; POSIX wrapper `bin/strata`, Windows wrapper `strata.cmd` / `strata.ps1`; Release archive は `strata-control-<version>-<platform>.tar.gz`（Windows は `.zip`） | POSIX は既定で `~/.local/share/strata/terminal/<version>/`（`STRATA_DATA_DIR` / `$XDG_DATA_HOME` で変更可）に展開し、`terminal/current` symlink と `~/.local/bin/strata`（既定、`STRATA_BIN_DIR` で変更可）を張る。Windows は `%LOCALAPPDATA%\Strata\terminal\<version>\` に展開し、`terminal\current` を `mklink /J` で作って `%LOCALAPPDATA%\Strata\terminal\current\bin` をユーザー PATH に追加（`STRATA_NO_PATH=1` で抑止）。checkout では repo と `.venv` |
| Strata デスクトップアプリ | Tauri shell `apps/desktop/src-tauri/`; Node App Host/UI は `apps/host/` | Tauri bundle と Release workflow。Windows/Linux installer は engine を含まず、初回起動時に engine component を取得。macOS は小型 Metal engine を `engine-bundle/` に同梱（app 更新 archive にも同梱されていた） | 現行 v0.2.9: `Strata-0.2.9-windows-x64-setup.exe`, `Strata-0.2.9-linux-x86_64.AppImage`, `Strata-0.2.9-macos-arm64.dmg`, 更新用 `Strata.app.tar.gz` | Windows installer は current-user install で既定 `%LOCALAPPDATA%\Programs\Strata`（`nsis/installer.nsi`）。Windows では `host/`, `control/`, `node/`, `harness/`, `engine-bundle/` が exe と同じフォルダに置かれる。macOS は `Strata.app/Contents/Resources/` 直下。Linux deb/AppImage では `<prefix>/lib/Strata`（`src/main.rs` の `packaged_resource_dir`）。ユーザーデータと engine component は別のユーザー領域 |
| 推論エンジン component | CMake target `strata`、入口 `src/program/generate.cpp`（SYCL は `sycl/`、Metal は `metal/`） | `setup.py` のソースビルド、`packaging/build_*.sh` / `.bat` と `package_engine.py` による package。Release feed に署名付き engine archive | `strata-engine-<version>-<platform>-<backend>[-<variant>].tar.gz`。別の package の DeepSeek engine は `strata-dsv41-<version>-<platform>-<backend>[-<variant>].tar.gz` | ソース build directory。アプリ/Terminal 利用時は component store の `engine/<version>-<platform>-<backend>[-<variant>]/`。Windows `%LOCALAPPDATA%\Strata\components`、POSIX `$XDG_DATA_HOME/strata/components`（既定 `~/.local/share/strata/components`）。`STRATA_COMPONENTS_DIR` で上書き可。DeepSeek engine は同じ store の `engine-dsv41/` に別領域 |
| Docker イメージ | 既製の engine package を使う `docker/Dockerfile` と、エンジンを作る `Dockerfile`（リポジトリ直下、`docker build -t strata:src .`）。`docker/build.sh`, `docker/publish.sh`, `docker/fetch-engines.py`, `docker/entrypoint.sh`, `docker/strata-wrapper.sh`, `docker/healthcheck.sh`, `docker/smoke-test.sh`, `docker/compose/*.yml` | GitHub Actions `.github/workflows/docker-images.yml` が `docker/publish.sh` を flavor ごとに呼び、ghcr に push。イメージは Release の engine package を signed feed 経由で検証して取り込む | `ghcr.io/niko1221/strata:<version>-<flavor>` と `:latest-<flavor>`。flavor は `cuda13`, `cuda12`, `rocm-gfx120x`, `rocm-gfx110x`, `rocm-gfx1151`, `sycl` | `docker run` で起動。イメージ内は Terminal が `/opt/strata/terminal`、engine が `/opt/strata/components/engine/`（`STRATA_COMPONENTS_DIR=/opt/strata/components`）、`strata` が `/usr/local/bin/strata`。データは volume `/data`、ポート 8080。`docker exec <name> strata ...` で Terminal が使える |
| CMake 診断・開発プログラム | 各 `CMakeLists.txt` の `add_executable`（root だけで 250 件） | backend・オプション・テスト設定により build directory に生成。通常の GUI/Terminal 製品コマンドではない | 例: `strata-plan`, `strata-gguf`, `strata-dequant`, 条件付き `strata-device`, `strata-load`, `strata-concurrent`, `strata-overlap`, `strata-q36`, `strata-q36ref`, `strata-dsv41`, `strata_ds4` (Metal), `strata-vision` / `strata-vision-hip` / `strata-vision-sycl` | build directory。Release の archive に入るのは engine package が採るファイルだけ（下記） |

Terminal の `strata` wrapper は同梱 Python runtime（`python/`）を優先し、checkout では `.venv` または PATH の Python 3.10 以上を使います。wrapper 自体は pip install も download も行いません。Release の `install.sh` / `install.ps1` は常駐 CLI ではなく、manifest を読んで Control archive を導入する installer です。モデルと engine は別途管理され、Terminal の `strata launch` は選択した GPU に合う engine を feed から取得します。

Control 自身の更新は component store に入り、`components/control/active.json` が切り替わります（`packaging/UPDATES.md`, `strata_control/updater.py`）。Linux ARM64（NVIDIA DGX Spark）の Terminal は `strata-feed-linux-aarch64.json` を読み、他のマシンは `strata-feed.json` を読みます（`strata_control/feed.py` の `FEED_NAME` / `AARCH64_FEED_NAME`）。

## 現行 GitHub Release の実物（v0.2.9）

2026-11-01 に GitHub Releases API と asset の実取得で確認しました。[`releases/latest`](https://github.com/Niko1221/Strata/releases/latest) は **v0.2.9**（公開 2026-10-31T08:02:32Z、asset 40 件）。checkout の HEAD は v0.2.9 タグのコミットそのものです（`git log v0.2.9..HEAD` は 0 件）。アプリ版は 0.2.9、Control と全 engine package は 0.1.55 です。

asset 40 件の内訳（名前は API の一覧から）:

- GUI installer: `Strata-0.2.9-windows-x64-setup.exe`, `Strata-0.2.9-linux-x86_64.AppImage`, `Strata-0.2.9-macos-arm64.dmg`
- Tauri updater 関連: `Strata-0.2.9-windows-x64-setup.exe.sig`, `Strata-0.2.9-linux-x86_64.AppImage.sig`, `Strata.app.tar.gz`, `Strata.app.tar.gz.sig`（`.sig` が付いているのは v0.2.8 以降。v0.2.5〜v0.2.7 の asset に `.sig` は無い）
- Terminal / Control 0.1.55（4 platform。`linux-aarch64` が加わった）: `strata-control-0.1.55-linux-x86_64.tar.gz`, `strata-control-0.1.55-linux-aarch64.tar.gz`, `strata-control-0.1.55-macos-arm64.tar.gz`, `strata-control-0.1.55-windows-x86_64.zip`
- Engine 0.1.55（14 archive）: `strata-engine-0.1.55-linux-x86_64-{cuda-cuda12,cuda-cuda13,hip-halo,hip-rx6000,hip-rx7900,hip-rx9070,sycl}.tar.gz`, `strata-engine-0.1.55-linux-aarch64-cuda-cuda13.tar.gz`, `strata-engine-0.1.55-macos-arm64-metal.tar.gz`, `strata-engine-0.1.55-windows-x86_64-{cuda-cuda12,cuda-cuda13,hip-rdna2,hip-rdna3,hip-rx9070}.tar.gz`
- DeepSeek engine 0.1.55（6 archive）: `strata-dsv41-0.1.55-linux-x86_64-{cuda-cuda13,hip-rx9070}.tar.gz`, `strata-dsv41-0.1.55-linux-aarch64-cuda-cuda13.tar.gz`, `strata-dsv41-0.1.55-macos-arm64-metal.tar.gz`, `strata-dsv41-0.1.55-windows-x86_64-{cuda-cuda13,hip-rdna3}.tar.gz`
- Feed / installer: `strata-feed.json` + `.sig`, `strata-feed-linux-aarch64.json` + `.sig`, `latest.json`, `install-manifest.txt`, `install.sh`, `install.ps1`, `SHA256SUMS.txt`

`install-manifest.txt` は取得できたので転記します（`platform version url sha256 size` の 4 行。SHA-256 は省略表記です）:

```text
linux-x86_64   0.1.55 strata-control-0.1.55-linux-x86_64.tar.gz   50783d2f…9488e8   99498096
macos-arm64    0.1.55 strata-control-0.1.55-macos-arm64.tar.gz    5c3f8ead…6f226     50763163
windows-x86_64 0.1.55 strata-control-0.1.55-windows-x86_64.zip    bdca3a42…594e99   73121142
linux-aarch64  0.1.55 strata-control-0.1.55-linux-aarch64.tar.gz  0f298b91…1203789   83372878
```

`strata-feed.json` の `control.packages` に載るのは 3 platform（linux-x86_64 / macos-arm64 / windows-x86_64）だけで、`linux-aarch64` は `strata-feed-linux-aarch64.json` 側にしかありません。`latest.json` と `strata-feed.json` の `app` は 3 platform（`windows-x86_64`, `linux-x86_64`, `darwin-aarch64`）で、`strata-feed-linux-aarch64.json` には `app` がありません（ARM64 Linux のデスクトップアプリは配布されていない）。共通 feed は schema_version 1、channel `stable`、sequence 118、`expires_at: null`、`feed: strata-updates`。

Release の installer スクリプトとソースの対応はハッシュで確認しました。`install.sh` の asset digest は `packaging/install.sh` と一致（`65c38f82…1f43`）。`install.ps1` の asset digest（`322ad52b…343fc`）は git オブジェクト上の `packaging/install.ps1`（LF）と一致しますが、working tree のファイルは `.gitattributes` の `*.ps1 text eol=crlf` で CRLF 化されるため、作業ツリーのファイルの SHA-256（`6e0c8b2f…`）とは一致しません。行末を変換すると一致します。

### archive を実際に展開して確認できた中身

`SHA256SUMS.txt` と突き合わせ、次の asset はダウンロードして展開しました（いずれもハッシュ一致）。

- `strata-engine-0.1.55-macos-arm64-metal.tar.gz`（38 entries）: トップレベルに `strata`, `strata-vision`, `engine-component.json`, `BUILD.json`, `metal/**`（`.metal` ソースは起動時にコンパイルする）。manifest は `id`/`name` = `strata-engine`、`platform` = `macos-arm64`、`backend` = `metal`、`entrypoint` = `strata`、`archs` = `["apple-gpu"]`、Ed25519 署名あり（key_id `5d1bc23abbeffd0d`）。
- `strata-dsv41-0.1.55-macos-arm64-metal.tar.gz`（33 entries）: manifest の `entrypoint` は `strata-dsv41`（`id`/`name` は `strata-engine` のまま）。
- `strata-engine-0.1.55-linux-x86_64-hip-halo.tar.gz`（280 entries）: `strata`, `strata-vision`, `strata-vision-hip`、ROCm ライブラリ、`hipblaslt/library/**`、`SYSTEM-LIBS.txt`。`BUILD.json` は `vision: "gpu"`, `dsv41: false`, `archs: ["gfx1151"]`。
- `strata-engine-0.1.55-linux-x86_64-sycl.tar.gz`（26 entries）: 実行ファイルは `strata` だけで、picture reader は同梱されていません。
- `strata-control-0.1.55-macos-arm64.tar.gz`（4631 entries）: トップレベルに `strata.py`, `strata_cli/`, `strata_control/`, `serve/`, `bin/strata`, `python/bin/python3.12`, `setup.py`, `tools/`, `data/`, `bench/`, `docs/`, `ref/`, `VERSION`（0.1.55）, `COMMIT`（4cf0d8cd3809b5a3f220ea4e1abf024ac7365de9）, `README.txt`。`install.sh` は `bin/strata` を持つこの形を前提に展開し、無ければ何もインストールしません。
- `Strata.app.tar.gz`（macOS の app 更新 archive、32494 entries）: `Strata.app/Contents/Resources/` 直下に `control/`, `host/`, `node/node`, `harness/`, `engine-bundle/0.1.55-macos-arm64-metal/`（`strata`, `strata-vision`, `engine-component.json`, `BUILD.json`, `metal/**`）。

### 実体を確認できていない項目（推測しない）

- Windows / Linux の GUI installer、AppImage、DMG は展開していません。`Strata-0.2.9-windows-x64-setup.exe` 内の `control/`, `host/`, `node/`, `harness/` の配置は、`tauri.conf.json` の resources mapping と `nsis/installer.nsi` の記述からの説明になります。
- Windows 用 Control archive（`.zip`）は未展開です。`bin/strata.cmd` / `bin/strata.ps1` が同梱されることは `packaging/README.md` と `packaging/package_terminal.py` の記述から分かりますが、Release asset としての実体は未確認です。
- Windows と Linux の engine archive も未展開です。`strata.exe`, `strata-vision.exe` といった名前は `packaging/package_engine.py`（既定 entrypoint は `strata.exe` / `strata`、`strata-vision[.exe]` と `strata-vision-hip[.exe]` を採る）とビルドスクリプトからの記載で、Release 実体では確認していません。
- `packaging/package_terminal.py` が作る `strata-terminal-<version>-<target>.tar.gz|zip` は、v0.2.9 の公開 asset に存在しません（公開は `strata-control-…` のみ）。同じ bundle を指す別名です（`apps/desktop/scripts/stage-control.py` と `packaging/README.md` の説明による）。
- `apps/desktop/src-tauri/tauri.conf.json` は bundle target に `deb` を持ちますが、Release に `.deb` asset はありません。
- Docker イメージは ghcr.io の tag 一覧を実際に取得して確認しました（`0.2.9-cuda12`, `0.2.9-cuda13`, `0.2.9-rocm-gfx110x`, `0.2.9-rocm-gfx1151`, `0.2.9-rocm-gfx120x`, `0.2.9-sycl` と `latest-*`、計 40 tag）。`0.2.4`〜`0.2.6` のタグはありません。イメージ内の実ファイルは未展開です。
- Windows 向け code signing 証明書は設定されていないため、`.exe` に Authenticode は付きません（`packaging/README.md`）。asset の `.sig` は Tauri updater の minisign 署名で、Authenticode とは別物です。
- ソースの `packaging/README.md` と `docs/INSTALL.md` の一部には「現在の Release は 0.2.5 / Control・engine 0.1.50」という古い前置きが残っています。表や手順本文は 0.2.9 の名前になっているので、Release の実体は上記の asset 一覧に従います。

## 直前の調査（v0.2.5）からの変化

前回この文書が対象にした v0.2.5（2026-10-25、asset 30 件）から、配布物の形は次のように変わりました。

- Control / engine の版は 0.1.50 → 0.1.55、アプリは 0.2.5 → 0.2.9（v0.2.6, v0.2.7, v0.2.8 を経た）。
- `linux-aarch64`（NVIDIA DGX Spark）が加わった: Terminal archive、engine、DeepSeek engine、`install-manifest.txt` の行、`strata-feed-linux-aarch64.json`（と `.sig`）。デスクトップアプリの ARM64 Linux ビルドは無い。`packaging/build_cuda_linux_aarch64.sh`, `spark/build_engine.sh`, `packaging/locks/runtime-linux-aarch64-cp312.txt`, `docs/DGX_SPARK_LINUX.md` が対応ソース。
- Tauri updater の `.sig` と `Strata.app.tar.gz.sig` が asset に加わった。
- `install.sh` が `Linux-aarch64` を `linux-aarch64` として扱うようになり、DGX Spark 以外の ARM マシンでは「Terminal は入るが engine が見つからないかもしれない」と注記する。それ以外の OS/arch では「この PC 用の Terminal は無い」と明示して終了。`install.ps1` は `windows-x86_64` のまま。
- v0.2.7 では Control / engine の版が 0.1.52 と 0.1.53 で混在していた（`linux-aarch64` 系のみ 0.1.53）。v0.2.8 以降は単一版。
- `packaging/feed_tool.py` は Control package の form が installer の期待（Windows は zip、他は tar.gz）と違う場合、`install-manifest.txt` から除外して note を出す。

## ビルド生成物と配布対象の区別

- root `CMakeLists.txt` は CUDA / HIP を有効にした時にエンジン `strata` を `src/program/generate.cpp` から作ります。`strata-plan`, `strata-gguf`, `strata-dequant` は backend 非依存で定義され、`strata-device`, `strata-load`, `strata-concurrent`, `strata-overlap` は CUDA / HIP が ON のブロック内、`strata-q36ref` / `strata-q36` は Qwen3.5/3.6 のブロック（`NOT STRATA_HIP_GFX906`）、`strata-dsv41` は `option(STRATA_BUILD_DSV41 …)` が ON かつ gfx906 以外の時に定義されます。root には 250 件の `add_executable` があり、`*_parity`, `*_bench`, `*_test` は診断・検証用です。ターゲット定義だけで Release 配布を意味しません。
- backend 別のエンジン入口は別ファイルです: `sycl/CMakeLists.txt` の `add_executable(strata …)`、`metal/CMakeLists.txt` の `add_executable(strata …)` と `add_executable(strata_ds4 …)`（`packaging/mac/build_dsv41_engine.sh` が `strata_ds4` を `strata-dsv41` として staging する）。
- 画像読み取りは `tools/vision/CMakeLists.txt` の `strata-vision` で、`STRATA_VISION_HIP` / `STRATA_VISION_SYCL` を付けるとそれぞれ `strata-vision-hip` / `strata-vision-sycl` という別プログラムになります。`package_engine.py` は `strata-vision[.exe]` と `strata-vision-hip[.exe]` を package に取り込みますが、SYCL package には picture reader が入っていません（実測）。`--no-picture-reader` で意図的に外す経路もあります。
- `packaging/README.md` の target matrix と `packaging/build_*.sh` / `.bat` が backend ごとの engine package 作成手順です。`package_engine.py` が build folder を component package にし、`feed_tool.py` が feed entry と archive 名（`pack-engine --prefix strata-engine` または `strata-dsv41`、`pack-control` で `strata-control-<version>-<platform>`）を作ります。engine package の形は `packaging/ENGINE-COMPONENT.md`（schema 2 の manifest、`<components>/engine/<version>-<platform>-<backend>[-<variant>]/`、`files` の全 SHA-256、署名方針）。
- `apps/desktop/src-tauri/tauri.conf.json` は Tauri の bundle target（`dmg`, `app`, `nsis`, `appimage`, `deb`）と、`host/dist`, `host/server`, `host/package.json`, `node`, `control`, `harness`, `engine-bundle` の resource mapping を定義します。staging は `apps/desktop/scripts/stage-control.py`（Control bundle）と `apps/desktop/scripts/stage-harness.mjs`（DeepSeek Harness）、`apps/desktop/scripts/fetch-node.sh` / `.ps1`（ピン留め Node runtime）。実際の Release 名は公開 asset で別途確認します。
- `docs/DOCKER.md`, `docker/`, `.github/workflows/docker-images.yml` は Release とは別の配布経路です。`docker/fetch-engines.py` は Release の engine package を signed feed で検証してからイメージに取り込みます。リポジトリ直下の `Dockerfile` はエンジンをその場でコンパイルする手元ビルド用（`docker build -t strata:src .`）で、`docker/build.sh` が使うのは `docker/Dockerfile`（既製の engine package を展開する方）です。ghcr に上がる flavor は後者です。
- 開発用のスクリプトは多数あります: `sycl/tools/*.sh`, `sycl/serve/strata-sycl.sh`, `metal/setup_mac.py`, `metal/tools/gen_grids.sh`, `tools/**`（`tools/dsv41*`, `tools/hip`, `tools/par`, `tools/trellis`, `tools/windows/enable_large_pages.ps1` など）, `apps/host/scripts/*.mjs`, `apps/desktop/scripts/*.mjs`, `packaging/smoke_terminal.py`, `packaging/acceptance_matrix.py`, `packaging/monitor_bundle.py`（portable monitor の zipapp `strata-monitor.pyz`。Release asset には含まれない）。`chat.py` は checkout ルートの簡易ターミナルチャット（サーバ起動後用）、`highlight.py` はその色付けライブラリで、製品 CLI ではありません。全ファイルを利用者向け CLI と数えず、呼び出し元と文書で役割を判断します。

## 調査で確認した主なソース

- checkout 情報: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-10-31T03:23:01+01:00）、working tree clean、`git describe --tags` は `v0.2.9`（tag と HEAD は同一コミット）。確認日: 2026-11-01。
- CLI / checkout setup: `strata.py`, `strata_cli/cli.py`, `bin/strata`, `bin/strata.cmd`, `bin/strata.ps1`, `setup.sh`, `SETUP.bat`, `START-HERE.bat`, `update.sh`, `UPDATE.bat`, `bench.sh`, `BENCH.bat`, `setup.py`, `chat.py`, `highlight.py`
- CMake / engine: `CMakeLists.txt`（`add_executable` の位置と条件）, `sycl/CMakeLists.txt`, `metal/CMakeLists.txt`, `tools/vision/CMakeLists.txt`, `src/program/generate.cpp`, `packaging/build_cuda_linux.sh`, `packaging/build_cuda_linux_aarch64.sh`, `packaging/build_hip_linux.sh`, `packaging/build_sycl_linux.sh`, `packaging/build_vision_mac.sh`, `packaging/build_vision_windows.bat`, `packaging/build_dsv41_cuda.sh`, `packaging/build_dsv41_windows.bat`, `packaging/mac/build_dsv41_engine.sh`, `packaging/package_engine.py`, `packaging/ENGINE-COMPONENT.md`, `spark/build_engine.sh`, `strata_control/engine_component.py`, `strata_control/dsv41_engine.py`
- Terminal / feed / install: `packaging/install.sh`, `packaging/install.ps1`, `packaging/package_terminal.py`, `packaging/feed_tool.py`, `packaging/make_local_feed.py`, `packaging/locks/runtime-linux-aarch64-cp312.txt`, `packaging/README.md`, `packaging/UPDATES.md`, `strata_control/feed.py`, `strata_control/paths.py`, `strata_control/components.py`, `strata_control/updater.py`, `strata_control/discovery.py`, `docs/INSTALL.md`, `docs/TERMINAL.md`, `docs/TERMINAL_LAUNCH.md`, `docs/TERMINAL_QUICKSTART.md`, `docs/DGX_SPARK_LINUX.md`, `.gitattributes`（`*.ps1 text eol=crlf`）
- Desktop: `apps/desktop/package.json`, `apps/host/package.json`（いずれも 0.2.9）, `apps/desktop/src-tauri/Cargo.toml`, `apps/desktop/src-tauri/tauri.conf.json`, `apps/desktop/src-tauri/nsis/installer.nsi`, `apps/desktop/src-tauri/src/main.rs`（`packaged_resource_dir`）, `apps/desktop/scripts/stage-control.py`, `apps/desktop/scripts/stage-harness.mjs`, `apps/desktop/scripts/fetch-node.sh`
- Docker: `docker/Dockerfile`, `docker/build.sh`, `docker/publish.sh`, `docker/fetch-engines.py`, `docker/entrypoint.sh`, `docker/strata-wrapper.sh`, `docker/healthcheck.sh`, `docker/compose/*.yml`, `docs/DOCKER.md`, `.github/workflows/docker-images.yml`, ghcr.io の `niko1221/strata` tag 一覧（2026-11-01 に取得）
- Release 実物: [`releases/latest`](https://github.com/Niko1221/Strata/releases/latest) と GitHub Releases API（`/releases/latest`, `/releases?per_page=15`）で v0.2.9 の asset 40 件・サイズ・digest を確認。`install-manifest.txt`, `latest.json`, `SHA256SUMS.txt`, `strata-feed.json`, `strata-feed-linux-aarch64.json`, `install.sh`, `install.ps1` の本文、および `strata-engine-0.1.55-macos-arm64-metal.tar.gz`, `strata-dsv41-0.1.55-macos-arm64-metal.tar.gz`, `strata-engine-0.1.55-linux-x86_64-hip-halo.tar.gz`, `strata-engine-0.1.55-linux-x86_64-sycl.tar.gz`, `strata-control-0.1.55-macos-arm64.tar.gz`, `Strata.app.tar.gz` を展開して中身とハッシュを確認。

## 更新手順と次回の調査指示

> この更新をどの順序で回すか（他の索引との関係、消えた項目の削除、未作成文書の一括作成、突合点検）はスキル `.agents/skills/strata-investigate/SKILL.md` にまとめた。以下は本書単体の手順として残す。

Strata checkout が更新されたら、`/home/sasasin/src/github.com/Niko1221/Strata` を調べ、この一覧をソースと公開 Release の双方に合わせて更新します。前回の説明に追記するだけでなく、削除・改名・統合された入口、GUI installer、Terminal installer、engine package、component/feed 方式、Docker 配布の変更も確認してください。

### 調査手順

1. **対象リビジョンと作業状態を記録する。** Strata リポジトリで `git rev-parse HEAD`、`git status --short`、`git log -1 --format='%h %cs %s'`、`git describe --tags` を確認します。tag と HEAD が同じコミットなら、Release とソースが一致している強い根拠になります。作業ツリーに未コミット変更があれば、それも調査対象に含め、既存変更を上書きしないでください。
2. **前回の調査時点からの差分を見る。** 前回文書に書いた commit に対して `git diff --name-status <prev>..HEAD -- packaging/ bin/ docker/ spark/ apps/desktop/ docs/ .` を使い、入口・配布スクリプト・手順書の追加改名削除だけを拾います（テストやベンチ結果の大量変更で薄まらないようにパスを絞る）。
3. **管理されている CLI 入口を列挙する。** `git ls-files | grep -E '\.(sh|bash|bat|cmd|ps1|py|js|mjs|c|cc|cpp)$'` で Strata ルート、`bin/`、`packaging/`、`apps/`、`docker/`、`spark/`、`tools/`、`sycl/`、`metal/` を確認し、README、`docs/INSTALL.md`、`docs/TERMINAL*.md`、`docs/DOCKER.md`、各サブディレクトリの README で利用者向けと開発用を見分けます。名前だけで分類せず、呼び出し先・ヘルプ・説明コメントを読みます。
4. **ビルド生成物とエントリーポイントを調べる。** `CMakeLists.txt` と `sycl/`, `metal/`, `tools/vision/` の `CMakeLists.txt` で `add_executable`、ターゲット名、`option(...)` と条件ブロックを確認します。Python/Node/Tauri 側は起動ファイル、`package.json` の scripts、`tauri.conf.json` の bundle target と resources、`packaging/package_terminal.py` / `package_engine.py` / `feed_tool.py` の archive 名生成を読みます。`strata` という同名でも、Python の Terminal CLI wrapper とネイティブ推論エンジン、Docker 内の wrapper を区別し、実際に配布されるファイル名（Windows の `.exe` を含む）を特定します。
5. **設置場所を根拠からたどる。** installer の展開先・symlink/junction・PATH 更新（`packaging/install.sh`, `packaging/install.ps1`, `apps/desktop/src-tauri/nsis/installer.nsi`, `apps/desktop/src-tauri/src/main.rs`）、component store の解決（`strata_control/engine_component.py`, `strata_control/paths.py`, `strata_control/updater.py`, `strata_control/dsv41_engine.py`）、Docker image 内の配置（`docker/Dockerfile`）を読みます。既定値とユーザーが変更できる場所（`STRATA_DATA_DIR`, `STRATA_BIN_DIR`, `STRATA_COMPONENTS_DIR`, `STRATA_FEED`, `STRATA_NO_PATH` など）を分けて記載します。ビルド出力先、checkout 内の実行場所、インストール後の場所を混同しないでください。
6. **Release 配布物を照合する。** GitHub Releases API（`/repos/Niko1221/Strata/releases/latest` と `/releases?per_page=…`）で tag、公開日、asset 名・サイズ・`digest` を取得します。`install-manifest.txt`, `latest.json`, `SHA256SUMS.txt`, `strata-feed.json`, `strata-feed-linux-aarch64.json`, `install.sh`, `install.ps1` は本文を取れます。小さい asset（macOS の engine package、`strata-dsv41-*-metal.tar.gz`、macOS の Control archive、`Strata.app.tar.gz`）は展開して中身とハッシュを確認すると、archive 内の実行ファイル名や `engine-bundle/` の folder 名まで実証できます。Windows/Linux の大きな archive は未取得のままなので、その旨を明記します。`*.ps1` は `.gitattributes` で CRLF 化されるため、asset の SHA-256 は git オブジェクト（LF）と比べます。Docker は `https://ghcr.io/v2/niko1221/strata/tags/list`（anonymous token 付き）で tag 実体を確認できます。ネットワークで最新 Release を確認できなかった場合は、そのことを明記し、ソースの仕様だけで現行 Release の実ファイル名を断定しないでください。
7. **一覧を見直して更新する。** 役割、Git 上の所在、生成・配布経路、配布時のファイル名、clone/build/install 後の場所を、埋められる項目だけ記載します。利用者向け入口、実験・開発用ツール、単なるビルド手順、Release だけで配布する archive 内の実行ファイルを区別します。前回の版から変わった点（platform 追加、`.sig` の追加、版数のずれ）も書きます。CLI 引数の網羅は別作業とし、このファイルは入口と配置の一覧に保ちます。
8. **根拠と更新結果を残す。** 文書末尾の「調査で確認した主なソース」を実際に参照したファイルに合わせて更新し、調査対象 Strata の commit hash、tag、調査日を追記します。Markdown の表が読みやすいこと、パス・コマンド名・拡張子がソース記述と一致することを読み返して確認します。

### 次回の依頼文

次回以降は、次のように依頼してください（`000_cli_tools.md` のこの節を指します）。

> Strata ソースコードが更新されたので、`/home/sasasin/src/github.com/sasasin/strata-envvars/docs/cli/000_cli_tools.md` の「更新手順と次回の調査指示」に従って、`/home/sasasin/src/github.com/Niko1221/Strata` を調査し、`000_cli_tools.md` を最新の内容に更新してください。CLI 入口、ビルド生成物、GitHub Release の配布物、ファイル名、インストール先を根拠となるソースから確認し、現行 Release の実体を確認できない項目は推測で埋めず、その制約を記載してください。
