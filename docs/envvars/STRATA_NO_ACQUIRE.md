# `STRATA_NO_ACQUIRE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

プロセス内の Strata がダウンロード、インストール、コンパイルなどの取得処理を開始してよいかを制限する。Python 側の `strata_control.acquisition` は `STRATA_NO_ACQUIRE` が有効なら取得前の `require()` で `AcquisitionRefused` を送出する。ホスト側も同じ判定を使い、engine や cloudflared の取得処理を拒否する。これは外部ライブラリや GPU driver の環境変数ではない（`terminal/strata_control/acquisition.py:53-73`, `app/host/server/acquisition.mjs:24-31`）。

この変数だけで全経路を一律に決めるわけではない。デスクトップ host は Tauri が常に `1` を設定し、host が起動する Control も既定で `1` にする。ユーザーが明示的に開始した取得処理では、その子プロセスの環境から変数を除く。一方 host の packaged mode は、変数が無効でも host 側の取得を拒否する（`app/desktop/src-tauri/src/main.rs:269-274`, `app/host/server/control-runtime.mjs:88-107`, `app/host/server/acquisition.mjs:24-31`）。

## 値と判定

| 判定箇所 | unset / 空文字 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Python Control・setup の共通取得ガード | 空文字相当となり無効 | trim 後、小文字化した `1`, `true`, `yes`, `on` | `0`, `false`, `no`, 空文字、空白だけ、その他の文字列 |
| Node host | unset / `null` / 空文字は無効 | trim 後、小文字化した `1`, `true`, `yes`, `on` | `0`, `false`, `no`, 空文字、空白だけ、その他の文字列 |
| host の packaged 判定 | `STRATA_PACKAGED` が文字列 `1` でなければ無効 | `STRATA_PACKAGED=1` | それ以外 |
| `setup.py` の Inkling tokenizer 公開 HF fallback 判定 | 取得を試みる側 | この分岐では値が厳密に文字列 `1` のとき fallback をスキップ | unset、空文字、`true` 等は分岐上は fallback を試みる |

Python 共通判定は `os.environ.get(ENV, "").strip().lower()` の完全一致で、数値変換はしない。Node 側も `String(...).trim().toLowerCase()` の後に同じ4語を完全一致で調べる。したがって大文字小文字と前後の空白は無視されるが、値の部分一致や `1anything` は受理しない（`terminal/strata_control/acquisition.py:26,53-55`, `app/host/server/acquisition.mjs:12,24-25`）。

setup の tokenizer fallback は別の厳密比較 `os.environ.get("STRATA_NO_ACQUIRE") != "1"` を行う。値が `true` の場合、この分岐自体は fallback を試みるが、`inkling_fetch()` が取得ガードに達すると共通判定で拒否される。この比較だけを共通ガードの値規則と混同しないこと（`terminal/setup.py:10733-10750`, `terminal/strata_control/acquisition.py:53-73`）。

## 有効になる条件

- Python の `acquisition.require()` を通る取得処理で、共通判定が有効なときに拒否される。対象には setup のネットワーク要求・install/build 実行、Control の component・picture・drafting ダウンロード、更新処理が含まれる（`terminal/setup.py:1095-1100,1131-1139`, `terminal/strata_control/components.py:530`, `terminal/strata_control/pictures.py:377,467`, `terminal/strata_control/drafting_fetch.py:310,388`, `terminal/strata_control/updater.py:438-440`）。
- `strata start` は CLI 内の `acquisition.forbidden()` コンテキストでも取得を禁止する。管理 runtime が起動する `serve.server` 子プロセスには、親環境の値によらず `STRATA_NO_ACQUIRE=1` を設定する（`terminal/setup.py:8558-8563`, `terminal/strata_control/runtime.py:1056-1074`）。
- Node host では変数が有効、または `STRATA_PACKAGED=1` のどちらかで取得を拒否する。後者は変数の値が unset、空、`0` 等でも有効（`app/host/server/acquisition.mjs:24-30`）。
- デスクトップ Tauri shell は host 起動コマンドに `STRATA_NO_ACQUIRE=1` を設定する。host から起動する Control も `controlEnvironment()` が `1` に設定する（`app/desktop/src-tauri/src/main.rs:269-274`, `app/host/server/control-runtime.mjs:88-100`）。
- 明示的な取得操作は例外経路である。Control の `acquire: true` 呼び出しではその Control 子プロセスから変数を削除し、`strata launch` の runner も子プロセス環境から削除する。`strata_mcp.py` の明示的な install job も setup 子プロセスから削除する（`app/host/server/control-runtime.mjs:101-105,140-146,277-300`, `terminal/strata_cli/launch/runner.py:1033-1043`, `terminal/tools/strata_mcp.py:3151-3163`）。
- `setup.py` が取得可能な状態でも、CONTROL mode は実行可能な bundled preparation tools を制限する。変数の削除だけで任意の installer/build が許されるわけではない（`terminal/setup.py:1131-1140`）。
- 環境変数または禁止コンテキストが有効なとき、setup の feed model 一覧取得と launch monitor の日次更新確認は取得を試みず、通常の setup 表示や launch に進む。`setup.py` は `acquisition.is_forbidden()` を見て feed fetch を省略し、日次確認は `None` を返して thread を作らない（`terminal/setup.py:9677-9691`, `terminal/strata_control/engine_update.py:109-115`）。

