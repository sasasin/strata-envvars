# Strata のコマンドラインツール一覧

この文書は、Strata リポジトリで管理される CLI、ソースから生成する実行ファイル、GitHub Releases 経由で配布される CLI と推論エンジンの所在・ファイル名・配置先を整理した入口です。個々の CLI の引数を網羅する文書ではありません。

> **名称に注意:** 現在の Strata には、Python 製のユーザー向け **Strata Terminal CLI** と、C++/CUDA/HIP 等でビルドする **推論エンジン** があり、どちらも実行ファイル名が `strata` です。Terminal CLI は `strata.py` を Python で起動し、エンジンは `strata` (`strata.exe`) というネイティブ実行ファイルです。Terminal がモデル実行時に GPU/OS に合うエンジンを別途取得・起動します。

## 配布・利用形態の一覧

| ツール / 役割 | Git 管理上の所在 | 生成・配布経路 | 実行ファイル名 | 主な設置場所 |
| --- | --- | --- | --- | --- |
| 初回セットアップ（POSIX） | Strata ルート `setup.sh`、`setup.py` | ソース checkout に同梱 | `setup.sh` → `setup.py` | clone した Strata ディレクトリ。仮想環境は通常 `.venv/`、セットアップ後の起動も同ディレクトリから |
| 初回セットアップ（Windows） | `SETUP.bat` → `START-HERE.bat`、`setup.py` | ソース checkout に同梱 | `SETUP.bat` / `START-HERE.bat` | clone した Strata ディレクトリ。Python 仮想環境は `.venv\Scripts\` |
| 既存セットアップの更新補助 | Strata ルート `update.sh`、`UPDATE.bat` | ソース checkout に同梱 | `update.sh` / `UPDATE.bat` | clone した Strata ディレクトリ |
| クイックベンチマーク | Strata ルート `bench.sh`、Windows 用 `BENCH.bat` | ソース checkout に同梱 | `bench.sh` / `BENCH.bat` | clone した Strata ディレクトリ。通常の比較可能なベンチマークは Terminal CLI の `strata bench run` |
| Strata Terminal CLI（POSIX） | `strata.py`、`strata_cli/`、`bin/strata` | ソース checkout では wrapper が Python ソースを起動。Release アーカイブには Python ランタイムと依存パッケージを同梱 | `strata` (POSIX wrapper。内部で `strata.py` を実行) | checkout: `bin/strata` と `strata.py` があるリポジトリ。Release 導入: 通常 `~/.local/share/strata/terminal/<version>/bin/strata`; `~/.local/bin/strata` シンボリックリンクが PATH 上の入口 |
| Strata Terminal CLI（Windows） | `strata.py`、`strata_cli/`、`bin/strata.cmd`、`bin/strata.ps1` | ソース checkout 同梱、または Windows Terminal ZIP アーカイブ | `strata.cmd` / `strata.ps1` (入口。実装は Python `strata.py`) | checkout: リポジトリと `.venv`。リリース導入: `%LOCALAPPDATA%\Strata\terminal\<version>\bin`。同 `bin` がユーザー PATH に追加される。`STRATA_NO_PATH=1` では PATH 変更を抑止 |
| 推論エンジン（CUDA/HIP 等） | CMake ターゲット `strata`、主入口 `src/program/generate.cpp` | `setup.py` のビルド、またはプラットフォーム別 `packaging/build_*.sh` / `.bat` など。Release の署名付き engine component/feed からも取得 | Linux/macOS: `strata`; Windows: `strata.exe` | ソースビルド: ビルドディレクトリ。Terminal 利用: ユーザー component 領域（通常 Linux/macOS `$XDG_DATA_HOME/strata/components` または `~/.local/share/strata/components`、Windows `%LOCALAPPDATA%\Strata\components`）。Terminal の run config は `component:strata-engine` を参照 |
| GitHub Release の POSIX インストーラー | `packaging/install.sh` | Release に `install.sh` として掲載。利用例: `curl -fsSL https://github.com/Niko1221/Strata/releases/latest/download/install.sh -o install.sh && sh install.sh` | `install.sh` | 取得したスクリプトを実行する場所は任意。一時作業領域を使い、Terminal をユーザー領域に展開。通常 `~/.local/share/strata/terminal/<version>/` と `~/.local/bin/strata`。`STRATA_DATA_DIR`、`STRATA_BIN_DIR` で変更可 |
| GitHub Release の Windows インストーラー | `packaging/install.ps1` | Release に `install.ps1` として掲載。利用例: `irm https://github.com/Niko1221/Strata/releases/latest/download/install.ps1 \| iex` | `install.ps1` | スクリプトを実行する場所は任意。通常 `%LOCALAPPDATA%\Strata\terminal\<version>\` に展開し、その `bin` をユーザー PATH に登録。`STRATA_DATA_DIR` でデータ/導入ルート変更、`STRATA_NO_PATH=1` で PATH 登録を抑止 |

上表の Terminal Release アーカイブは `strata-terminal-<version>-<platform>.tar.gz`（Linux/macOS）または `.zip`（Windows）形式で、`install-manifest.txt` が選択するファイルです。インストーラー自身はインストール後も常駐する CLI ではありません。初回モデル起動時に必要なエンジンを Release feed から取得します。

## ソース内の関連実行ファイル

Strata にはユーザー向け `strata` のほか、CMake で生成される開発・診断用プログラムもあります。例として `strata-plan`、`strata-device`、`strata-load`、`strata-concurrent`、`strata-overlap`、`strata-gguf`、`strata-dequant` があります。さらに backend/option に応じて `strata-dsv41`、`strata-q36` 等の専用プログラムや、多数の `*_parity` / `*_bench` が生成されます。これらは通常の Terminal 製品コマンドと同義ではなく、ビルド条件や CMake target が異なります。出典は `CMakeLists.txt` の `add_executable(...)` 定義です。

リポジトリ内の `.sh` / `.bat` / `.ps1` 全てがエンドユーザー向け CLI ではありません。`packaging/build_*` はビルド手順、`docker/` はコンテナ運用、`tools/`・`sycl/tools/`・`metal/tests/` や `bench/results/` 以下には開発、検証、個別ベンチマーク用スクリプトがあります。この一覧は、汎用的なユーザー入口と配布エントリーポイントを記録し、個人・実験用の全スクリプトを列挙するものではありません。

## 調査で確認した主なソース

- Strata ルート: `setup.sh`, `SETUP.bat`, `START-HERE.bat`, `update.sh`, `UPDATE.bat`, `bench.sh`, `BENCH.bat`, `setup.py`, `strata.py`
- Terminal launcher: `bin/strata`, `bin/strata.cmd`, `bin/strata.ps1`
- Release packaging / build: `packaging/install.sh`, `packaging/install.ps1`, `packaging/package_terminal.py`, `packaging/feed_tool.py`, `packaging/README.md`, `packaging/UPDATES.md`
- 推論エンジン: `CMakeLists.txt` (`add_executable(strata src/program/generate.cpp)`)
- Terminal の機能・配置の説明: `docs/TERMINAL.md`

調査基準: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-24）。GitHub の latest Release のファイル一覧は今回確認できていないため、Release 実体ではなく Strata checkout 内の packaging ソースで確認できたファイル名・配置仕様を記載しています。Release ファイル名や配置仕様は更新される可能性があるため、再調査時は上記 packaging ソースと Release feed 生成手順を確認してください。

## 更新手順と次回の調査指示

Strata のソースコードが更新されたら、`/home/sasasin/src/github.com/Niko1221/Strata` にある更新後の checkout を調べ、この文書の一覧と説明を現状に合わせて更新します。古い一覧への追記だけで済ませず、削除・改名・統合された入口や廃止された配布方法も確認してください。

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
