# `XDG_STATE_HOME`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

POSIX 系で Strata がユーザー状態を保存する基準ディレクトリを指定する。端末側は `strata_control.paths.state_base()` が `${XDG_STATE_HOME}/strata` を返し、ランタイム状態、プロセス記録、起動設定、serve の前回実行マーカー、通信拒否記録などの保存先に使う（`terminal/strata_control/paths.py:13-21`、`terminal/strata_control/runtime.py:128-139`、`terminal/strata_control/procs.py:192-200`、`terminal/strata_cli/launch/runner.py:841-845`、`terminal/serve/lastrun.py:42-47`、`terminal/strata_control/netpolicy.py:214-223`）。Node ホスト側は同じ規則で `strata/tuning`、`strata/time-skip`、温度プローブの marker を解決する（`app/host/server/platform-paths.mjs:16-32`、`app/host/server/index.mjs:886-895`、`app/host/server/timeskip.mjs:26-29,313-320`、`app/host/server/temperature-telemetry.mjs:100-101`）。この変数は保存場所を変え、engine の backend、モデル選択、生成内容や token 計算は制御しない。

Docker image は `XDG_STATE_HOME=/data/state` を既定で設定しているため、image 内の通常起動では state root は `/data/state/strata` になる（`tools/docker/Dockerfile:105-112`、`tools/docker/Dockerfile.src:147-149`）。entrypoint にも `XDG_STATE_HOME` を展開する `STATE_DIR` 代入があるが、その変数は同ファイル内で後続利用されていない（`tools/docker/entrypoint.sh:44-49`）。

## 値と判定

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Linux/macOS 等の POSIX、Python 端末 | `Path.home()/.local/state/strata` | 空でない文字列をそのままパスとして使い、末尾に `strata` を加える | 空文字は unset と同じ fallback。文字列形式の検査・数値変換はない |
| Linux/macOS 等の POSIX、Node ホスト | `$HOME/.local/state/strata`。`HOME` も unset/空なら `./.local/state/strata` | 空でない文字列を `posix.join(..., 'strata')` に渡す | 空文字は fallback。形式検査・数値変換はない |
| Windows、Python 端末および Node ホスト | Python は `%LOCALAPPDATA%`、なければ `Path.home()/AppData/Local` に `Strata`。Node は `%LOCALAPPDATA%`、なければ `%USERPROFILE%`（なければ Node の home）配下 `AppData\\Local\\Strata` | `XDG_STATE_HOME` は参照されず、値にかかわらず無効 | 該当なし（Windows 分岐は `LOCALAPPDATA` を使う） |

Python は `environ.get("XDG_STATE_HOME") or fallback`、Node は `env.XDG_STATE_HOME || fallback` としているため、未設定と空文字はいずれも fallback になる。`0`、`false`、空白だけの文字列も非空なのでパス値として採用される。相対パスを拒む共通検証はなく、通常の保存先では相対パスがプロセスの作業ディレクトリ基準になる。管理 runtime では、解決後の `.../runtime` が絶対パスでなければ `ProfileError("STRATA_RUNTIME_DIR must be absolute")` となる（`terminal/strata_control/runtime.py:128-138`）。実装箇所: `terminal/strata_control/paths.py:13-21`、`app/host/server/platform-paths.mjs:17-23`。

## 有効になる条件

