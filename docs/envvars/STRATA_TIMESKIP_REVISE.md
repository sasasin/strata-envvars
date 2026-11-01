# `STRATA_TIMESKIP_REVISE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata ホストの従来型（`legacy: true`）Time-skip が revision を試すときに使うコマンド文字列を指定します。ホストは起動時にこの値を読み、`strata timeskip run` の `--revise-command` 引数として渡します。新しい agent 経路（`legacy !== true`）はこの値を使わず、`body.useAgent === false` の従来型要求も revision command を渡しません（`apps/host/server/index.mjs:777-778,1132-1152,1160-1165`）。

## 値と判定

| 環境値 | ホストで選ばれる値 | 結果 |
|---|---|---|
| 未設定 | `"${process.execPath}" "${REVISE_NODE_SCRIPT}"` | Node の実行ファイルでアプリ内 `timeskip-revise.mjs` を起動する既定コマンド |
| 空文字 | 空文字 | 既定値には置き換わらない。ただし後段の truthiness 判定で `--revise-command` を追加しないため、revision command なしで実行される |
| 空でない任意の文字列 | その文字列 | trim、文字種検査、パス確認、コマンド形式の検証をせず `--revise-command` の値にする |

読み取りは JavaScript の nullish coalescing（`??`）なので、既定値になるのは未設定（`undefined`）の場合だけです。空文字や空白だけの値は未設定と同じ扱いではありません。後段の `if (reviseCommand)` は空文字だけを除外し、`"0"`、`"false"`、空白を含む文字列などは引数に追加します（`apps/host/server/index.mjs:777-778`; `apps/host/server/timeskip.mjs:446-455`）。

## 有効になる条件

- ホストサーバーの `apps/host/server/index.mjs` がこの値をモジュール初期化時に読みます。起動後にプロセス環境を変更しても、モジュール定数 `TIMESKIP_REVISE` は再評価されません（`apps/host/server/index.mjs:777-778`）。
- `/api/timeskip/start` の要求が `legacy: true` の経路に入る必要があります。`legacy !== true` は `forkTs.start(...)` を呼び、対象変数を参照しません（`apps/host/server/index.mjs:1132-1152`）。
- 従来型経路でも `body.useAgent === false` なら `reviseCommand` は `null` となり、環境変数の値は使われません（`apps/host/server/index.mjs:1152`）。
- revision 回数が 0 の場合、コマンドが選択されていても revision は実行されません。ホストは要求の `attempts` を渡し、CLI が 0〜10 に clamp します（`apps/host/server/index.mjs:1160-1164`; `apps/host/server/timeskip.mjs:451-453`; `strata_control/time_skip.py:329,442-448`）。

## 実行時の詳細

従来型要求ではホストが選んだ文字列を `reviseCommand` に入れて `timeskip.startDetached()` へ渡します。空でない場合、同関数は `--revise-command` と文字列を CLI 引数へ追加し、Python の `strata.py timeskip run` を起動します（`apps/host/server/index.mjs:1152,1160-1165`; `apps/host/server/timeskip.mjs:446-455`）。この環境変数の読み取りや文字列の検査をする別の本番箇所はありません。

CLI の `--revise-command` は任意引数です。各 revision attempt で値が truthy なら、Strata は `subprocess.run(..., shell=True, cwd=candidate, env=env, capture_output=True, ...)` にその文字列を渡します。`env` は既存環境を引き継ぎ、`STRATA_TIMESKIP_PROMPT` と `STRATA_TIMESKIP_ATTEMPT` を上書き追加します（`strata_cli/cli.py:359-365,1572-1585`）。未指定なら revision 関数は `None` を返し、実行結果は「revision を試さない」経路です。既定の Node helper は `apps/host/server/timeskip-revise.mjs` です（`apps/host/server/index.mjs:774-778`; `strata_cli/cli.py:1572-1577`）。

コマンドの終了コードが 0 以外なら、Strata は stderr、stderr が空なら stdout の末尾最大 300 文字を含む `the revision command failed (exit N): ...` を失敗理由にします。Time-skip run は例外を `failed` 状態と `error` に記録します（`strata_cli/cli.py:1577-1583`; `strata_control/time_skip.py:480-493`）。detached 起動時に run record が作られず CLI が終了した場合、ホストは JSON のエラー、stderr、stdout などから理由を取り出し、HTTP 400（code 2）または 502 で返します。起動から20秒以内に run が始まらない場合は timeout として扱います（`apps/host/server/timeskip.mjs:464-481`; `apps/host/server/index.mjs:1166`）。

## 根拠

- `apps/host/server/index.mjs:777-778` — 環境値の唯一の直接読み取りと、未設定時の Node helper 既定値。
- `apps/host/server/index.mjs:1132-1152,1160-1166` — legacy / agent 経路の分岐、`useAgent` の抑止、CLI 起動への値の受け渡しと起動エラー応答。
- `apps/host/server/timeskip.mjs:446-481` — 空文字での引数省略、CLI 起動、子プロセスの環境、起動失敗・timeout の処理。
- `strata_cli/cli.py:359-365,1572-1589` — CLI 引数の定義、revision command の起動と失敗処理。
- `strata_control/time_skip.py:329,422-493` — attempt 回数の下限処理、revision の反復、失敗時の記録。
- `rg -n -S --hidden --glob '!.git/**' 'STRATA_TIMESKIP_REVISE|TIMESKIP_REVISE'` による全参照確認では、本番コードの参照は `apps/host/server/index.mjs:777,1152` の2箇所です。索引 `docs/envvars/000_envvers.md:1578` に候補名があります。
