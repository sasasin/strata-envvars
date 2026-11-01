# `STRATA_NO_ACQUIRE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

Strata のセットアップ、Control/CLI、desktop host が、明示された install/update 以外の実行中に取得（ダウンロード、インストール、ビルドなど）を始めないための禁止スイッチです。Python 側は取得を行う primitive の直前で共通 guard を呼び、host 側は engine と cloudflared の取得入口で guard を呼びます。変数は GPU backend やモデル計算を制御しません。

## 値と判定

通常の取得 guard は値全体の文字列を trim し、小文字化してから次の集合と比較します。数値変換や先頭文字だけの判定ではありません。

| 読み取り側 | unset / 空文字 | 禁止になる値 | 禁止にならない値 |
|---|---|---|---|
| Python Control / setup / CLI | 禁止しない | `1`, `true`, `yes`, `on`（前後空白を除去し、大文字小文字を無視） | 上記以外。例: `0`, `false`, `no`, `2`, ` true x ` |
| desktop host (Node.js) | 禁止しない | `1`, `true`, `yes`, `on`（前後空白を除去し、小文字化） | 上記以外。例: `0`, `false`, `no`, `2` |
| staged Control の旧 launcher 判定 | 条件不成立 | この分岐では値が厳密に `1` の場合だけ追加判定へ進む | `01`, `true`, 空文字、前後空白付き `1` など |

Node.js host では、別変数 `STRATA_PACKAGED` が厳密に `1` の場合も acquisition を禁止します。この条件は `STRATA_NO_ACQUIRE` が未設定または `0` でも有効です。Python の staged Control 判定では、厳密な `STRATA_NO_ACQUIRE=1` に加えて `STRATA_HANDOVER` が未設定であることなども必要です（下記）。

## 有効になる条件

- Python の `acquisition.require()` を通る取得処理では、環境値が禁止値なら `AcquisitionRefused` を送出します。`setup.py` の HTTP ダウンロード、インストール/ビルド実行、各種 engine の取得・ビルドなどがこの guard を呼びます（`setup.py:947-962,3008-3016,4543-4557,5660-5666`、Control の取得処理は `strata_control/components.py:532`、`strata_control/updater.py:349`、`strata_control/drafting_fetch.py:63`）。
- `setup.py start()` は値にかかわらず `acquisition.forbidden()` の範囲内で起動処理を行います。したがって、開始処理中に取得 guard に到達した場合は環境変数が未設定でも拒否されます（`setup.py:7110-7115`）。
- desktop host は engine の release 確認・install と cloudflared の install 前に `requireAcquisition()` を呼びます（`apps/host/server/engine-install.mjs:68-88`、`apps/host/server/cloudflared-install.mjs:46-55`）。開発実行でも `STRATA_NO_ACQUIRE` は評価され、パッケージ版ではさらに `STRATA_PACKAGED=1` が禁止条件になります（`apps/host/server/acquisition.mjs:24-30`）。
- Tauri shell は起動する host に `STRATA_NO_ACQUIRE=1` を設定します（`apps/desktop/src-tauri/src/main.rs:230-235,461-482`）。host が Control を起動するときも、ユーザー環境をコピーした後に同じ値で上書きします。通常の Control 子プロセスは値を保持し、明示 update の呼び出しだけ `acquire: true` により削除します（`apps/host/server/control-runtime.mjs:88-103,124-130,180-195`）。
- Control が管理サーバーを起動するときは、親環境をコピーした上で子サーバーの環境に `STRATA_NO_ACQUIRE=1` を設定します（`strata_control/runtime.py:859-875`）。
- 例外的な明示操作は起動元が子プロセス用環境から値を外します。CLI `launch` は継承環境から削除します（`strata_cli/launch/runner.py:674-684`）。host の明示 `strata update` は Control の環境で削除し、アプリのモデル install job は `tools/strata_mcp.py` に渡す setup 用環境から削除します（`apps/host/server/control-runtime.mjs:101-103,180-195`、`tools/strata_mcp.py:2841-2852`）。この install job の setup は `STRATA_CONTROL_INSTALL` モードで、一般の pip/git/compiler/engine fetch を許可するという意味ではありません（`setup.py:959-967`）。

## 実行時の詳細

Python の `is_forbidden()` は呼び出されるたびに `_depth` と `os.environ.get("STRATA_NO_ACQUIRE", "")` を評価します。値を static cache しません。`forbidden()` はネスト可能な範囲カウンターを増減し、環境値が許可でも、その範囲内では取得を禁止します（`strata_control/acquisition.py:28-29,53-73`）。host の `forbidden(env = process.env)` も呼び出し時に値を判定し、結果を cache しません（`apps/host/server/acquisition.mjs:12,24-30`）。

禁止された取得は処理を始めず、Python では `AcquisitionRefused`（`code="acquisition_refused"`, `exit_code=5`）になります。`setup.py` のトップレベル起動は `[X]` と例外メッセージを表示して終了コード 5 を返します（`strata_control/acquisition.py:32-43,70-84`、`setup.py:10493-10498`）。`strata update` も拒否を CLI の失敗応答、終了コード 5 に変換します（`strata_cli/update_cmd.py:229,257-265`）。エラーには不足した対象と、SETUP/UPDATE/`strata install` など明示コマンドが含まれます（`strata_control/acquisition.py:38-50`）。

desktop host の拒否は `AcquisitionRefused` エラーで、`code` は `acquisition_refused`、HTTP status は 409 です。エラーメッセージは対象ソフトウェアがないことと Terminal の `strata install` 案内を含みます（`apps/host/server/acquisition.mjs:14-20,28-30`）。Control status API は、現在の `STRATA_NO_ACQUIRE` 値（未設定なら `null`）と、共通判定による `acquisition.forbidden` を返します（`apps/host/server/index.mjs:1292-1303`）。

加えて `strata_cli/handover.py` の `refuse_old_updater()` は、引数が `--version` のみ、環境値が厳密に `1`、`STRATA_HANDOVER` が未設定で、Control が stage folder 配下にある場合に旧 launcher と判定します。そのとき stdout に `This Terminal cannot switch to the new Control by itself. Run the Strata install command once more to update it.` を出し、終了コード 7 を返します。この特殊経路の文字列判定は、通常の取得禁止 guard と異なります（`strata_cli/handover.py:174-187`）。

## 根拠

- Python の共通判定と拒否例外: `strata_control/acquisition.py:26-29,32-73`
- host の値判定と拒否エラー: `apps/host/server/acquisition.mjs:12-30`
- desktop shell から host への設定: `apps/desktop/src-tauri/src/main.rs:230-235,461-482`
- Control 子プロセスの設定と明示 update の例外: `apps/host/server/control-runtime.mjs:88-103,124-130,180-195`
- Python 管理サーバー子プロセスへの設定: `strata_control/runtime.py:859-875`
- staged Control の完全一致判定: `strata_cli/handover.py:174-187`