- Python の `state_base()` を使う端末側機能で、OS が Windows ではないこと。Windows は `LOCALAPPDATA` 分岐を使う（`terminal/strata_control/paths.py:15-21`）。
- Node ホストでも `stateRoot()` は Windows (`win32`) では `LOCALAPPDATA` を使う。POSIX 系の state root を基にするのは tuning、Time-skip、temperature telemetry 等の呼び出し経路に限られる（`app/host/server/platform-paths.mjs:17-32`）。
- tuning と Time-skip にはそれぞれ別の保存先指定が優先される。CLI の `--state-dir` があればそれを使い、なければ `STRATA_TUNE_DIR` または `STRATA_TIMESKIP_DIR`、どちらもなければ `XDG_STATE_HOME` 由来の root を使う（`terminal/strata_cli/cli.py:1546-1555,1713-1720`）。Node ホストはこれらの専用変数を各 CLI 子プロセスに渡す（`app/host/server/index.mjs:886-895`、`app/host/server/timeskip.mjs:313-320`）。
- Docker image は変数を `/data/state` に設定するため、コンテナ内で別値を渡さない限りその値が使われる（`tools/docker/Dockerfile:105-112`）。
- ディレクトリ作成・読み書きが必要な機能では、選ばれた場所への filesystem access が必要。`XDG_STATE_HOME` 自体に対する警告や値の拒否処理はない。

## 実行時の詳細

Python の `state_base()` は呼び出しのたびに `os.environ` から値を取得し、結果を module-level/static cache しない（`terminal/strata_control/paths.py:13-21`）。この基準パスから runtime は `runtime/` を作成し、絶対パスと private-directory 条件を確認する（`terminal/strata_control/runtime.py:128-156`）。ほかに `procs/` の launch 記録、`launch/` の実行設定、serve の marker、`net/refused-hosts.json` のような状態記録が配下に置かれる（`terminal/strata_control/procs.py:192-200`、`terminal/strata_cli/launch/runner.py:841-845`、`terminal/serve/lastrun.py:87-105`、`terminal/strata_control/netpolicy.py:214-229`）。

CLI の tuning と Time-skip は、`--state-dir`、専用環境変数、共通 `state_base()` の順で保存 root を決める。従って専用指定がある経路では `XDG_STATE_HOME` はその機能の保存場所に影響しない（`terminal/strata_cli/cli.py:1546-1555,1713-1720`）。Node ホストでは `stateRoot()` / `tuningDir()` / `timeSkipDir()` が呼ばれる時点で `env` を参照し、Time-skip の子プロセス環境はホスト初期化時に複製される（`app/host/server/platform-paths.mjs:17-32`、`app/host/server/index.mjs:958-963`）。

## ログと測定値

`XDG_STATE_HOME` の値の検証や、この変数専用のログ・警告は実装されていない。選択先での作成・読み書きが失敗した場合の扱いは各機能による。例えば runtime は指定された runtime directory が絶対パスでない場合に上記の `ProfileError` を出し、directory が private でない場合は `_not_private_message(base)` を使って失敗させる（`terminal/strata_control/runtime.py:135-156`）。性能測定値は該当なし。

## 根拠

- `terminal/strata_control/paths.py:13-21` — Python 側の OS 分岐、unset/空文字 fallback、`strata` suffix。
- `app/host/server/platform-paths.mjs:17-32` — Node 側の OS 分岐、fallback、および tuning / Time-skip の専用 override。
- `terminal/strata_control/runtime.py:128-156` — runtime directory の優先指定、絶対パス・private 条件。
- `terminal/strata_cli/cli.py:394-405,420,486-512,1546-1555,1713-1720` — CLI 引数と環境変数の優先順位。
- `app/host/server/index.mjs:886-895,954-963`、`app/host/server/timeskip.mjs:302-320,377-388` — Node ホストの保存先と子プロセスへの転送。
- `terminal/strata_control/procs.py:192-200`、`terminal/strata_cli/launch/runner.py:841-845`、`terminal/serve/lastrun.py:42-47,87-105`、`terminal/strata_control/netpolicy.py:214-229`、`app/host/server/temperature-telemetry.mjs:100-101` — 保存先を使う Strata 機能。
- `tools/docker/Dockerfile:105-112`、`tools/docker/Dockerfile.src:147-149`、`tools/docker/entrypoint.sh:44-49` — Docker 側の既定値と未使用の `STATE_DIR` 代入。