## 実行時の詳細

Python の `is_forbidden()` は呼び出しごとに環境を読み直し、プロセス内の禁止コンテキスト深度 `_depth` も併せて判定する。値を module-level に cache しないため、同一プロセスで環境が変更された後の次の判定には新しい値が使われる。`forbidden()` の深度は lock で増減し、ネスト可能（`terminal/strata_control/acquisition.py:28-30,53-73`）。

setup の一部処理は `is_forbidden()` を使って任意の feed 取得や日次更新確認を静かに省略する。一方、実際の取得 primitive は `require()` を呼び、禁止されていれば例外にする。setup の `get_ready_made_engine()` は `require()` の後にだけ子プロセス用環境から変数を除くため、親 setup が禁止状態ならこの削除によって拒否を回避できない（`terminal/setup.py:5366-5377,9677-9689`, `terminal/strata_control/engine_update.py:109-130`）。

Node host の `forbidden()` も呼び出しごとに渡された環境（既定は `process.env`）を読み、値を cache しない。`/api/health` の応答には `acquisition.forbidden()` の結果と `STRATA_NO_ACQUIRE` の生値（未設定なら `null`）を載せる（`app/host/server/acquisition.mjs:24-25`, `app/host/server/index.mjs:1427-1436`）。

取得を拒否された Python 処理は `AcquisitionRefused` を送出する。`main_guard()` を使う入口では `strata: {理由}` を stderr に出して終了コード 5 を返し、`strata update` も拒否時に `fail(..., 5)` へ変換する。update の文面には `(the update is the one explicit step that downloads; run it from a shell where STRATA_NO_ACQUIRE is not set)` が付く（`terminal/strata_control/acquisition.py:32-43,76-84`, `terminal/strata_cli/update_cmd.py:383-390`）。

Node 側の拒否は `AcquisitionRefused` error（code `acquisition_refused`, status `409`）となる（`app/host/server/acquisition.mjs:14-21,28-31`）。

デスクトップ Control の update check / update / drafting fetch / picture fetch は明示取得として `acquire: true` で子プロセスを起動し、その子だけ変数を外す。通常の Control 呼び出しは `1` を維持する（`app/host/server/control-runtime.mjs:88-107,140-146,277-300,401-429`）。また `strata launch` は実行環境から変数を削除し、明示 launch のための downloader が利用できるようにする（`terminal/strata_cli/launch/runner.py:1033-1043`）。

## ログと測定値

Python の拒否理由は `AcquisitionRefused` の文面 `"{what} is missing or out of date. Starting and serving never install or download anything. Run: {command}"`。標準の `main_guard()` では先頭に `strata: ` を付けて stderr に出し、終了コードは `5`（`terminal/strata_control/acquisition.py:32-43,76-84`）。更新コマンドはこれを `fail(..., 5)` に渡す（`terminal/strata_cli/update_cmd.py:387-388`）。

host 側の拒否メッセージは `"{what} is not installed here, and the app never downloads it while it runs. Install it from {command}."` で、error code は `acquisition_refused`、HTTP status は `409`（`app/host/server/acquisition.mjs:14-21,28-31`）。この変数について Strata ソースに性能測定値はない。

## 根拠

- `terminal/strata_control/acquisition.py:26-84` — Python 共通判定、禁止コンテキスト、拒否例外と標準終了経路。
- `app/host/server/acquisition.mjs:12-31` — host の値規則、packaged 条件、拒否例外。
- `app/desktop/src-tauri/src/main.rs:269-274`、`app/host/server/control-runtime.mjs:88-107,140-146` — host / Control 子プロセスへの設定と明示取得時の削除。
- `terminal/setup.py:1095-1100,1131-1140,5366-5383,8558-8563,10733-10750` — setup の共通取得ガード、ready-made engine の子プロセス環境、start 禁止コンテキスト、tokenizer fallback の厳密比較。
- `terminal/strata_control/runtime.py:1056-1074`、`terminal/strata_cli/launch/runner.py:1033-1043`、`terminal/tools/strata_mcp.py:3151-3163` — managed server と明示 launch/install の子プロセス環境。
- `terminal/strata_control/components.py:530`、`terminal/strata_control/pictures.py:377,467`、`terminal/strata_control/drafting_fetch.py:310,388`、`terminal/strata_control/updater.py:438-440` — 共通ガードを呼ぶ取得処理。
- `terminal/strata_cli/update_cmd.py:355,383-390`、`app/host/server/index.mjs:1427-1436` — CLI の拒否結果と health API の観測値。

