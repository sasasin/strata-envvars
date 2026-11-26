# `PATH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`PATH` は、Strata の Python 側が外部コマンドを探す際の検索元であり、engine を子プロセスとして起動するときの環境にも使われる。Strata 独自の一つの設定スイッチではなく、読み取り側ごとに探索対象・優先順位が異なる。例として、setup は `nvcc`、`cmake`、`ninja`、HIP/Vulkan の build tool を探し、Terminal は `nvidia-smi`、`rocminfo`、`lspci`、MCP command、`cloudflared` などを探す。探索できない場合の処理は各呼び出し元に依存する（`terminal/setup.py:2653-2665,2717-2738,5678-5689,9524-9528`、`terminal/strata_control/engine_component.py:571-580,989-1006`、`terminal/serve/mcp.py:138-154`、`terminal/strata_cli/launch/access.py:122-146`）。

Windows では、engine package の `BUILD.json` にあるライブラリ directory を `PATH` の先頭へ追加した環境を、HIP engine の probe や engine version 確認などに渡す。Linux/macOS の同じコード経路は `LD_LIBRARY_PATH` / `DYLD_LIBRARY_PATH` を使う（`terminal/setup.py:5192-5204,9634-9639`、`terminal/strata_control/local_engine.py:48-55`）。ここで確認できるのは Strata が子プロセスに渡す値であり、OS loader の PATH 解釈や外部ライブラリの挙動は本書の対象外。

## 値と判定

PATH 全体を数値や boolean として parse する共通処理はない。直接走査する箇所は `os.pathsep`（OS ごとの区切り文字）で分割し、読み取り側によって前後空白・引用符を除く場合と除かない場合がある。`shutil.which` を使う箇所は PATH を個別に変換せず、コマンド名の探索に渡す。未設定時の処理も統一されていない。

| 読み取り経路 | unset / 空文字 | 設定値の扱い・例 |
|---|---|---|
| `setup.py` の `shutil.which` | Python の `shutil.which(name)` に PATH 引数を渡さず、実行環境でコマンドを探す。PATH が空／未設定の場合の OS・Python 標準機能の詳細は Strata 独自コードでは定義しない。 | `nvcc`、`cmake`、`ninja`、`git`、`g++` などの場所を検索する。PATH 上で見つからない場合、候補一覧・build 条件に応じて toolkit の既知 directory を調べるか、未検出として setup を止める（`terminal/setup.py:2653-2665,2717-2738,6624-6687,9524-9528`）。 |
| `launch/access.py` の `cloudflared` 探索 | 未設定は `""` に置き換わり、PATH directory は追加されない。空文字も分割後の空要素が無視される。 | `os.pathsep` で分割し、directory の前後空白と外側の `"` を除去する。各 directory に `cloudflared`（Windows は `.exe`）を結合する。`STRATA_CLOUDFLARED` が空でない場合は PATH より優先し、その一候補だけを返す。PATH の後に OS 別の既知 directory も検索する（`terminal/strata_cli/launch/access.py:122-146,176-189`）。 |
| `launcher_heal.stale_launchers` | `PATH` 未設定は空文字扱いとなり、PATH 由来の directory はない。 | `os.pathsep` で分割し、各 directory の前後空白と外側の `"` を除く。Windows で Strata 固有の `strata.ps1` と隣接する `strata.cmd` を探すために使う（`terminal/strata_cli/launcher_heal.py:30-52,55-77`）。本 checkout では `heal()` の呼び出し元を確認できず、この関数が通常起動経路で実行されるとは断定できない。 |
| `serve/mcp.py` | 基本環境は `dict(os.environ)`。設定の `env` が同名キーを上書きするため、設定で PATH を空にした場合は `shutil.which(..., path="")` に空文字が渡る。キーがなければ `None` が渡される。 | PATH を使って設定済み MCP command を探索する。見つからない場合は元の command 文字列を executable として起動し、起動不能なら `could not start {command!r}: {e}` の `McpError` にする（`terminal/serve/mcp.py:138-154`）。 |
| `time_skip.py` | `env.get("PATH") or env.get("Path")` を使うため、PATH が未設定または空なら `Path` を試す。両方が空ならコマンド不在判定になる。 | PATH で最初の command を `shutil.which` で探し、見つからない場合はチェック結果を `unknown` とする。複合 shell command や builtin はこの PATH 判定を行わない（`terminal/strata_control/time_skip.py:145-153,176-201`）。 |
| engine 用 `engine_env` | `dict(os.environ)` で元の環境を複製。Windows で package library directory がなければ PATH を変更しない。 | Windows かつ engine package の `BUILD.json` に実在する `lib_dirs` があれば、それらを PATH の先頭に `os.pathsep` 区切りで追加し、元 PATH は値が truthy の場合に後ろへ残す。Linux/その他は PATH ではなく `LD_LIBRARY_PATH` を更新する（`terminal/setup.py:5192-5204,5270-5276`）。 |
| Windows package 作成 | PATH 未設定は `""` として分割され、PATH からの directory 候補がなくなる。 | `CUDA_PATH`、`HIP_PATH` の `bin/x64` / `bin` 候補を先に追加し、その後 PATH を `os.pathsep` で分割する。存在する directory のみを返し、Windows package の不足 DLL 探索に使う（`tools/packaging/package_engine.py:239-249,252-259`）。 |

