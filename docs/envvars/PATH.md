# `PATH`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。Strata 所有の Python/JavaScript コードが `PATH` を参照する箇所を調査。OS や外部ライブラリ自身による検索規則は対象外。

## 役割

`PATH` は、Strata のセットアップ時にビルドツールを見つける処理、Windows 向けエンジンパッケージで不足 DLL の候補ディレクトリを探す処理、`strata launch` が `cloudflared` などの補助プログラムを探す処理に使われます。また、MCP 子プロセスのコマンド解決、Windows でシェル実行結果を判定する処理でも参照されます。これは Strata 独自の設定値ではなく、各処理が起動元プロセスまたは明示的に渡された環境の `PATH` を参照するものです。

## 値と判定

Strata は `PATH` 全体を真偽値や数値として parse しません。各箇所が `os.pathsep`（実行中 Python のプラットフォームにおけるパス区切り）で分割し、ディレクトリ候補として使うか、`shutil.which` に渡します。

| 経路 | 未設定・空値 | 分割要素の扱い・優先順位 |
|---|---|---|
| Windows エンジンの DLL bundling | 未設定なら空文字として扱い、PATH 由来候補はなし | 空要素を除外。候補の前に `CUDA_PATH/bin/x64`, `CUDA_PATH/bin`, `HIP_PATH/bin/x64`, `HIP_PATH/bin` を追加。実在ディレクトリだけ残す |
| CLI `strata launch` の `cloudflared` 探索 | 未設定なら空文字。空文字列は要素なしとなり、PATH 候補はなし | 空白だけの要素は無視。各要素の前後空白と外側の `"` を除いて実行ファイル名を結合。PATH の後に標準インストール場所を調べる |
| Desktop host の `cloudflared` 探索 | POSIX では `PATH`、Windows では `Path` があればそれを優先し、なければ `PATH`。未設定は空文字 | `:` または `;` で分割し、要素の前後空白と外側の `"` を除く。Strata 内蔵 connector、optional component の後、PATH、標準場所の順 |
| MCP の子プロセス | 起動時に現在の `os.environ` を複製。MCP 設定の `env` が同名キーを指定すれば上書き | `shutil.which(command, path=env.get("PATH"))` の結果を実行ファイルに使い、見つからなければ設定されたコマンド文字列をそのまま使う |
| Windows の shell timeout 判定 | 渡された env の `PATH` が空/未設定なら `Path` を使う | `shutil.which(program, path=...)` で見つからない場合に限り、終了コード 1 を「コマンドが実行できなかった」と分類する |

上表のパス探索規則は Strata の候補組み立てと関数呼び出しについての記述です。大文字小文字、実行ファイル拡張子、探索結果の採用など、`shutil.which` や OS が担う詳細は Strata の独自仕様としては説明しません。

## 有効になる条件

- DLL bundling の PATH 参照は `target.startswith("windows")` の場合だけです。`--search` に非空のディレクトリ一覧を渡した場合はその一覧が既定候補の代わりに使われ、PATH は検索されません。`--search` を指定しない場合、または空一覧の場合に既定候補が使われます。
- `strata launch` では `STRATA_CLOUDFLARED` を trim した値が非空なら、それだけを候補にし、PATH と標準場所への fallback はしません。未設定または空白だけなら PATH を検索します。見つかったファイルは存在確認され、非 Windows では実行可能であることも確認され、起動可能な最低バージョンの確認後に選ばれます。
- Desktop host の connector 探索では `STRATA_CLOUDFLARED` が真値ならその単一候補を使います。`STRATA_CLOUDFLARED_SEARCH=own` なら PATH と標準場所を省き、Strata 内蔵 connector と optional component だけを調べます。各候補を実行して `--version` を確認し、最低バージョン未満や実行できない候補を飛ばします。
- MCP 経路では設定されたコマンドの起動時に参照します。起動後に環境変数を書き換えても、既に作られた子プロセスのコマンド選択は変わりません。
- セットアップコードの `shutil.which` 呼び出しも実行環境の PATH に依存します。CUDA の `nvcc` 探索では PATH 候補の後に `CUDA_PATH`/`CUDA_HOME` や標準 toolkit 場所も調べます。`cmake`/`ninja` 探索では Python 環境の Scripts/bin を PATH より先に見て、その後 PATH、`~/.local/bin` の順で候補にします。

## 実行時の詳細

Windows 向けエンジンの packaging では、未梱包の DLL import を検出し、既定検索ディレクトリから見つかった DLL を staging package にコピーして manifest に追加します。候補順に最初に一致したファイルが採用され、追加の DLL import があれば最大 8 回の pass で続けて解決します。未解決の import が残ると `refusing to package: ...` で packaging を拒否します。PATH のディレクトリが存在しない場合は検索候補から落ちます。

`strata launch` の PATH 検索は access option の可否表示、cloudflared の不足案内、Cloudflare tunnel 起動に使われます。候補が見つからなければオプションは `cloudflared is not installed` と表示され、tunnel 起動は不足案内を返します。起動時は見つけた実行ファイルを完全なパスで実行し、サーバー URL に向けた tunnel を開始します。

セットアップ時には、Metal build の子プロセス向け PATH の先頭へ Python 実行ファイルの親ディレクトリを追加します。ROCm/HIP および Vulkan セットアップでは SDK の bin ディレクトリを PATH の先頭に足し、その環境で `shutil.which` によるツール検出や build を行います。これらは setup プロセス内または子プロセス用環境の更新であり、永続的なシェル設定を書き換える処理ではありません。

Windows の engine 起動用環境では、インストール済み HIP engine の `rocm/bin` など Strata が列挙した library directory を PATH の先頭に追加して子プロセスへ渡します。DeepSeek-V4.1 engine も Windows では同様に `lib_dirs` を PATH 先頭へ加えます。MCP 起動は現在の環境を複製し、設定の `env` で PATH を上書きしてコマンド解決と子プロセス起動の両方に渡します。

## 根拠

- `packaging/package_engine.py:236-246,249-279,305-306,351-355` — Windows の既定 DLL 検索先、明示 `--search` の優先、bundle と不足時の拒否。
- `strata_cli/launch/access.py:70-95,97-132,242-263,270-282,376-399` — `STRATA_CLOUDFLARED` 優先、PATH と標準場所の候補、候補検証、利用可否表示と起動。
- `apps/host/server/cloudflared-find.mjs:42-70,73-110` — Desktop host の候補順、Windows の `Path`/`PATH` 選択、`STRATA_CLOUDFLARED_SEARCH`、候補の実行とバージョン確認。
- `apps/host/server/cloudflare.mjs:13` — Desktop host が Cloudflare connector 探索関数を呼ぶ箇所。
- `serve/mcp.py:93-109` — 現在の環境と MCP 設定の `env` を合成し、PATH を指定してコマンドを解決してから起動。
- `strata_control/time_skip.py:131-153` — Windows の shell timeout 終了コード 1 の場合に、渡された PATH または Path でコマンド存在を判定。
- `setup.py:2054-2065,2118-2129,4196-4204,4616-4626,4690-4695,4777-4799,5481-5510,5539,8020-8025` — PATH を用いた tool 探索と、HIP/Vulkan/engine 子プロセス用 PATH の追加。
- `metal/setup_mac.py:100-104,126-142,169-184` — pip-installed tool 優先の `cmake`/`ninja` 検索と、build 子プロセス用 PATH の先頭追加。
- `docs/DETAILS.md:200` はセットアップが `nvcc` を PATH 等から探す旨を記載。DLL bundling や launch の PATH 優先順位を定義する設計説明は確認できなかったため、上記の細部は実装から記述。
