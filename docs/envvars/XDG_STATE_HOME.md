# `XDG_STATE_HOME`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。対象は Strata 所有のコードと同梱設定。外部ライブラリの挙動は対象外。

## 役割

POSIX 系で Strata がユーザー単位の状態を置く基底ディレクトリを指定します。Python 側は最終的に `<XDG_STATE_HOME>/strata` を使い、Node の host 側も同じ規則で状態ルートを組み立てます。ここから runtime 管理ファイル、プロセス記録、launch 関連ファイル、tuning 結果、Time-skip データなどの場所が決まります（`strata_control/paths.py:13-21`, `apps/host/server/platform-paths.mjs:16-32`）。

## 値と判定

文字列の数値変換や形式検証はありません。Python は `environ.get("XDG_STATE_HOME") or ...`、Node は `env.XDG_STATE_HOME || ...` で判定します。

| 状態 | POSIX の Python / Node | Windows の Python / Node |
|---|---|---|
| 未設定 | `~/.local/state/strata`（Node は `HOME` が空なら `./.local/state/strata`） | `LOCALAPPDATA/Strata`。`LOCALAPPDATA` もなければユーザープロファイル下の `AppData/Local/Strata` |
| 空文字 | 未設定と同じ fallback | 参照しない |
| 非空文字列 | 値をそのまま state ルートとして使い、その下に `strata` を追加 | 参照しない |

空白だけの値や相対パスも非空なので採用されます。Python の `Path` と Node の `path.posix.join` がパスを組み立てます。一般の `state_base()` / `stateRoot()` 利用では絶対パス検査をしませんが、Python の managed runtime は `STRATA_RUNTIME_DIR` が未指定ならその下の `runtime` を使い、最終パスが絶対でなければ `STRATA_RUNTIME_DIR must be absolute` で失敗します（`strata_control/runtime.py:101-111`）。

## 有効になる条件

- Python `state_base()` は Windows では `LOCALAPPDATA` を使い、`XDG_STATE_HOME` を見ません。POSIX では `XDG_STATE_HOME` を使います（`strata_control/paths.py:13-21`）。
- Node host も `platform === 'win32'` では `%LOCALAPPDATA%\Strata` 系の経路を取り、POSIX 系でのみ `XDG_STATE_HOME` を参照します（`apps/host/server/platform-paths.mjs:17-23`）。
- Docker イメージは `XDG_STATE_HOME=/data/state` を image environment に設定するため、既定の POSIX state base は `/data/state/strata` です（`docker/Dockerfile:102-108`）。同梱 entrypoint にも `${XDG_STATE_HOME:-/data/state}/strata` の代入がありますが、`STATE_DIR` は同スクリプト内で後続利用されていません（`docker/entrypoint.sh:27-31`）。
- 関連する専用指定がある場合、その機能は state base の該当サブディレクトリを使わないことがあります。たとえば Python managed runtime は非空の `STRATA_RUNTIME_DIR`、Time-skip は CLI の `--state-dir` または非空の `STRATA_TIMESKIP_DIR`、tuning は `--state-dir` または非空の `STRATA_TUNE_DIR` を優先します（`strata_control/runtime.py:101-107`, `strata_cli/cli.py:1476-1483,1643-1650`）。

## 実行時の詳細

Python の共通関数は、引数 `environ` を省略した場合に `os.environ` を参照します。OS 判定も省略時に行います。各利用箇所は必要時にこの関数を呼ぶため、値をプロセス起動時に一度だけ固定する cache はありません。runtime の既定場所は `<state base>/runtime`、process records は `<state base>/procs`、launch 用ディレクトリは `<state base>/launch` です（`strata_control/runtime.py:101-112`, `strata_control/procs.py:192-200`, `strata_cli/launch/runner.py:555-559`, `strata_cli/launch/access.py:364-368,391-399`）。tuning の再確認マークは既定で `<state base>/tuning/recheck.json`、CLI の tuning / Time-skip データはそれぞれ `<state base>/tuning` と `<state base>/time-skip` に置かれます（`strata_control/preset_marks.py:35-36`, `strata_cli/cli.py:1476-1485,1643-1650`）。

Node host は `stateRoot()` の既定引数 `process.env` から値を読み、tuning と Time-skip の既定ディレクトリをそれぞれ state root 配下にします。専用の `STRATA_TUNE_DIR` / `STRATA_TIMESKIP_DIR` が truthy ならそちらを返します（`apps/host/server/platform-paths.mjs:17-32`）。

値自体についてのログ、警告、エラーはありません。パスが書き込み可能か、private な属性を満たすかなどの検査やエラーは各利用機能側で行われます。子プロセスへの環境継承・上書きで `XDG_STATE_HOME` を特別扱いする処理は確認できません。

## 根拠

- `strata_control/paths.py:13-21` — Python 共通 state base。値判定、Windows 分岐、fallback。
- `strata_control/runtime.py:101-123`, `strata_control/procs.py:192-200` — managed runtime と process records の保存先。
- `strata_control/preset_marks.py:35-36`, `strata_cli/cli.py:1476-1485,1643-1650`, `strata_cli/launch/runner.py:555-559`, `strata_cli/launch/access.py:364-368,391-399` — tuning、Time-skip、launch / tunnel の保存先と上書き。
- `apps/host/server/platform-paths.mjs:17-32` — Node host の state root と専用ディレクトリ指定。
- `docker/Dockerfile:102-108`, `docker/entrypoint.sh:27-31` — Docker image の既定値と entrypoint 内の未使用代入。
- `docs/TERMINAL.md:94` — runtime / logs / state の説明。実装上は各機能の専用指定や Windows 分岐もあるため、この文書は概要として参照。
