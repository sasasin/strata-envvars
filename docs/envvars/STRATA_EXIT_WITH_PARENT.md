# `STRATA_EXIT_WITH_PARENT`

調査対象: Strata main の HEAD c62d5e3a15b40ea51c96aae9e8d36928965f53ab（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

親プロセスが終了したときに、子プロセスも停止させるための変数です。この名前は同じ値判定ではなく、二つの Strata 所有コード経路で読まれます。

- `apps/host/server/index.mjs` は、デスクトップアプリが起動した App Host を親プロセス終了時にクリーンシャットダウンします。
- `tools/mtp_fetch.py` は、セットアップから起動された MTP の inventory / fetch プロセスを、起動元終了時に終了させます。

環境から読んだ値を、これら以外のプロセスへ転送する処理は確認できません。セットアップの run() と Desktop の Tauri 起動コードは子プロセスの環境に値を設定します。

## 値と判定

| 読み取り箇所 | 未設定・空文字 | 有効になる値 | その他の値 |
|---|---|---|---|
| App Host (`apps/host/server/index.mjs`) | 無効 | 文字列全体が厳密に 1 | 無効 |
| MTP ツール (`tools/mtp_fetch.py`) | 無効 | 前後の空白を strip() した結果が厳密に 1 | 無効 |

Node.js 側は `process.env.STRATA_EXIT_WITH_PARENT === '1'` を判定します。` 1 `、`01`、`true`、空文字は有効になりません。Python 側は値が未設定なら空文字に置き換えた上で前後の空白を除き、厳密に比較します。そのため ` 1 ` は有効ですが、01 や true は無効です。数値変換や真偽値変換はありません。根拠: `apps/host/server/index.mjs:2281-2287`、`tools/mtp_fetch.py:217-242`。

## 有効になる条件

- **App Host:** 環境変数が厳密に 1 のとき有効です。Tauri の `host_command()` は起動する Node 子プロセスへ常に 1 を設定します（`apps/desktop/src-tauri/src/main.rs:442-482`）。この関数は Linux 以外の Desktop 起動経路から呼ばれます（同: 495-515）。ホスト側の判定自体には OS / backend / build macro / サーバーモード条件はありません。値を設定しない通常のソース起動では、この機能は無効です。
- **MTP ツール:** main() が引数を解析した後、verify 以外のコマンドで `exit_with_parent()` を呼びます。したがって有効な値でも verify には適用されず、inventory と fetch に適用されます（`tools/mtp_fetch.py:475-489`）。
- **セットアップからの起動:** `setup.py` の run() は、子プロセス環境のコピーに `setdefault("STRATA_EXIT_WITH_PARENT", "1")` を適用します。呼び出し元が値を渡していれば保持し、未指定のときだけ 1 を追加します。`fetch_mtp()` はこの run() を通じて MTP fetch を起動します（`setup.py:959-978,981-988`）。run() は他のセットアップ用ツール起動にも使われますが、この変数を読む箇所として確認できたのは mtp_fetch.py です。

## 実行時の詳細

App Host はモジュール起動時に値を一度判定し、有効ならその時点の `process.ppid` を記録します。その後 1 秒ごとに親の消失を調べます。POSIX 系では ppid の変化、Windows では記録した PID に対する `process.kill(parent, 0)` の失敗が `ESRCH` になることを消失と判断します。消失時は `shutdown()` を呼び、task timer と task queue を閉じ、HTTP server と接続を閉じて共有・トンネル・native・agent の各機能を停止し、終了コード 0 で終了します。通常の停止処理には control がある場合 45 秒、ない場合 10 秒の終了タイマーも設定されています。親消失専用のログ出力はこの分岐にはありません。根拠: `apps/host/server/index.mjs:2268-2288`。

MTP ツールは inventory / fetch の処理開始前に値を読みます。親 PID が 1 以下なら監視を開始しません。Windows では親プロセスの同期ハンドルを開けなければ監視せずに戻ります。監視開始後は別スレッドが 1.5 秒間隔で親の終了を確認し、終了を検知すると stderr に `the process that started this download has ended: stopping` を出して `os._exit(1)` で終了します。通常の verify は監視関数の呼び出し前に終了します。根拠: `tools/mtp_fetch.py:217-242,475-489`。

値はどちらも起動時の環境から判定され、後からプロセス環境を変えても再判定されません。CLI 引数による上書きはありません。Tauri の Desktop 起動では `.env("STRATA_EXIT_WITH_PARENT", "1")` が継承環境より優先します。セットアップの run() では setdefault により、明示された環境値が既定の 1 より優先します。 MTP fetch がこの機能で非 0 終了した場合、fetch_mtp() は失敗として扱い、最大 3 回まで 5 秒待って再試行し、最後はセットアップの失敗経路へ進みます（setup.py:981-997）。

## 根拠

- App Host の厳密な値比較、親消失監視、クリーン終了: `apps/host/server/index.mjs:2268-2288`
- Desktop がホスト子プロセスへ 1 を設定: `apps/desktop/src-tauri/src/main.rs:442-482`
- セットアップ子プロセス環境への既定値追加と MTP fetch 起動: `setup.py:959-978,981-988`
- MTP ツールの値判定、OS 別監視、stderr と終了コード、適用コマンド: `tools/mtp_fetch.py:217-242,475-489`
