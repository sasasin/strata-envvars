# `STRATA_PORT_NOTICE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

desktop shell が、希望した loopback port を使えず別 port で App Host を起動した事実を host と UI に伝えるプロセス間通知です。Rust shell が port を選んだ後に host 子プロセスへ値を渡し、host は `/api/shell` の応答に解析結果を含めます。UI は通常の競合と `strata launch` の model server による競合を別の警告トーストで表示します。この変数自体は port 選択・bind・モデル動作を制御しません（`app/desktop/src-tauri/src/main.rs:299-314,522-545`、`app/host/server/index.mjs:153-163,2216-2218`、`app/host/src/lib/store.ts:641-647`）。

## 値と判定

host の `parsePortNotice` は `process.env.STRATA_PORT_NOTICE` を文字列として正規表現 `^busy:(\d{1,5}):(\d{1,5})(:terminal)?$` に照合します。完全一致が必要で、trim・大小文字変換・port 範囲検査はしません。数字部分は `Number` に変換されます（`app/host/server/shell-prefs.mjs:59-64`）。

| host が受け取る値 | 判定と結果 |
|---|---|
| 未設定または空文字 | `null`。通知なし。未設定は `String(value ?? '')` により空文字として照合されます。 |
| `busy:<1〜5桁>:<1〜5桁>` | 受理。`wanted` と `used` を数値にした通知オブジェクトを返します。例: `busy:47831:51234`。 |
| `busy:<1〜5桁>:<1〜5桁>:terminal` | 受理。上記に `terminal: true` が加わります。例: `busy:8080:51234:terminal`。 |
| その他 | `null`。例: `busy:47831:`、` busy:47831:51234`、`BUSY:47831:51234`、`busy:123456:2`、`busy:1:2:other`。 |

正規表現上は `busy:00000:99999` も受理されます。host 側では値域を検証しません。desktop shell が生成する値は `u16` port から作られ、希望 port は設定ファイルで `0`（既定 port を使う）または `1024..65535` に制限されます（`app/desktop/src-tauri/src/main.rs:299-314`、`app/desktop/src-tauri/src/shell.rs:55-63`、`app/desktop/src-tauri/src/identity.rs:53-56`）。

## 有効になる条件

- desktop shell の起動経路で port を選び、希望 port が bind できなかった場合に shell が通知を生成します。通常は設定済み port、未指定なら `47831` が希望 port です。空いていれば通知は生成されず、希望 port を使います（`app/desktop/src-tauri/src/main.rs:289-314`、`app/desktop/src-tauri/src/shell.rs:55-63`）。
- 競合先への health 確認が `ModelServer` と判定された場合だけ末尾に `:terminal` が付き、それ以外の競合は通常形式です（`app/desktop/src-tauri/src/main.rs:308-313`）。
- Linux supervisor と非 Linux desktop のどちらも `pick_stable_port` と `host_command` を通ります（`app/desktop/src-tauri/src/supervisor.rs:503-527`、`app/desktop/src-tauri/src/main.rs:554-564`）。backend、build macro、モデルのロード状態による追加条件は、この通知の読み取り・表示経路にはありません。
- Strata の CLI や engine がこの変数を設定として読む箇所はありません。host を desktop shell の外から直接起動する場合、shell が通知を渡す経路はありません。host に値が届かなければ通知は `null` です（`app/desktop/src-tauri/src/main.rs:543-545`、`app/host/server/index.mjs:162`）。
- host 起動元の環境に同名変数があれば、shell が検出した通知を `cmd.env` で設定する分岐があるのは通知ありの場合だけです。通知なし時にこの名前を明示的に削除する処理はありません（`app/desktop/src-tauri/src/main.rs:522-545`）。そのため有効な値が別経路から host に渡れば、host は同じ形式で解釈して表示できます。

## 実行時の詳細

起動ごとに `pick_stable_port` が shell 設定の希望 port を bind し、失敗時は空き loopback port を選びます。競合相手が Strata model server かを調べて通知文字列を `PORT_NOTICE` に保存し、`host_command` が値を設定して Node host を起動します（`app/desktop/src-tauri/src/main.rs:299-314,522-545`、`app/desktop/src-tauri/src/shell.rs:55-63`、`app/desktop/src-tauri/src/identity.rs:53-56`）。

host は `/api/shell` の GET ごとに `shellState()` を作り、その中で `process.env.STRATA_PORT_NOTICE` を解析します。POST `/api/shell/prefs` の応答でも同じ `shellState()` が呼ばれます。環境変数の解析結果を cache する処理はありません（`app/host/server/index.mjs:153-163,2216-2222`）。UI は接続状態を初期化した際に `announcePortNotice()` を一度呼び、通常の競合なら「Strata could not use its port」、Terminal の model server なら「A model is already running from the Terminal」の警告トーストを出します。通知が `null` のときはトーストを出しません。host 起動後の環境変更をアプリが行う経路は確認できません（`app/host/src/lib/store.ts:637-647,1091`）。

## ログと測定値

この変数の処理は host の API 応答と UI の警告トーストに現れ、通知文字列を出力する stdout/stderr ログはありません。host が取得した数値は、通常の競合ではポート使用中の説明と再起動案内に、`:terminal` 付きでは `strata launch` の停止案内に使われます（`app/host/src/lib/store.ts:641-647`）。該当する測定値はありません。

## 根拠

- `app/desktop/src-tauri/src/main.rs:289-314,522-545` — 希望 port の選択、競合時の通知生成、host 子プロセスへの設定。
- `app/desktop/src-tauri/src/shell.rs:55-63`、`app/desktop/src-tauri/src/identity.rs:53-56` — port の既定選択と通知文字列の形式。
- `app/host/server/shell-prefs.mjs:59-64`、`app/host/server/index.mjs:153-163,2216-2222` — 環境値の parse と API への引き渡し。
- `app/host/src/lib/store.ts:637-647,1091` — 起動時の一度の取得と警告トースト。
- `app/desktop/src-tauri/src/supervisor.rs:503-527` — Linux supervisor の起動経路。
