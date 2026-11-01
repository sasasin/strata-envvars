# `STRATA_PYTHON`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。外部ライブラリの環境変数は対象外。

## 役割

Strata Terminal の `bin/strata`、`bin/strata.cmd`、`bin/strata.ps1` では、Python 実行ファイルの明示指定です。空でない指定は launcher の他の候補（同梱 Python、checkout の venv、PATH 上の Python）より優先されます。Strata App Host の Python resolver も `STRATA_PYTHON` を参照し、非空なら `STRATA_NATIVE_PYTHON` や Control 同梱 Python より優先します。

この値は「Python のパス」として使われ、引数を含むコマンド文字列には対応していません。Terminal launcher の指定値については Python のバージョンを検査しません。3.10 以上という案内はありますが、明示指定値の最低バージョンを保証するチェックはありません。

## 値と判定

| 読み取り経路 | unset / 空文字 | 非空値の判定・変換 | 無効値の結果 |
|---|---|---|---|
| POSIX `bin/strata` | `${STRATA_PYTHON:-}` と `-n` により unset と空文字は同じ。次の候補へ進む | 値全体を引用してパスとして使い、`-x` で実行可能か確認。数値変換やバージョン検査なし | 実行可能でなければ stderr に `strata: STRATA_PYTHON=<値> is not executable`、終了コード 5。指定が実行可能でも Python でなければ後続の実行に失敗し得る |
| Windows `bin/strata.cmd` | `if defined STRATA_PYTHON` が真なら指定経路へ進む。空の環境値は未設定と区別されない扱い | 値全体を引用したパスとして `if not exist` で確認。実行可能性・Python バージョンは検査しない | パスが存在しなければ stderr に `strata: STRATA_PYTHON=<値> does not exist`、終了コード 5。存在しても Python でなければ実行時に失敗し得る |
| Windows `bin/strata.ps1` | PowerShell の `if ($env:STRATA_PYTHON)` により unset と空文字は次の候補へ進む | `Test-Path -LiteralPath` でパスの存在を確認し、その文字列を実行コマンドに使う。実行可能性・Python バージョンは検査しない | パスが存在しなければ stderr に `strata: STRATA_PYTHON=<値> does not exist`、終了コード 5。存在しても Python でなければ実行時に失敗し得る |
| App Host `resolvePython()` | JavaScript の `env.STRATA_PYTHON || env.STRATA_NATIVE_PYTHON` により unset と空文字は同様に扱い、後者または次候補へ進む | 非空文字列をそのまま `{ command: explicit, args: [] }` として選ぶ。パス存在、実行可能性、Python バージョンの事前検査なし | resolver は失敗を判定せず値を返す。実際の spawn が失敗する場合は呼び出し側でエラーになる |
| `integrations/harness/tool_flow_e2e.py` | `os.environ.get("STRATA_PYTHON", sys.executable)` により unset のみ `sys.executable` に fallback。空文字は空文字のまま | `python -m serve.server ... --engine mock` の実行ファイル要素として渡す | 起動できなければ `subprocess.Popen` の起動失敗。これは E2E ツール内の読み取りで、通常の製品 launcher の選択規則ではない |

POSIX launcher では有効な override があればそれを最優先します。なければ同梱 Python、続いて PATH や macOS の既知の配置場所にある Python 3.10 以上を探索します。Windows launcher の優先順は override、同梱 Python、checkout の `.venv`、`py -3`、`python` です。これらの fallback 候補には 3.10 以上の確認がありますが、明示 override にはありません（`bin/strata:31-73`, `bin/strata.cmd:16-32`, `bin/strata.ps1:25-46`）。

## 有効になる条件

