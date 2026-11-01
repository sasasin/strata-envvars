# `STRATA_RUNTIME_DIR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の作業ツリーは `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されなかった。

## 役割

Strata Control の管理 runtime が使う状態ディレクトリを指定します。保存 profile ごとの owner state JSON、制御 endpoint、host log、child marker、ready file、rollback snapshot などがこのディレクトリを基準に置かれます。管理 runtime の共有 activity lock と `strata serve` の server log も同じ場所を使います。GPU backend や推論計算を設定する変数ではありません。

実際に値を読む中心箇所は `strata_control/runtime.py` の `runtime_dir()` です。この関数は、対象環境をサポートする OS かを先に確認し、`os.environ.get("STRATA_RUNTIME_DIR")` から値を読みます（`strata_control/runtime.py:81-92,101-129`）。

## 値と判定

| 環境変数の状態 | 使用するパス |
|---|---|
| 未設定 | OS ごとの既定 state base の下の `runtime` |
| 設定値が空文字 | `if override` が偽になるため、未設定と同じ既定パス |
| 空でない値 | `Path(value).expanduser()` の結果。`~` 展開後に絶対パスでなければ拒否 |

空白の trim、環境変数値の数値・真偽値 parse、相対パスの絶対化はありません。空白だけの値も非空値として扱い、相対パスなら `STRATA_RUNTIME_DIR must be absolute` の `ProfileError` になります。値は存在しない場合に作成されます（親も作成）。根拠: `strata_control/runtime.py:101-111`。

既定パスは Windows では `%LOCALAPPDATA%\Strata\runtime`（`LOCALAPPDATA` 未設定または空なら `~/AppData/Local/Strata/runtime`）、POSIX では `$XDG_STATE_HOME/strata/runtime`（`XDG_STATE_HOME` 未設定または空なら `~/.local/state/strata/runtime`）です。`STRATA_RUNTIME_DIR` が非空ならこれらより優先されます。CLI 引数や profile 設定による別の directory override は、この `runtime_dir()` の実装にはありません。根拠: `strata_control/paths.py:13-21`、`strata_control/runtime.py:103-111`。

作成・検査の条件もあります。POSIX では新規 directory を mode `0700` で作り、既存 directory を自動で chmod せず、最終的に directory で owner-only であることを検査します。Windows では ACL 対応 volume の directory にユーザー限定 ACL を設定・修復し、なお private でなければ失敗します。FAT/exFAT のように ACL がない volume では `[strata] ... is on a drive that has no file permissions ...` を stderr に一度出して、その directory を返します。根拠: `strata_control/private_files.py:320-346`、`strata_control/runtime.py:110-129,132-153`。

## 有効になる条件

- 管理 runtime の状態ディレクトリとして使うのは、Windows または Unix domain socket を持つ POSIX 上です。それ以外では `_supported()` が `managed runtime has no qualified local control transport on this platform` を返します（`strata_control/runtime.py:81-92`）。
- `runtime start` は呼び出し側で `_paths()` を使い host log 等を決め、別プロセスの runtime host を起動します。host は自身の環境からも `_paths()` と activity lease の directory を解決します。`subprocess.Popen` に `env` を渡していないため、Python の既定動作で起動元環境を継承します。`runtime_dir()` に static cache はなく、各呼び出しで環境を読み直します（`strata_control/runtime.py:205-212,521-585,746-756,1269-1271`）。通常の CLI は環境値を変えませんが、同一 Python プロセス内で `os.environ` が変更された場合は、後続呼び出しが別のパスを解決し得ます。
- Windows の `repair-access` および起動時の既知 root 修復では、この名前も helper の key tuple に含まれます。`user_roots()` は値を使って「ユーザー自身の data root」内かを判定し、`known_roots()` は存在する root を修復対象として列挙します。したがって、この変数は Windows の修復範囲にも影響します。これらの helper は `os.environ.get(key)` で動的に読みます（`strata_control/private_files.py:418-433,436-453,509-527,530-575`; CLI 呼び出し `strata_cli/cli.py:2103-2110`）。
- Desktop host の diagnostics 保存 API は `process.env.STRATA_RUNTIME_DIR ?? fallback` で `.server.log` を探します。これは Python runtime directory resolver とは別の読取箇所です。この JS 側では空文字は fallback にならず、読取失敗は空の catch で無視されます（`apps/host/server/index.mjs:1014-1024`）。

## 実行時の詳細

`runtime_dir()` が返す directory は、`_paths()` で `<profile>.json` の owner state、OS ごとの socket/address、`<profile>.host.log` に使われます（`strata_control/runtime.py:205-212`）。activity lease は `.activity.lock` として作られます（同 `:173-188`）。child marker や rollback/ready file も `runtime_dir()` を再度呼び出して配置・検査されます（同 `:238-240,327-332,364-371`）。`runtime.start` の host log open や owner host の起動は同 `:521-585`、owner host の state path 初期化と activity lease 取得は同 `:746-756,1269-1271` にあります。

directory が相対パス、非 directory、owner-only でない（対応する Windows ACL 条件を含む）などで `runtime_dir()` が `ProfileError` または filesystem error を出すと、runtime host entry point は stderr に `[strata runtime] host failed: <型>: <内容>` を出し exit code `6` で終了します（`strata_control/runtime.py:1364-1386`）。呼び出し側の `runtime.start()` では host が state file を作る前に終了した場合、`runtime host failed to start; inspect <host log path>` を `ProfileError` として返します（同 `:579-585`）。`strata serve` の起動失敗時に使う server-log path の取得は best effort で、`runtime_dir()` の例外を握りつぶして `None` にします（`strata_cli/launch/runner.py:1839-1844`）。

`docs/TERMINAL.md:94` も runtime のログと state を `XDG_STATE_HOME` 配下または `STRATA_RUNTIME_DIR` に置くと説明しています。現行コードでは Windows の ACL 非対応 volume に対する警告・例外経路もあるため、権限の挙動は上記実装に基づいて記しました。

## 根拠

- 中心の値読取、既定値、絶対パス条件、directory 検査: `strata_control/runtime.py:81-129`
- OS ごとの state base: `strata_control/paths.py:13-21`
- private directory の作成: `strata_control/private_files.py:320-346`
- 状態・socket・host log 等のパス、activity lease、管理 host 起動: `strata_control/runtime.py:173-212,238-240,327-371,521-585,746-756,1269-1271`
- Windows の動的 root helper と修復経路: `strata_control/private_files.py:418-453,509-575`; `strata_cli/cli.py:2103-2110`
- Desktop diagnostics の別読取: `apps/host/server/index.mjs:1014-1024`
- 既存設計説明との照合: `docs/TERMINAL.md:94`
