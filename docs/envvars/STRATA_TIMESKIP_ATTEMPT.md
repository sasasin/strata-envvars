# `STRATA_TIMESKIP_ATTEMPT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Time-skip の revision 子プロセスへ、現在の試行番号を渡す環境変数です。`strata timeskip run` が revision callback を呼ぶたび、1 始まりのループ番号を10進文字列にして設定します。CLI 自身がこの変数を設定値として読むわけではありません。`--revise-command` がなければ callback は `None` を返して revision を行わず、子プロセスも起動しません。

主な読み取り先は同梱の Python bridge `integrations/harness/revise_once.py` と、アプリ内蔵の Node bridge `apps/host/server/timeskip-revise.mjs` です。どちらも revision command として使われる場合の受け渡し用で、推論エンジンの設定ではありません。

## 値と判定

| 箇所 | 未設定時 | 設定時の扱い |
|---|---|---|
| `strata_cli/cli.py` の revision callback | 親プロセスの値にかかわらず、試行ごとにループ番号を設定 | `str(attempt)` で上書き。整数を1始まりで渡す |
| `integrations/harness/revise_once.py` | `"1"` | `os.environ.get` で文字列をそのまま取得。数値変換、範囲検査、空文字の置換はしない |
| `apps/host/server/timeskip-revise.mjs` | `Number(undefined ?? 1)` により `1` | `Number(...)` で数値化。空文字は `0`、数値でない文字列は `NaN` になる。値域検査や clamp はない |

通常の CLI 実行では callback が環境を複製した上で `STRATA_TIMESKIP_ATTEMPT` を上書きするため、呼び出し元が同名変数を設定していてもその値は使われません。Python bridge を単独起動した場合は、未設定なら `"1"`、空文字なら空文字が `attempt` に入ります。Node bridge を単独起動した場合は、未設定なら `1`、空文字なら `0` です。Node の `NaN` は `JSON.stringify` により内部 API の JSON body では `null` になります。

## 有効になる条件

- `strata timeskip run` の revision callback が実行されること。試行回数は CLI の `--attempts` に従い、`strata_control/time_skip.py` が `range(1, max_attempts + 1)` で試行番号を生成します。
- CLI では `--revise-command` が指定されていること。App Host 経由では `useAgent: false` でなく、App Host が選んだ revision command（既定は `timeskip-revise.mjs`）が起動されること。別環境変数 `STRATA_TIMESKIP_REVISE` はこの command 自体を上書きします。
- callback は親環境を引き継いでから prompt と attempt を設定するため、この変数は各 callback について試行番号で必ず上書きされます。

Node bridge は変数を `attempt` として `/api/internal/timeskip-revise` に送ります。しかし現行 handler は body の `cwd` と `prompt` を使って処理し、`body.attempt` を参照しません。したがってこの Node 経路では、環境値の変換結果は JSON の `attempt` 欄まで届きますが、handler 側の revision 挙動には使われていません。

## 実行時の詳細

CLI の callback は `env = {**os.environ, ...}` で子プロセス用の環境を作り、`STRATA_TIMESKIP_ATTEMPT` に現在の整数 index を文字列化してセットしてから revision command を起動します。子プロセスの非ゼロ終了は `TimeSkipError` になり、run の失敗記録へ進みます。成功時は stdout の末尾部分が attempt の note として記録されます。

Python bridge はこの値を tempfile の prefix（`strata-revise-a{attempt}-`）と Harness の request ID（`timeskip-{attempt}`）に埋め込みます。環境の値を後から読み直す cache はありません。CLI が各子プロセスの起動直前にセットし、bridge はプロセス起動後 `main()` 内で一度取得します。

Node bridge は値を数値化し、内部 API の JSON body に含めます。`STRATA_HOST_URL`、`STRATA_INTERNAL_SECRET`、prompt のいずれかが空/未設定なら、stderr に `The revision step needs the Strata app to be running.` を出して終了コード 2 です。fetch/API の失敗などは stderr にエラーを出して終了コード 1 になります。現在の API handler は受け取った `attempt` を使わず、assistant turn は `cwd` と `prompt` を使って開始します。

## 根拠

- 対象名の全参照は `strata_cli/cli.py:363,1572-1583`、`integrations/harness/revise_once.py:16,70-89,102-105,129-136`、`apps/host/server/timeskip-revise.mjs:14-28`、および説明文書 `docs/work/IMPLEMENTATION_STATUS.md:371-373` にあります。実際の読み取りは Python の `:86` と Node の `:17`、CLI からの値の注入は `strata_cli/cli.py:1572-1578` です。
- 試行番号が1始まりで生成される箇所: `strata_control/time_skip.py:442-449`。
- CLI の revision command がない場合の扱いと、試行回数引数: `strata_cli/cli.py:352-365,1570-1585`。
- App Host が revision command を選択し、attempts を CLI に渡す箇所: `apps/host/server/index.mjs:777-778,1152-1165`。
- Python bridge 内の一時領域名と request ID: `integrations/harness/revise_once.py:102-105,129-136`。
- Node bridge の内部 API 呼び出し・数値の送信・終了経路: `apps/host/server/timeskip-revise.mjs:14-33,35-56`。handler は `apps/host/server/index.mjs:1194-1228` で `cwd` と `prompt` を使い、`attempt` を参照しません。
- 関連資料 `docs/work/IMPLEMENTATION_STATUS.md:361-373` は Python bridge の契約を説明しており、ソースの受け渡し方法と一致します。`000_envvers.md:1574` に候補として掲載されていますが、この調査では上記の Strata 所有コードに実際の環境読み取りを確認しました。

