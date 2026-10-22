# `STRATA_NO_ACQUIRE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

インストール、ダウンロード、ビルドなどの acquisition（ソフトウェア取得）を、プロセス単位で拒否するガードです。Python の `strata_control.acquisition` と、Node.js の host server `apps/host/server/acquisition.mjs` がそれぞれ値を読みます。値が拒否条件に合う場合、取得処理の前に専用エラーを送出します。

この変数はモデルや通常のサーバー処理を無効にするものではありません。Strata のコメントと呼び出し箇所では、start/serve 中に不足したエンジン等を自動取得せず、明示的な install/setup/update に委ねる境界として使われています。

## 値と判定

| 読み取り側 | unset / 空文字 | 拒否する値 | 拒否しない値 |
|---|---|---|---|
| Python Control | unset は拒否しない。空文字も拒否しない | `1`, `true`, `yes`, `on` | 上記以外 |
| Node.js host | unset は拒否しない。空文字も拒否しない | `1`, `true`, `yes`, `on` | 上記以外 |

どちらも文字列の前後空白を除去し、小文字化してから完全一致で判定します。そのため ` TRUE ` は拒否し、`false`、`0`、`y`、空文字は拒否しません。数値変換は行いません。Python は `os.environ.get(..., "").strip().lower()`、Node.js は `String(env.STRATA_NO_ACQUIRE ?? '').trim().toLowerCase()` を使います。

Node.js host では別条件として `STRATA_PACKAGED === '1'` でも取得を拒否します。これは `STRATA_NO_ACQUIRE` の値判定ではなく、host 側の追加条件です。

## 有効になる条件

- Python: `acquisition.require()` が呼ばれる処理で有効です。加えて `setup.py` の `start()` は `acquisition.forbidden()` のスコープ内で `_start()` を実行するため、環境変数が unset でもそのスコープ中は取得が拒否されます。
- Node.js host: `engine-install.mjs` の llama.cpp 検索・導入、`cloudflared-install.mjs` の connector 導入など、`require()` を通る取得経路で有効です。host の API 状態には拒否状態と変数値を含めます。
- Tauri shell は起動する host に `STRATA_NO_ACQUIRE=1` を設定し、Control の子プロセスにも設定します。managed server の起動時にも Python runtime が子環境へ `1` を設定します。
- 明示的な取得を行う一部の子プロセスでは、この変数を引き継がないようにします。`strata launch` の engine 子プロセス環境と、`setup.py` が feed から engine を取るために起動する update 子プロセスは、環境からこの変数を削除します。親プロセス自身の判定を解除する処理ではありません。

## 実行時の詳細

Python は `is_forbidden()` が呼ばれるたびに環境変数を読み直します。値は static cache されません。判定が拒否なら `require()` は `AcquisitionRefused` を送出します。例外には `code = "acquisition_refused"`、`exit_code = 5` があり、既定メッセージには不足物と明示的な setup/update/install コマンドが含まれます。CLI の update 経路はこの例外を失敗メッセージと終了コード 5 に変換します。`setup.py` の取得境界も `_urlopen()`、install/build 実行、component fetch などで `require()` を呼びます。

Python の `forbidden()` は環境値に加えて、ネスト可能なプロセス内 `_depth` も参照します。`setup.py` の start 処理はこのコンテキストを使います。`strata_control.runtime` は managed server の `subprocess.Popen` に渡す `child_env` を作る際に値を `1` で上書きします。

Node.js は `forbidden()` / `require()` の呼び出し時に渡された環境（既定は `process.env`）を評価します。拒否時は `AcquisitionRefused` を送出し、`code` は `acquisition_refused`、HTTP 用 `status` は 409 です。llama.cpp の fetch は検索・導入関数の入口で、cloudflared は既存 connector が見つからず導入に進む前に判定されます。そのため、値が拒否条件に合っても既存 connector の検出自体は止めません。

Strata の setup/runtime 処理は環境変数を変更せず、判定は各 `require()` 時点の値に従います。子プロセスへの継承は各起動側の環境構築によります。特に Tauri は host/Control に `1` を設定し、`strata launch` と feed engine update の明示経路は対象子プロセスから変数を削除します。

## 根拠

- 値の判定、拒否例外、プロセス内 `forbidden()` スコープ: `strata_control/acquisition.py:26-73`。
- start 処理へのスコープ適用: `setup.py:6546-6551`。
- setup の取得境界: `setup.py:740-755`; component download: `strata_control/components.py:524-545`。
- update 経路での拒否と CLI の終了コード変換: `strata_control/updater.py:303-315`; `strata_cli/update_cmd.py:217-225`。
- Node.js host の値判定・例外: `apps/host/server/acquisition.mjs:12-30`。
- host のエンジン取得: `apps/host/server/engine-install.mjs:68-88`; connector 取得: `apps/host/server/cloudflared-install.mjs:46-55`。
- Tauri による host/Control への設定: `apps/desktop/src-tauri/src/main.rs:229-235,610-618`。
- managed server 子プロセスへの設定: `strata_control/runtime.py:804-818`。
- 明示的な child acquisition の環境から削除: `strata_cli/launch/runner.py:416-426`; `setup.py:4098-4112`。
- 実行時取得を拒む設計とユーザー選択モデル取得との区別: `packaging/README.md:118-123`。
