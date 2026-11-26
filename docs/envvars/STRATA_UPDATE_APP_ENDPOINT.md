# `STRATA_UPDATE_APP_ENDPOINT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Desktop アプリの Tauri updater が使う endpoint を、通常の `tauri.conf.json` の endpoint から差し替えるための環境変数です。実装コメント上の用途はローカルのテスト feed で、HTTPS または loopback HTTP の URL に限定されます。変数名を定数に置いた箇所は `app/desktop/src-tauri/src/updater.rs:25-26`、選択処理は同ファイル `:224-240` です。

対象は Desktop アプリ自身の更新です。Terminal の `strata update` やエンジン・モデル更新の設定ではありません。通常の feed 確認は Settings の「Check for updates」操作で行われ、Settings の表示やアプリ起動だけでは行われません。更新ジョブ完了後には結果を更新する再確認もあります。インストールは「Update」操作から始まります（`app/host/src/components/SettingsUpdates.tsx:26-37,81-90`、`app/host/server/updates.mjs:50-64,87-97`、`app/host/server/native-control.mjs:808-830`）。

## 値と判定

`std::env::var(ENDPOINT_ENV).ok()` で Unicode 文字列として読み、文字列の先頭を大文字小文字を区別して比較します。数値変換、空白除去、URL 全体に対する許可リスト照合はありません（`app/desktop/src-tauri/src/updater.rs:224-230`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Desktop updater の endpoint 選択 | `None` となり、`tauri.conf.json` の endpoint を使う | `https://`、`http://127.0.0.1:`、`http://localhost:` のいずれかで始まり、さらに Tauri の URL 型に parse できる文字列。例: `https://updates.example.com/latest.json`、`http://127.0.0.1:19080/app/latest.json`、`http://localhost:19080/latest.json` | 空文字、`0`、`1`、`true`、`false`、`http://example.com/feed`、`HTTPS://updates.example.com/feed`、先頭に空白がある値などは接頭辞判定に失敗し、設定 endpoint に戻る。非 Unicode 値も `var(...).ok()` が失敗するため unset と同じ扱い |

接頭辞判定を通った後に URL parse が失敗すると `bad update endpoint: {parse error}` が返ります。この場合は設定 endpoint へ戻りません。例えば接頭辞だけの `https://` は接頭辞判定を通りますが、parse エラーになります（`app/desktop/src-tauri/src/updater.rs:233-240`）。

有効な override は一つの URL を `endpoints(vec![url])` に渡します。無効値や未設定では Tauri 設定の endpoint に切り替えます。設定ファイルの既定値は `https://github.com/Niko1221/Strata/releases/latest/download/latest.json` です（`app/desktop/src-tauri/src/updater.rs:233-240`、`app/desktop/src-tauri/tauri.conf.json:66-75`）。CLI 引数や別環境変数による優先順位はこの実装にはありません。

## 有効になる条件

- Desktop アプリの Tauri updater 経路で使われます。Windows/macOS では shell が App Host を起動して bridge を渡し（`app/desktop/src-tauri/src/main.rs:554-568`）、Linux では shell が window child を起動し、その child が updater bridge を登録します（`app/desktop/src-tauri/src/supervisor.rs:390-400,552-555`、`app/desktop/src-tauri/src/main.rs:1295-1349`）。
- bridge が作成できることが必要です。loopback listener を bind できない場合 `updater::start` は `None` を返し、アプリ内 updater は利用できません（`app/desktop/src-tauri/src/updater.rs:441-455`）。
- Host 側から token 付き loopback bridge に check/install の要求が来たときに endpoint を選びます。通常の check は Settings のボタンから、または更新ジョブ完了後の再確認から呼ばれます（`app/host/src/components/SettingsUpdates.tsx:26-37,81-90`、`app/host/server/updates.mjs:50-64,87-97`、`app/host/server/native-control.mjs:808-830`、`app/host/server/app-updater.mjs:19-28,35-42`、`app/desktop/src-tauri/src/updater.rs:402-415`）。
- 変数が未設定または接頭辞判定に失敗した場合は、`tauri.conf.json` の既定 endpoint が使われます。許可接頭辞を満たすが URL parse に失敗する値では、その操作がエラーになります（`app/desktop/src-tauri/src/updater.rs:224-240`）。
- GPU backend、モデル状態、サーバーモードには依存しません。Terminal updater は別経路です。候補名の全参照を検索した結果、この updater 実装以外に本番コードの読み取りはありません。

## 実行時の詳細

`endpoint_override()` に static cache はなく、`updater_for()` が呼ばれるたびに現在のプロセス環境を読みます。更新確認は bridge の `GET /app-update/check` から `check()` を呼び、インストールは `POST /app-update/install` から非同期 `install()` を起動します。したがって check と install はそれぞれ updater を作り、その時点で endpoint を選びます（`app/desktop/src-tauri/src/updater.rs:224-245,257-270,402-415`）。

Windows/macOS では updater を持つ shell 自身が値を読みます。Linux では supervisor が環境を明示的に消さずに window child を起動し、window child 側で bridge を作るため、その child のプロセス環境から読みます（`app/desktop/src-tauri/src/supervisor.rs:390-400,552-555`、`app/desktop/src-tauri/src/main.rs:1295-1349`）。App Host へ渡す `apply_env` が追加するのは bridge URL/token とアプリ version で、この endpoint 値を別途転送・上書きする処理はありません（`app/desktop/src-tauri/src/updater.rs:457-464`）。

## ログと測定値

この変数の値を報告する専用 stdout/stderr ログはありません。check 時に updater 作成または確認が失敗すると、shell bridge は `502 Bad Gateway` と `{ "error": ... }` を返します。install 時は同じ種類の失敗が progress の `state: "error"` と `error` に入り、Host はその error を例外として扱います。これらのエラー経路は `app/desktop/src-tauri/src/updater.rs:243-270,402-415`、Host 側の受け取りは `app/host/server/app-updater.mjs:23-28,41-64` にあります。専用の性能測定値はありません。

## 根拠

- `app/desktop/src-tauri/src/updater.rs:25-26,224-240` — 変数名、値の判定、設定 endpoint との切り替え。
- `app/desktop/src-tauri/tauri.conf.json:66-75` — 設定 endpoint。
- `app/desktop/src-tauri/src/updater.rs:243-310,379-417,441-464` — check/install、bridge と App Host への環境設定。
- `app/desktop/src-tauri/src/main.rs:554-568,1295-1349`、`app/desktop/src-tauri/src/supervisor.rs:390-400,552-555` — OS ごとの updater bridge 起動経路。
- `app/host/server/app-updater.mjs:19-28,35-64` — Host から bridge を呼ぶ契機と応答エラーの扱い。
