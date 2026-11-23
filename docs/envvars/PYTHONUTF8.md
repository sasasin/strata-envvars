# `PYTHONUTF8`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata 自身が `PYTHONUTF8` を読み取って値を判定する箇所は見つからない。一方、Windows の Strata 起動スクリプトとホストアプリは、Python 子プロセス用の環境にこのキーを明示的に設定している。従って Strata 側で確認できる役割は、これらの起動経路で値 `'1'` をセットまたは転送することまでであり、Python がその値をどう解釈するかは本書の対象外である。

Windows では `START-HERE.bat` がセットアップ／起動の前に設定し、Terminal の `strata.cmd` と `strata-direct.ps1` も `strata.py` を起動する前に設定する（`START-HERE.bat:4-8`, `terminal/bin/strata.cmd:8-10,42-44`, `terminal/bin/strata-direct.ps1:55-59`）。アプリのホスト側では、ソース checkout のサーバー、Control、インストーラー、調整 CLI、Time-skip の各子プロセスに渡す環境を組み立てるときに設定する（`app/host/server/control-runtime.mjs:82-107,114-120,140-146`, `app/host/server/native-control.mjs:142,197-203,689-692,735-742`, `app/host/server/index.mjs:890-895`, `app/host/server/timeskip.mjs:313-321,457-467`）。

## 値と判定

Strata 側に入力値の parse・文字列比較・数値変換はない。子プロセス向けの環境を作る箇所では、継承元の同名値を `'1'` で上書きする。従って親プロセスで未設定、空文字、`0`、`true` などのどれであっても、明示設定を行う経路では子プロセスに渡す値は `'1'` となる。たとえば `sourceServerEnvironment` は `{ ...env, ..., PYTHONUTF8: '1' }`、Control 用環境は最後に `PYTHONUTF8: '1'` を設定する（`app/host/server/control-runtime.mjs:82-95`）。同様に各 spawn 用環境でも固定値を指定する（`app/host/server/native-control.mjs:142,201,741`, `app/host/server/index.mjs:892-894`, `app/host/server/timeskip.mjs:316-320,465-466`）。

| 経路 | 親側の unset／空文字／`0`／`true` | 子プロセスへ渡す値 | 例外・上書き |
|---|---|---|---|
| Windows 起動スクリプト | 元の値を判定しない | スクリプト内で `'1'` に設定 | 起動前に無条件で代入（`START-HERE.bat:4-6`, `terminal/bin/strata.cmd:8-10`, `terminal/bin/strata-direct.ps1:55-58`） |
| ホスト管理の通常の子プロセス | 元の値を判定しない | 組み立てた環境で `'1'` に固定 | `timeskip.startDetached` は固定値を設定した後に `extraEnv` を展開するため、呼び出し側が同名キーを渡せば上書き可能。現在の呼び出し側は `STRATA_HOST_URL` と `STRATA_INTERNAL_SECRET` のみを渡す（`app/host/server/timeskip.mjs:465-466`, `app/host/server/index.mjs:1284-1289`） |

ここでいう `true` は親環境にその文字列が設定されている例であり、Strata が真偽値として扱うことを意味しない。Strata の値域チェックや「無効値」時の fallback はない。子プロセスの env に別値を渡す `extraEnv` の例外を除き、CLI 引数との優先順位もない。

## 有効になる条件

- Windows の `START-HERE.bat`、`terminal/bin/strata.cmd`、`terminal/bin/strata-direct.ps1` 経由では、起動時に無条件で `'1'` を設定する。これらは Python を選択した後、`strata.py` の実行前に設定する（`START-HERE.bat:4-8`, `terminal/bin/strata.cmd:8-10,42-44`, `terminal/bin/strata-direct.ps1:55-59`）。
- ホストアプリのソース checkout 経路では `serve/server.py`、同梱 MCP ツール、native の調整・更新系 Python 子プロセスに設定する。packaged Control 経路は `controlEnvironment`／`installerEnvironment` を通り、同じく `'1'` になる（`app/host/server/native-control.mjs:142,197-203,689-692,735-742`, `app/host/server/control-runtime.mjs:82-119`）。
- ホストの tuning CLI と Time-skip CLI も spawn ごとに設定する。Time-skip の detached 起動だけは `extraEnv` が後勝ちだが、現行の呼び出し元は対象キーを渡していない（`app/host/server/index.mjs:890-895,1284-1289`, `app/host/server/timeskip.mjs:313-320,457-467`）。
- Strata ソース内に、OS 以外の backend、build macro、モデル状態、別環境変数または CLI 引数を条件として `PYTHONUTF8` の設定を切り替える分岐はない。これは Python 子プロセスを起動する前の環境設定であり、GPU backend の選択処理ではない。

## 実行時の詳細

この変数を読み取る値のキャッシュはない。Windows スクリプトは起動処理で代入する。ホストは各子プロセス起動時に環境オブジェクトを作り、spawn に渡す。たとえば Control CLI は `runCli` から `controlEnvironment` を経由し（`app/host/server/control-runtime.mjs:82-107,140-146`）、ソース版サーバーは起動時に `sourceServerEnvironment()` を渡す（`app/host/server/native-control.mjs:689-692`）。Tuning と Time-skip も各起動の spawn オプションに値を含める（`app/host/server/index.mjs:890-895`, `app/host/server/timeskip.mjs:313-320,457-467`）。

明示設定経路では、親から継承した値は子環境の組み立て時に置き換わる。Time-skip の detached 経路だけは先述の通り呼び出し側の `extraEnv` が後から上書きできる。起動済み子プロセスに対して後から値を読み直したり、実行中に変更を反映したりする Strata の処理はない。

## ログと測定値

`PYTHONUTF8` の値に応じた Strata 固有のログ、警告、終了コードは確認できない。子プロセスが起動できない場合や終了した場合には、ホストは通常のプロセスエラーとして処理する。ソース版サーバーは終了を instance error として記録し（`app/host/server/native-control.mjs:689-692`）、detached Time-skip は起動エラー、終了コード、stderr 等を結果に返す（`app/host/server/timeskip.mjs:471-492`）。これらの経路は `PYTHONUTF8` の値を理由として判定していない。該当する測定値はない。

## 根拠

- `START-HERE.bat:4-8` — Windows の初回セットアップ／起動前の設定。
- `terminal/bin/strata.cmd:8-10,42-44`、`terminal/bin/strata-direct.ps1:55-59` — Terminal の Windows ランチャー。
- `app/host/server/control-runtime.mjs:82-107,114-119,140-146` — source server、Control／installer 環境、および CLI 起動。
- `app/host/server/native-control.mjs:142,197-203,689-692,735-742` — tuning、MCP／installer、source server、native 操作の子プロセス。
- `app/host/server/index.mjs:890-895,1284-1289` — tuning 起動と Time-skip 呼び出し側の追加環境。
- `app/host/server/timeskip.mjs:313-321,457-492` — Time-skip 通常／detached 起動と起動失敗の返却。
