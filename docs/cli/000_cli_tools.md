# Strata の CLI・実行ファイル・配布物

この文書は、Strata の利用者向け入口、ビルド生成物、GitHub Release の配布物と設置先を整理します。CLI 引数や全ての開発用スクリプトの網羅は対象外です。

> **`strata` の名前に注意:** Python の Strata Terminal は `strata` コマンドから `strata.py` を実行します。推論エンジンも CMake ターゲット `strata` で、Linux/macOS では `strata`、Windows では `strata.exe` です。デスクトップアプリは Tauri の GUI で、別の配布物です。

## 利用者向け入口と設置先

| 役割 | ソース上の入口 | 生成・配布経路 | 配布時の名前 | 主な設置・実行場所 |
| --- | --- | --- | --- | --- |
| ソース checkout のセットアップ | `setup.sh` → `setup.py`; Windows は `START-HERE.bat` → `setup.py`。`SETUP.bat` は同 bat を `--setup` 付きで呼ぶ | checkout 同梱。開発・ソース利用向けで、Release 用 GUI installer ではない | `setup.sh`, `START-HERE.bat`, `SETUP.bat` | clone したリポジトリ。通常 `.venv/` または `.venv\\Scripts\\` を使う |
| checkout 更新・ベンチ補助 | `update.sh`, `UPDATE.bat`, `bench.sh`, `BENCH.bat` | checkout 同梱 | 同名スクリプト | clone したリポジトリ内から実行 |
| Strata Terminal CLI | `strata.py`, `strata_cli/`, `strata_control/`; wrapper は `bin/strata`, `bin/strata.cmd`, `bin/strata.ps1` | ソース checkout では既存 Python 環境を利用。Release installer は署名付き feed の Control archive を選択し、SHA-256 と feed 署名を検証して展開 | コマンド `strata`; Windows wrapper `strata.cmd` / `strata.ps1`; Release archive は `strata-control-<version>-<platform>.tar.gz` または Windows `.zip` | checkout は repo と `.venv`。POSIX installer は通常 `~/.local/share/strata/terminal/<version>/` と `~/.local/bin/strata` symlink。Windows は通常 `%LOCALAPPDATA%\\Strata\\terminal\\<version>\\`、`terminal\\current\\bin` がユーザー PATH |
| Strata デスクトップアプリ | Tauri shell `apps/desktop/src-tauri/`; Node App Host/UI は `apps/host/` | Tauri bundle と Release workflow。Windows/Linux は engine を含めず、初回起動時に engine component を取得。macOS DMG は小型 Metal engine を同梱 | 公開中の v0.2.5: `Strata-0.2.5-windows-x64-setup.exe`, `Strata-0.2.5-linux-x86_64.AppImage`, `Strata-0.2.5-macos-arm64.dmg` | Windows installer は current-user install。既定のプログラム先は `%LOCALAPPDATA%\\Programs\\Strata`。Linux AppImage は取得した場所から起動。macOS DMG 内の `Strata.app` を Applications に配置。ユーザーデータと engine component は別のユーザー領域 |
| 推論エンジン component | CMake target `strata`、入口 `src/program/generate.cpp` | `setup.py` のソースビルド、`packaging/build_*.sh` / `.bat` と `packaging/package_engine.py` による package。Release feed に署名付き engine archive | `strata-engine-<version>-<platform>-<backend>-<variant>.tar.gz`。別 package の DeepSeek engine は `strata-dsv41-...tar.gz` | ソース build directory。アプリ/Terminal 利用時は component store の `engine/`。Windows `%LOCALAPPDATA%\\Strata\\components`、POSIX `$XDG_DATA_HOME/strata/components`（通常 `~/.local/share/strata/components`）。設定は `STRATA_COMPONENTS_DIR` で上書き可 |
| CMake 診断・開発プログラム | `CMakeLists.txt` の `add_executable` | backend、オプション、テスト設定により build directory に生成。通常の GUI/Terminal 製品コマンドではない | 例: `strata-plan`, `strata-device`, `strata-load`, `strata-concurrent`, `strata-overlap`, `strata-gguf`, `strata-dequant`, `strata-q36`, 条件付き `strata-dsv41` | build directory。Release に含まれるかは各 Release asset を個別に確認する |

Terminal の `strata` は wrapper が同梱 Python runtime を優先し、checkout では `.venv` または Python 3.10 以上を使います。wrapper 自体は pip install や download を行いません。Release の `install.sh` / `install.ps1` は常駐 CLI ではなく、manifest を読んで Control archive を導入する installer です。モデルと engine は別途管理され、Terminal の `strata launch` は選択した GPU に合う engine を feed から取得します。

## 現行 GitHub Release の実物