その他の明示的な変更箇所では、HIP build 時に ROCm の `bin` と clang directory、または Vulkan SDK の `bin` を PATH の先頭に置き、元の PATH を後置する（`terminal/setup.py:5681-5689,5750-5759,5860-5864`）。Windows の CUDA package build は `os.environ` のキーを大文字化して PATH を取り出し、CUDA `bin` を前置して cmake を探す（`tools/packaging/build_cuda_windows.py:110-122,170-174`）。これらは読み取り側が構築する子 build 環境であり、現在の環境変数値の有効／無効判定ではない。

他の `shutil.which` 利用箇所も PATH をコマンド探索 API に渡す。Terminal では GPU/driver probe（`engine_component.py:571-585,771-780,942-951,989-1006`; `doctor.py:230-243,394`; `updater.py:285-292`; `tune_machine.py:77-94`; `strata_mcp.py:1173,1229`）、setup の HIP tool（`setup.py:5531-5535,5754-5759`）、cloudflared 以外の `tailscale`（`launch/access.py:228`）を探す。開発・packaging tool では `engine/metal/setup_mac.py:106,139-140,182`、`engine/sycl/setup_intel.py:215-218`、`tools/check_cuda_spills.py:403-409,621-634`、`tools/check_isa_guard.py:85`、`tools/check_no_mmq.py:77-78`、`tools/check:139,163,241-270,349`、`tools/packaging/smoke_terminal.py:71,158` が PATH 上の tool を調べる。これらは各 caller の条件でだけ実行され、PATH 共通の fallback や結果ログは設けていない。

インストーラーにも別の PATH 処理がある。POSIX の `install.sh` は現在の PATH に install 用 `bin` directory が完全一致で含まれるかを `case` で調べ、含まれなければ `export PATH=...` の profile 追記例を表示する（`tools/packaging/install.sh:176-185`）。Windows の `install.ps1` は既定でレジストリのユーザー `Path` に install directory を追加する。同じ directory が既にあれば追加せず、既存値の文字列や registry value kind を保持し、追加失敗時は警告を表示する。`STRATA_NO_PATH=1` の場合は registry を変更せず、install 実行中の `$env:Path` にも追加しない（`tools/packaging/install.ps1:73-98,216-223`）。

## 有効になる条件

- PATH は値が「有効」かどうかを共通判定する設定ではない。利用するコマンド探索関数が呼ばれる場面でのみ、その探索結果に影響する。
- `setup.py` の tool 探索では PATH 上の候補より先に、実行中 Python の隣に pip install された tool を候補にする。PATH 上の `cmake` はその後で、さらに `~/.local/bin` が候補になる。実行不能な候補と最低 CMake version 未満の候補はスキップされる（`terminal/setup.py:2717-2738`）。CUDA 検出は `nvcc` を PATH で探した後、`CUDA_PATH` / `CUDA_HOME` と OS 別の既知場所も調べる（`terminal/setup.py:2653-2665`）。
- `cloudflared` は非空 `STRATA_CLOUDFLARED` があれば PATH 探索を行わず、その指定を優先する。PATH で見つからなくても既知 directory の検索に進む（`terminal/strata_cli/launch/access.py:122-146`）。
- MCP command は MCP 設定の `env` が親プロセスの環境を上書きできる。PATH がコマンドを解決しない場合も Strata は command 名のまま起動を試し、`OSError` を `McpError` にする（`terminal/serve/mcp.py:138-154`）。
- 子 engine の Windows PATH 前置きは `engine_env()` が呼ばれ、package `lib_dirs` に存在する directory がある場合に限る。設定値の内容に関係なく、PATH は元の値を suffix として引き継ぐ（`terminal/setup.py:5192-5204,9634-9639`）。
- `launcher_heal` の PATH 探索は Windows の場合だけ有効だが、この checkout では関数の呼び出し元を確認できていない（`terminal/strata_cli/launcher_heal.py:30-77`）。

