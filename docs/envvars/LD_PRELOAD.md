# `LD_PRELOAD`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の Linux AppImage 向け外部プロセス環境の整形対象です。Strata はこの名前を `external-env.mjs` のパス一覧に含め、AppImage が追加した自身のディレクトリを指す要素を、古い AppImage 起動環境から取り除きます。個々の値を有効・無効として解釈したり、Strata 本体のロード設定として使ったりするコードは見つかりませんでした（`apps/host/server/external-env.mjs:25-26,43-57`）。

`externalEnvironment()` の結果はフォルダー選択、デスクトップ通知、ファイルや URL を開くプログラムなど、Strata 外部の子プロセスへ渡されます。Strata が `LD_PRELOAD` を転送または除去する処理はありますが、子プロセスや動的ローダーが受け取った値をどう扱うかはこの調査の対象外です（`apps/host/server/folder-dialog.mjs:106-119`, `apps/host/server/app-ui.mjs:38-46,55-59`, `apps/host/server/chat-files.mjs:89-94`, `apps/host/server/open-text-file.mjs:26-36`, `apps/host/server/artifacts.mjs:5-6`）。

## 値と判定

値を数値・真偽値・単一パスとして parse しません。AppImage の古い起動環境を整える分岐では、コロン区切りの要素ごとに文字列として検査します。空要素は除かれ、`APPDIR` と一致する要素、または `APPDIR/`・`APPDIR//` で始まる要素が除かれます。残りがあればコロンで連結し、残りがなければ `LD_PRELOAD` 自体を環境オブジェクトから削除します（`apps/host/server/external-env.mjs:43-57`）。

| 状況 | Strata が作る外部環境の `LD_PRELOAD` |
|---|---|
| AppImage 外で、`STRATA_ORIGINAL_ENV` もない | 入力環境の値をそのままコピー。unset は unset、空文字も空文字のまま（`external-env.mjs:64-70`）。 |
| `STRATA_ORIGINAL_ENV` に有効な非空環境レコードがある | レコードを base64 decode し、NUL 区切りの `NAME=VALUE` から復元した元環境の値を使用。元環境に `LD_PRELOAD` がなければ未設定。現在の値とのマージはしない（`external-env.mjs:28-40,67-70`）。 |
| レコードがない／無効で、`APPDIR` がある | 現在の値から空要素と `APPDIR` 内を指す要素を除く。全要素が除かれる場合は未設定（`external-env.mjs:43-57,67-70`）。 |
| レコードがなく、`APPIMAGE` はあるが `APPDIR` がない | `withoutAppImage()` は一覧の値を編集しないため、値はそのままコピーされる（`external-env.mjs:43-57,61,67-70`）。 |
| `externalEnvironment(env, extra)` の `extra` に `LD_PRELOAD` がある | 上記の環境へ `extra` を最後に展開するため、その値で上書き（`external-env.mjs:64-70`）。調査した標準 caller は `extra` を指定していない。 |

`APPDIR` 内判定はパスの正規化ではなく、文字列の完全一致または前方一致です。区切りは常に `:` として処理されます。パスの解決、引用符やエスケープの解釈はありません（`external-env.mjs:45-55`）。

## 有効になる条件

- `externalEnvironment()` が参照される外部プログラム起動経路で使われます。代表例は Linux の `zenity` / `kdialog` / `gdbus` によるフォルダー選択、`notify-send`、ファイル・URL の opener、`xdg-open`、成果物を開く処理です（上記「役割」の caller 参照）。
- AppImage の記録環境が有効なら、その記録を優先します。記録環境がないときは `APPDIR` を使った除去に進みます。AppImage 外で記録もなければコピーだけです（`external-env.mjs:28-40,43-70`）。
- Agent Harness の子プロセスでは、`externalEnvironment()` 後に環境名の allowlist で絞られます。`KEEP` に `LD_PRELOAD` は含まれないため、通常の継承値は Harness に渡されません（`apps/host/server/agent/harness-runtime.mjs:22-36,75-83`）。
- `LD_PRELOAD` 専用の CLI 引数、Strata 設定、優先順位、警告、build macro 分岐はありません。呼び出し側が独自の `extra` を与える場合はその値が最後に優先します。

## 実行時の詳細

`externalEnvironment()` はデフォルト引数 `env = process.env` を呼び出しごとに受け取り、結果の環境オブジェクトを子プロセス起動側へ渡します。`LD_PRELOAD` の値を保持する static cache や、独立した起動時読み取りはありません（`apps/host/server/external-env.mjs:29,44,61,67-70`）。一方、Harness 起動はその環境をさらに allowlist で絞るため、通常はこの変数を子へ引き継ぎません（`apps/host/server/agent/harness-runtime.mjs:26-36,80-83`）。

`LD_PRELOAD` に対する個別ログや終了処理はありません。外部プロセス起動が失敗した場合の結果は caller ごとに異なります。たとえば folder chooser は候補の失敗を記録し、利用可能な chooser がなければ入力案内付きの結果を返します（`apps/host/server/folder-dialog.mjs:110-139`）。opener は短時間内の起動エラーを `false` とし、ファイル opener は spawn error を無視します（`apps/host/server/app-ui.mjs:38-46`, `apps/host/server/chat-files.mjs:89-94`）。これらを `LD_PRELOAD` に固有の失敗とは判定できません。

## 根拠

- `apps/host/server/external-env.mjs:25-26` — `LD_PRELOAD` を含む動的なパス一覧。
- `apps/host/server/external-env.mjs:28-40` — `STRATA_ORIGINAL_ENV` の復元。
- `apps/host/server/external-env.mjs:43-57,61-70` — `APPDIR` 内要素の削除、AppImage 判定、外部環境の選択と `extra` の優先。
- `apps/host/server/folder-dialog.mjs:106-139`, `apps/host/server/app-ui.mjs:38-59`, `apps/host/server/chat-files.mjs:89-94`, `apps/host/server/open-text-file.mjs:26-36`, `apps/host/server/artifacts.mjs:5-6` — 整形済み環境を渡す caller。
- `apps/host/server/agent/harness-runtime.mjs:22-36,75-83` — Harness への allowlist と子プロセス起動。
