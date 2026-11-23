# `STRATA_APP_VERSION`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata デスクトップアプリの版を App Host と更新処理へ伝える。App Host の `/api/setup` が返すアプリ版の表示値に使われ、更新確認ではインストール済みアプリ版として Control の `--app-version` 引数または CLI 更新コンテキストへ渡される。アプリのバージョンを変更したり、単独で更新を実行したりする設定ではない（`app/desktop/src-tauri/src/supervisor.rs:515-527`、`app/desktop/src-tauri/src/updater.rs:457-463`、`app/host/server/index.mjs:149-150,320-331,1513-1514`、`app/host/server/control-runtime.mjs:269-299`、`terminal/strata_cli/update_cmd.py:303-321`）。

デスクトップシェルは Linux の supervisor で `env!("CARGO_PKG_VERSION")`、Windows/macOS の App Host 起動では `app.package_info().version` を子プロセス環境へ設定する。デスクトップ外の checkout 起動では App Host が同じ `app/desktop/src-tauri/Cargo.toml` を読む fallback を持つ（`app/desktop/src-tauri/src/supervisor.rs:515-527`、`app/desktop/src-tauri/src/main.rs:554-568`、`app/desktop/src-tauri/src/updater.rs:457-463`、`app/host/server/app-version.mjs:1-18`）。

## 値と判定

App Host 表示用の `appVersionFrom` は `String(env.STRATA_APP_VERSION ?? '').trim()` で読み、正規表現 `^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.+-]+)?$` 全体に一致する場合だけ値を採用する。一致しない場合は `app/desktop/src-tauri/Cargo.toml` の `version` 行を同じ形式で検証し、それも読めない・不適合なら `dev` を返す（`app/host/server/app-version.mjs:8-18`）。

| 経路 | 未設定・空文字 | 受け付ける例 | 表示用に無効となる例 |
|---|---|---|---|
| App Host の表示 (`appVersionFrom`) | 空文字として扱い、Cargo.toml の版へ fallback。読み取り失敗または不適合なら `dev` | `1.2.3`、`0.2.0-beta`、`1.2.3+build.7`。前後空白は trim 後に判定 | `1.2`、`latest`、`1.2.3x` |
| App Host の Control 更新確認 | `/api/updates/check` では `process.env.STRATA_APP_VERSION || null`。未設定・空文字は `null` として渡す | truthy の環境値を検証・trim せず `--app-version` に渡す | host 側では値検証なし。Control が版として扱えない値は更新確認エラーになり得る |
| `strata update` / `strata components update` | `--app-version` が falsy なら `os.environ.get("STRATA_APP_VERSION")`。環境変数も未設定なら `None`、空文字なら空文字 | CLI 引数が truthy なら環境変数より優先。どちらも文字列のまま更新 Context に入る | host/CLI の入力段階では形式検査なし。Control のアプリ版比較時に不適合ならエラー |

表示用正規表現は数値部分を 3 セグメント要求するが、先頭ゼロや suffix 内の `+` / `-` の並びを追加制約しない。対して更新比較側の `app_version_key` は `-` で区切った prerelease だけを許し、基底版を `version_key` で検証するため、`+build` を含む値は表示で受理されても更新比較で拒否される。更新側で未設定値はアプリ版 `unknown-installed` となる。feed にアプリがない、または現在の platform 向け installer がない場合はそれぞれ `not-in-feed`、`none-for-this-pc` となり、値比較はされない（`terminal/strata_control/feed.py:69-82`、`terminal/strata_control/updater.py:1980-1993`）。

## 有効になる条件