## 実行時の詳細

PATH は各処理が環境を参照・複製するときに評価され、Strata による一括 static cache はない。例外として `cloudflared_version()` は PATH 自体ではなく見つけた実行ファイルの version 結果を `(path, mtime)` キーで cache する（`terminal/strata_cli/launch/access.py:149-167`）。プロセス環境を実行中に変更した場合に、すでに cache された cloudflared version が再取得されるとは限らない。

MCP 起動は親環境を複製してから MCP 個別の `env` を上書きし、その PATH を使って command を解決したうえで同じ環境を子プロセスへ渡す（`terminal/serve/mcp.py:138-152`）。engine version / GPU probe では、Strata が元環境を複製し、Windows なら engine package の library directory を先頭に足した環境を子 engine に渡す。Linux などでは対象変数を `LD_LIBRARY_PATH` に切り替える（`terminal/setup.py:5192-5204,9634-9639`、`terminal/strata_control/local_engine.py:48-55`）。setup の HIP/Vulkan build も、同一 setup プロセスの環境辞書を書き換えてから build command を呼ぶ（`terminal/setup.py:5681-5701,5750-5774,5860-5864`）。

## ログと測定値

PATH の値そのものを出す共通ログや測定値は確認できない。個別の失敗は呼び出し元に現れる。例えば `doctor` の NVIDIA probe は `nvidia-smi is not installed or is not on PATH` を返し、MCP 起動失敗は `could not start ...` のエラーになる（`terminal/strata_control/doctor.py:230-243`、`terminal/serve/mcp.py:149-154`）。`setup.py` は必要 build tool が PATH 等の候補で見つからない場合、条件に応じて不足 tool の説明や install 提案を表示し、tool 不足を `fail()` で終了させる（`terminal/setup.py:6624-6658,6683-6687,9524-9528`）。

`launcher_heal.heal()` が呼ばれた場合、PATH 内に条件に合う旧 `strata.ps1` があればファイルを `strata-direct.ps1` に rename し、stderr と隣接する `launcher-heal.log` に記録する。ただし本 checkout では呼び出し元が見つからないため、通常利用での発生は確認できない（`terminal/strata_cli/launcher_heal.py:30-77`）。性能測定値は該当しない。

## 根拠

- setup と build tool の探索・PATH 前置き: `terminal/setup.py:2653-2665,2717-2738,5192-5204,5678-5701,5750-5774,5841-5864,6624-6687,9524-9528`
- Terminal command / cloudflared 探索: `terminal/strata_cli/launch/access.py:122-189`; `terminal/strata_control/engine_component.py:571-585,989-1006`; `terminal/strata_control/time_skip.py:145-201`; `terminal/strata_control/doctor.py:230-243`; `terminal/strata_control/tune_machine.py:77-94`; `terminal/strata_control/updater.py:275-293`
- 他の `shutil.which` 利用箇所: `terminal/strata_control/engine_component.py:771-780,942-951`; `terminal/strata_control/doctor.py:394`; `terminal/strata_control/updater.py:285-292`; `terminal/tools/strata_mcp.py:1173,1229`; `terminal/strata_cli/launch/access.py:228`; `engine/metal/setup_mac.py:106,139-140,182`; `engine/sycl/setup_intel.py:215-218`; `tools/check_cuda_spills.py:403-409,621-634`; `tools/check_isa_guard.py:85`; `tools/check_no_mmq.py:77-78`; `tools/check:139,163,241-270,349`; `tools/packaging/smoke_terminal.py:71,158`
- installer の読み取り・更新: `tools/packaging/install.sh:176-185`; `tools/packaging/install.ps1:73-98,216-223`
- MCP 子プロセス: `terminal/serve/mcp.py:138-154`
- Windows engine 子環境: `terminal/strata_control/local_engine.py:48-69`; `terminal/setup.py:5192-5204,9634-9639`
- 起動修復 helper: `terminal/strata_cli/launcher_heal.py:24-77`
- Windows DLL 探索を行う package tool: `tools/packaging/package_engine.py:239-259`; `tools/packaging/build_cuda_windows.py:110-122,170-174`