- `bin/strata`、`bin/strata.cmd` または `bin/strata.ps1` を通じて Terminal CLI を起動する場合に interpreter 選択へ使われます。CLI のサブコマンドによって優先順位は変わりません。
- POSIX launcher の `serve` または `bench` では、選んだ interpreter に必要な Python packages があるか先に確認します。不足・probe 失敗時は stderr に `strata: the interpreter <PY> is missing packages the API server needs.` と pip install 案内を出して終了コード 5 です。その他の CLI ではこの probe を行いません（`bin/strata:102-126`）。
- App Host の `resolvePython()` では、非空の `STRATA_PYTHON` が非空の `STRATA_NATIVE_PYTHON` に優先します。両方なければ Control 同梱 Python、repo venv、Windows の `py -3` / `python.exe`、または POSIX の Homebrew Python 3.11/3.10 / `python3` の順です（`apps/host/server/python-resolver.mjs:33-52`）。
- Host の packaged Control を動かす環境は `controlEnvironment()` が `STRATA_PYTHON` と `STRATA_NATIVE_PYTHON` を削除してから作ります。したがって Host のプロセスで値を選択に使う経路と、Control 子プロセスの環境とは区別されます（`apps/host/server/control-runtime.mjs:88-103`）。
- Source checkout の native-control は resolver で選んだ interpreter で MCP client、source server、auto-tuner、更新などの Python コマンドを起動します。ただし較正・tune job は resolver の結果を得た後、`command` を repo の venv Python に置き換えます。`STRATA_PYTHON` はその較正・tune 実行の interpreter 選択には効きません（`apps/host/server/native-control.mjs:55,98,102-110,387-390,408-414`）。
- Host の `index.mjs` は起動時に `resolvePython({ repo, control })` を一度呼び、その結果を tune 関連の Python 設定として保持します。環境を書き換えてもこの設定は再評価されません。native-control の resolver は呼び出し時の env 値を cache key に含めるため、値が変われば別 key の選択になります（`apps/host/server/index.mjs:763-769,903-910`; `apps/host/server/python-resolver.mjs:31-55`）。

## 実行時の詳細

POSIX launcher は非空の `STRATA_PYTHON` が実行可能かを確認してから選択し、override 選択時は private runtime 用の `PYTHONHOME` / `PYTHONPATH` 除去を行いません（同梱 runtime を選んだ場合だけ除去します）。その後、選択した interpreter で `strata.py` を `exec` します。CLI 引数はそのまま `strata.py` へ渡されます（`bin/strata:31-36,76-100,128-134`）。

Windows launcher は override を指定した場合、bundled interpreter 選択時の `PYTHONHOME` / `PYTHONPATH` 除去を行わず、最終的に `strata.py` を起動します。cmd と PowerShell は起動時に `PYTHONUTF8=1` を設定します（`bin/strata.cmd:29-44`; `bin/strata.ps1:28-56`）。

App Host の resolver は通常 `process.env` を入力にします。`index.mjs` の結果は Host 起動時の Python 選択に使われます。source native-control の resolver 結果は Python 子プロセス起動時に使われ、source server、MCP client、auto-tuner などは `{ ...process.env, ... }` の環境を渡すため `STRATA_PYTHON` も子プロセス環境に残ります。対して packaged Control の環境生成では同名を削除します（`apps/host/server/native-control.mjs:55,98,102-110,387-390`; `apps/host/server/control-runtime.mjs:88-103`）。

`integrations/harness/tool_flow_e2e.py` の読み取りは別経路です。この E2E tool flow は `STRATA_PYTHON` か `sys.executable` を使って mock server の子プロセスを開始します（`integrations/harness/tool_flow_e2e.py:58-66,406-420`）。

## 根拠

- Terminal POSIX launcher の優先順、override 判定、失敗、serve/bench probe、実行: `bin/strata:8-17,31-73,76-88,102-134`。
- Windows cmd launcher の override と fallback、失敗・起動: `bin/strata.cmd:4-7,16-32,34-48`。
- PowerShell launcher の override と fallback、失敗・起動: `bin/strata.ps1:1-7,25-56`。
- App Host resolver の優先順位・cache・fallback: `apps/host/server/python-resolver.mjs:31-57`。
- Host 起動時の resolver と用途: `apps/host/server/index.mjs:763-769,903-910`。
- Source native-control の resolver 呼び出し、Python child process、較正/tune における venv 上書き: `apps/host/server/native-control.mjs:55,98-110,387-390,408-414`。
- Packaged Control 子プロセス向け環境からの削除: `apps/host/server/control-runtime.mjs:88-103`。
- 同梱 E2E harness の独立した読み取り: `integrations/harness/tool_flow_e2e.py:58-66,406-420`。
- 候補一覧: `docs/envvars/000_envvers.md:1344`。候補名だけでは通常利用時の読み取りを保証しない。