- デスクトップ版では App Host 起動時にシェルが版を設定する。Linux は Cargo の compile-time `CARGO_PKG_VERSION`、Windows/macOS は Tauri の package info を使う（`app/desktop/src-tauri/src/supervisor.rs:515-527`、`app/desktop/src-tauri/src/main.rs:554-568`、`app/desktop/src-tauri/src/updater.rs:457-463`）。
- `/api/setup` の表示値は `appVersionFrom` の検証・fallback 結果。ソース checkout では Cargo.toml が読める場合にその版を表示し、環境値が不適合でも更新 API に渡す値まで置き換えるわけではない（`app/host/server/index.mjs:149-150,320-331,1513-1514`、`app/host/server/app-version.mjs:10-18`）。
- `/api/updates/check` の Control 経路は `control?.updateCheck` がある場合に限り、環境値を Control の `--app-version` として渡す。Control がなければ別の `checkUpdates` 経路を使い、`setupState().app.version` と native state の版を `appVersionToShow` で選ぶ（`app/host/server/index.mjs:1513-1514`、`app/host/server/control-runtime.mjs:269-285`）。
- CLI の `--app-version` が指定されると環境変数より優先する。ただし `getattr(..., None) or os.environ.get(...)` のため、空文字の引数は環境変数へ fallback する。値はアプリ更新が feed に含まれ、対応 platform の項目があるときに版比較に影響する（`terminal/strata_cli/update_cmd.py:59-75,314-321`、`terminal/strata_control/updater.py:1980-1993`）。
- App Host の更新確認値と表示 fallback は別々に計算される。無効な非空値は表示では Cargo.toml 版または `dev` に fallback しても、Control 更新確認にはそのまま送られる（`app/host/server/index.mjs:149-150,1513-1514`）。

## 実行時の詳細

`appVersionFrom` は `/api/setup` の状態を作るたびに呼ばれ、Node の環境オブジェクトをその時点で参照する。関数内 cache はなく、プロセス起動後に環境値が変更された場合も次の呼び出しで読み直す（`app/host/server/index.mjs:149-150,320-331`）。デスクトップシェルの値は App Host 子プロセス起動時に設定される（`app/desktop/src-tauri/src/supervisor.rs:523-527`、`app/desktop/src-tauri/src/updater.rs:459-463`）。

更新確認では API handler が環境値を `|| null` で取り出し、`checkComponentUpdates` から `control.updateCheck({ appVersion })` へ渡す。Control runner は feed と版を含む引数列を作り、版が truthy のとき `--app-version <値>` を追加する。更新確認はアプリ版で feed を比較し、feed の offered 版がインストール済み版より大きければ `available`、そうでなければ `current` と報告する。アプリ版が未知なら `unknown-installed` とし、`--app` による CLI ダウンロード対象になり得る（`app/host/server/updates.mjs:55-64`、`app/host/server/control-runtime.mjs:269-285`、`terminal/strata_cli/update_cmd.py:351-363`、`terminal/strata_control/updater.py:1980-2004`）。

native-control は `process.env.STRATA_APP_VERSION || null` を使い、アプリ更新ジョブ開始時の `appUpdateFrom` として保存する。次回起動時に同じ値と比較し、値が変わっていればジョブを完了扱い、同じなら installer が旧版で再起動したエラー扱いにする。ここでは `appVersionFrom` の形式検査・Cargo.toml fallback を使わず、生の環境値を比較する（`app/host/server/native-control.mjs:128-136,829`）。

## ログと測定値

この変数自体を読み取ったことを示す専用ログはない。CLI の `--check` は更新レポートを通常出力または JSON で返す。比較時に不正な版として `FeedError` になった場合、CLI は `strata: <エラー>` を stderr に出し、例外の exit code で終了する。App Host の Control 更新確認は例外を捕捉し、`Couldn't check for updates. Try again in a moment.` を含む error 状態を返す（`terminal/strata_cli/update_cmd.py:307-312,357-363,379-382`、`terminal/strata_control/feed.py:69-82`、`app/host/server/updates.mjs:55-64`）。

## 根拠

- デスクトップから子プロセスへの設定: `app/desktop/src-tauri/src/supervisor.rs:515-527`、`app/desktop/src-tauri/src/main.rs:554-568`、`app/desktop/src-tauri/src/updater.rs:457-463`
- App Host の読み取り、検証、fallback、表示: `app/host/server/app-version.mjs:8-18`、`app/host/server/index.mjs:149-150,320-331`
- App Host の更新確認と Control への引き渡し: `app/host/server/index.mjs:1513-1514`、`app/host/server/updates.mjs:55-64`、`app/host/server/control-runtime.mjs:269-285`
- CLI の引数・環境変数優先順位と Context 設定: `terminal/strata_cli/update_cmd.py:59-75,303-321`
- 更新側のアプリ版比較・無効値判定: `terminal/strata_control/feed.py:69-82`、`terminal/strata_control/updater.py:1980-2004`
- App Host のアプリ更新完了判定: `app/host/server/native-control.mjs:128-136,829`