2026-10-26 に GitHub の [`releases/latest`](https://github.com/Niko1221/Strata/releases/latest) と [v0.2.5 の公開 assets 一覧](https://github.com/Niko1221/Strata/releases/expanded_assets/v0.2.5) を確認しました。現行公開 Release は **v0.2.5**、公開日は 2026-10-25、asset は 32 件です。Strata checkout の `apps/desktop/package.json` と `apps/desktop/src-tauri/Cargo.toml` は 0.2.6 ですが、Release の公開実物が 0.2.6 である根拠にはなりません。

確認できた v0.2.5 の主な asset 名:

- GUI installer: `Strata-0.2.5-windows-x64-setup.exe`, `Strata-0.2.5-linux-x86_64.AppImage`, `Strata-0.2.5-macos-arm64.dmg`
- Terminal/Control: `strata-control-0.1.50-linux-x86_64.tar.gz`, `strata-control-0.1.50-macos-arm64.tar.gz`, `strata-control-0.1.50-windows-x86_64.zip`
- DeepSeek engine: `strata-dsv41-0.1.50-linux-x86_64-cuda-cuda13.tar.gz`, `strata-dsv41-0.1.50-linux-x86_64-hip-rx9070.tar.gz`, `strata-dsv41-0.1.50-windows-x86_64-cuda-cuda13.tar.gz`
- Engine: `strata-engine-0.1.50-linux-x86_64-cuda-cuda12.tar.gz`, `strata-engine-0.1.50-linux-x86_64-cuda-cuda13.tar.gz`, `strata-engine-0.1.50-linux-x86_64-hip-halo.tar.gz`, `strata-engine-0.1.50-linux-x86_64-hip-rx6000.tar.gz`, `strata-engine-0.1.50-linux-x86_64-hip-rx7900.tar.gz`, `strata-engine-0.1.50-linux-x86_64-hip-rx9070.tar.gz`, `strata-engine-0.1.50-linux-x86_64-sycl.tar.gz`, `strata-engine-0.1.50-macos-arm64-metal.tar.gz`, `strata-engine-0.1.50-windows-x86_64-cuda-cuda12.tar.gz`, `strata-engine-0.1.50-windows-x86_64-cuda-cuda13.tar.gz`, `strata-engine-0.1.50-windows-x86_64-hip-rdna2.tar.gz`, `strata-engine-0.1.50-windows-x86_64-hip-rdna3.tar.gz`, `strata-engine-0.1.50-windows-x86_64-hip-rx9070.tar.gz`
- Feed / updater: `install-manifest.txt`, `install.sh`, `install.ps1`, `latest.json`, `SHA256SUMS.txt`, `strata-feed.json`, `strata-feed.json.sig`, `Strata.app.tar.gz`

公開 asset 一覧に Terminal installer が読む Control archives が実在することは確認しました。asset 一覧から `install-manifest.txt` 本文を取得できなかったため、manifest 内の各行・SHA-256・サイズはここでは転記せず、Control archive と OS の対応も manifest 内容としては断定しません。ソースの `feed_tool.py` は Control archive から同 manifest を生成する仕様を定めています。`strata-terminal-<version>-<platform>` 形式は `package_terminal.py` の別の build 出力仕様で、今回の v0.2.5 公開 assets にはその名の archive はありません。

## ビルド生成物と配布対象の区別

- `CMakeLists.txt` は通常エンジンの `strata` を `src/program/generate.cpp` から生成します。条件付きで `strata-q36`、`strata-dsv41` なども定義されます。多数の `*_parity`、`*_bench`、test target は主に診断・検証用であり、ターゲット定義だけで Release 配布を意味しません。
- `packaging/README.md` の target matrix と `packaging/build_*` が backend ごとの engine package 作成手順を示します。`package_engine.py` が build directory を component package にし、`feed_tool.py` が feed entry と archive 名を生成します。
- `apps/desktop/src-tauri/tauri.conf.json` は Tauri の bundle target と `host/dist`, `host/server`, Node runtime, Control, harness, engine-bundle の resource mapping を定義します。実際の Release 名は公開 assets で別途確認します。
- `tools/`, `tests/`, `bench/`, `apps/desktop/scripts/`, `apps/host/scripts/` には検証、開発、個別ベンチ用の多数のスクリプトがあります。全ファイルを利用者向け CLI と数えず、呼び出し元と文書で役割を判断します。

## 調査で確認した主なソース

- checkout 情報: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-25）、working tree clean。確認日: 2026-10-26。
- CLI / checkout setup: `strata.py`, `strata_cli/cli.py`, `bin/strata`, `bin/strata.cmd`, `bin/strata.ps1`, `setup.sh`, `SETUP.bat`, `START-HERE.bat`, `update.sh`, `UPDATE.bat`, `bench.sh`, `BENCH.bat`, `setup.py`
- CMake / engine: `CMakeLists.txt`, `src/program/generate.cpp`, `packaging/build_*.sh`, `packaging/build_*.bat`, `packaging/package_engine.py`, `packaging/ENGINE-COMPONENT.md`, `strata_control/engine_component.py`
- Terminal / feed / install: `packaging/install.sh`, `packaging/install.ps1`, `packaging/package_terminal.py`, `packaging/feed_tool.py`, `packaging/README.md`, `packaging/UPDATES.md`, `docs/INSTALL.md`, `docs/TERMINAL.md`, `docs/TERMINAL_LAUNCH.md`
- Desktop: `apps/desktop/package.json`, `apps/desktop/src-tauri/Cargo.toml`, `apps/desktop/src-tauri/tauri.conf.json`, `apps/desktop/src-tauri/nsis/installer.nsi`, `apps/desktop/src-tauri/src/main.rs`, `apps/desktop/scripts/`
- Release 実物: [`releases/latest`](https://github.com/Niko1221/Strata/releases/latest) と [v0.2.5 assets](https://github.com/Niko1221/Strata/releases/expanded_assets/v0.2.5)。公開 assets 名と公開ページ記載を確認。`install-manifest.txt` 本文は取得できなかったため内容未確認。

## 更新手順と次回の調査指示

Strata checkout が更新されたら、`/home/sasasin/src/github.com/Niko1221/Strata` を調べ、この一覧をソースと公開 Release の双方に合わせて更新します。前回の説明に追記するだけでなく、削除・改名・統合された入口、GUI installer、Terminal installer、component/feed 方式の変更も確認してください。

### 調査手順

1. **対象リビジョンと作業状態を記録する。** Strata リポジトリで `git rev-parse HEAD`、`git status --short`、必要に応じて `git log -1 --format='%h %cs %s'` を確認します。作業ツリーに未コミット変更があれば、それも調査対象に含め、既存変更を上書きしないでください。
2. **管理されている CLI 入口を列挙する。** `rg --files` で `.sh`、`.bash`、`.bat`、`.cmd`、`.ps1`、`.py`、`.js`、`.mjs`、`.c`、`.cc`、`.cpp` 等を探します。特に Strata ルート、`bin/`、`packaging/`、`apps/`、`docker/`、`tools/`、`sycl/`、`metal/` を確認し、README、`docs/TERMINAL.md`、各サブディレクトリの README で利用者向けと開発用を見分けます。名前だけで分類せず、呼び出し先・ヘルプ・説明コメントを読みます。
3. **ビルド生成物とエントリーポイントを調べる。** `CMakeLists.txt` とサブディレクトリの `CMakeLists.txt` にある `add_executable`、ターゲット名、条件付きビルド定義を確認します。Python/Node/Tauri の CLI やパッケージングスクリプトについては、起動ファイル、`package.json` の scripts/bin、ビルド・ステージング手順も調べます。`strata` という同名でも、Python の Terminal CLI wrapper とネイティブ推論エンジンを区別し、実際に配布されるファイル名（Windows の `.exe` を含む）を特定します。
4. **設置場所を根拠からたどる。** installer のコピー・展開・PATH 更新、Terminal archive の生成、engine component の管理、実行時の component 解決箇所を読みます。既定値とユーザーが変更できる場所は分けて記載します。単なるビルド出力先、ソース checkout 内の実行場所、インストール後の場所も混同しないでください。
5. **Release 配布物を照合する。** ソース内の release/feed 生成手順（例: `packaging/UPDATES.md`、`packaging/feed_tool.py`、`packaging/package_terminal.py`）と、現在の GitHub Releases のファイル／`install-manifest.txt` が参照可能なら両方を確認します。`latest/download/install.sh`・`install.ps1` がソース内のどのファイルに対応するか、Terminal archive と engine archive/component の名称・プラットフォーム・展開先を確認します。ネットワーク上の最新 Release を確認できなかった場合は、そのことを明記し、ソースにある仕様だけで現行 Release の実ファイル名を断定しないでください。
6. **一覧を見直して更新する。** 役割、Git 上の所在、生成・配布経路、配布時のファイル名、clone/build/install 後の場所をそれぞれ埋められる項目だけ記載します。利用者向け入口、実験・開発用ツール、単なるビルド手順、Release だけで配布するアーカイブ内の実行ファイルを区別します。CLI 引数の網羅は別作業とし、このファイルは入口と配置の一覧に保ちます。
7. **根拠と更新結果を残す。** 文書末尾の「調査で確認した主なソース」を実際に参照したファイルに合わせて更新し、調査対象 Strata の commit hash と調査日を追記します。Markdown の表が読みやすいこと、パス・コマンド名・拡張子がソース記述と一致することを読み返して確認します。

### 次回の依頼文

次回以降は、次のように依頼してください（`000_cli_tools.md` のこの節を指します）。

> Strata ソースコードが更新されたので、`/home/sasasin/src/github.com/sasasin/strata-envvars/docs/cli/000_cli_tools.md` の「更新手順と次回の調査指示」に従って、`/home/sasasin/src/github.com/Niko1221/Strata` を調査し、`000_cli_tools.md` を最新の内容に更新してください。CLI 入口、ビルド生成物、GitHub Release の配布物、ファイル名、インストール先を根拠となるソースから確認し、現行 Release の実体を確認できない項目は推測で埋めず、その制約を記載してください。
