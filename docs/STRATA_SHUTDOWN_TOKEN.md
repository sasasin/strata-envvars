# `STRATA_SHUTDOWN_TOKEN`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

デスクトップシェルと App Host の間で共有する内部認証値です。シェルまたはデスクトップのウィンドウプロセスが App Host の管理 API を呼ぶ際、`x-strata-shutdown` HTTP ヘッダーにこの値を入れます。Host は同じプロセス環境の `STRATA_SHUTDOWN_TOKEN` と比較し、UI 状態の更新、終了要求、ドロップファイル受け渡しを許可します。

これは起動時にシェルが生成・設定する値です。利用者が外から指定するオプションとしては使われず、デスクトップの起動コマンドが親環境の同名値を上書きします。

## 値と判定

| 箇所 | 判定・既定値 |
|---|---|
| デスクトップシェルの生成 | `random_token()` が64文字の16進文字列を生成します。ユーザー環境から値を読みません。 |
| Node App Host の認証 | `process.env.STRATA_SHUTDOWN_TOKEN ?? ''` で取得します。未設定は空文字です。トークン長が32文字未満、ヘッダー値の文字列長がトークンと異なる、または `timingSafeEqual` の比較が一致しない場合は認証失敗です。大文字小文字も区別されます。 |
| Linux ウィンドウ子プロセス | `std::env::var(...).unwrap_or_default()` で取得します。未設定または Unicode 文字列として取得できない場合は空文字になります。読み取った値を管理 API のヘッダーに使います。 |

Host 側は `1` など特定の値を要求せず、文字列を数値変換もしません。アプリが生成するトークンは ASCII の16進文字列で、長さ条件を満たします。Host は `fromShell()` の呼び出しごとに `process.env` を参照します。Linux ウィンドウ子プロセス側は起動後に一度読み取ってローカル変数に保持します。

## 有効になる条件

この変数を使う経路は Strata デスクトップアプリの Host とウィンドウプロセスです。App Host は `/api/control/ui`、`/api/control/shutdown`、`/api/app/drop` の POST を受ける際、`fromShell()` が真でなければ `403` と `Not allowed.` を返します。これら以外の API でこのトークンによる認証は行いません。

Host を直接起動して変数が未設定、空、または32文字未満なら、上記の3 API はトークン認証を通過しません。デスクトップシェル起動時は Host コマンドにトークンを設定し、Linux の別ウィンドウプロセスにも同じ値を渡します。Windows/macOS のウィンドウは同一アプリプロセスで Host と連携し、シェルが保持するトークンをヘッダーに使います。

## 実行時の詳細

Linux では `supervisor.rs` が起動ごとにトークンを生成し、Host 子プロセスと `--window-child` プロセスへ環境変数として設定します。Host への `--quit` 要求やウィンドウ切替・登録要求では、保存した同じ値を `x-strata-shutdown` ヘッダーに入れます。Windows/macOS では `main.rs` がトークンを生成して Host の環境に設定し、アプリ状態に保持します。終了処理のシェルは `/api/control/shutdown` にヘッダー付き POST を送り、Host は認証後に HTTP 202 を返して通常の `shutdown()` を開始します。

Linux のウィンドウ子プロセスは起動時に環境値を読み、Host へのウィンドウ登録とファイルドロップ送信で同じヘッダーを付けます。誤った値や不在時に返る `403 Not allowed.` は呼び出し側で個別に処理されます。Host 側で認証失敗を示す専用ログは確認できません。

## 根拠

- `apps/desktop/src-tauri/src/main.rs:199-215,480-490` — トークンの生成、Host 起動環境への設定、アプリ状態への保持。
- `apps/desktop/src-tauri/src/main.rs:431-477,535-573` — Host 起動環境の組み立てと終了要求。
- `apps/desktop/src-tauri/src/supervisor.rs:164-174,229-239,241-255,340-365,388-399` — Linux の Host 要求、子プロセスへの環境値引き渡しと起動。
- `apps/desktop/src-tauri/src/main.rs:1082-1100,1104-1123,1135-1149` — Linux ウィンドウ子プロセスの読み取り、ドロップ・登録要求。
- `apps/host/server/index.mjs:1284-1289,1298-1315,1317-1320` — Host の比較方法、認証される API、拒否応答。
- `apps/host/server/index.mjs:2213-2223` — 認証後の終了処理。
