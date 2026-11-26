# `WEBKIT_DISABLE_DMABUF_RENDERER`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Linux のデスクトップ起動コードが、この変数の設定有無を調べ、未設定かつ `/sys` の DRM/NVIDIA 状態が特定条件に当たる場合に、プロセス環境へ `WEBKIT_DISABLE_DMABUF_RENDERER=1` を設定する。Strata 自身は設定値を解釈せず、既存値を上書きしない。外部 WebKit がこの変数をどう扱うかは Strata の挙動としては説明しない。実装は `app/desktop/src-tauri/src/main.rs:915-923`、判定は `app/desktop/src-tauri/src/renderer_choice.rs:14-20,23-50`。

## 値と判定

| 条件（build / 実行経路） | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux デスクトップ実行ファイル | 下記の sysfs 判定が真なら Strata が `"1"` を設定。偽なら未設定のまま | Strata 側に有効値・無効値の区別はない。空文字、`0`、`1`、`true`、任意の文字列を含め、設定されていれば自動設定を抑止 | 同左。文字列の検証・変換はしない |
| Linux 以外 | `main` の自動判定では読まない | `main` による設定はない | `main` による設定はない |

`std::env::var_os(...).is_none()` による存在確認なので、空文字も「設定済み」であり自動設定を止める。大文字小文字、空白、数値としての妥当性、文字列全体は検査しない。設定済みなら、値が `0` や空文字でも Strata はそのまま残す（`app/desktop/src-tauri/src/main.rs:920-921`）。

## 有効になる条件

- 自動設定コードは `#[cfg(target_os = "linux")]` のブロックだけでコンパイルされる（`app/desktop/src-tauri/src/main.rs:915-923`）。
- Linux で変数が未設定であり、`renderer_choice::disable_dmabuf_here("/sys")` が真の場合に限り、Strata が値 `"1"` を設定する（`app/desktop/src-tauri/src/main.rs:920-921`）。
- 判定は `/sys/module/nvidia` がディレクトリなら真。または `/sys/class/drm` から DRM カードの driver を一つも列挙できない場合、もしくは列挙したカードの driver 名に `amdgpu`、`radeon`、`i915`、`xe` 以外が一つでも含まれる場合も真（`app/desktop/src-tauri/src/renderer_choice.rs:14-20,23-50`）。driver のリンクを読めないカードは空名として扱われ、許可名以外に該当する（同 `:34-40`）。
- `--browser` などの CLI モード判定より前に自動設定コードが実行されるため、その引数は自動設定を抑止しない。ブラウザモードでは後段でアプリウィンドウを起動しない（`app/desktop/src-tauri/src/main.rs:920-935`、`app/desktop/src-tauri/src/supervisor.rs:547-563`）。
- `--self-test` の分岐よりも前に同じ判定を実行する（`app/desktop/src-tauri/src/main.rs:915-926`）。
- この名前を読む呼び出しは Linux 専用の自動設定箇所と、診断用の動的な環境変数一覧である。診断一覧の読み取りは設定を変えない（`app/desktop/src-tauri/src/desktoplog.rs:186-193`）。

## 実行時の詳細

自動判定はデスクトップ実行ファイルの `main` で一度行われ、`/sys/module/nvidia` と `/sys/class/drm` をその場で確認する。関数内 cache やリクエスト単位の再評価はない。実行中に環境値や sysfs 状態を変えても、この分岐は再実行されない（`app/desktop/src-tauri/src/main.rs:901-923`、`app/desktop/src-tauri/src/renderer_choice.rs:23-50`）。

Linux の通常起動では shell が同じ実行ファイルの window child を起動し、指定する環境変数以外は継承するため、自動設定された値も window child に渡る（`app/desktop/src-tauri/src/supervisor.rs:390-401,552-555`）。アプリ更新後の再起動では、`STRATA_ORIGINAL_ENV` を復元できる場合はその環境で新しいプロセスを起動し、復元できない場合は現在の環境を継承して一部の Strata 内部変数だけを取り除く。そのため前者では次回起動時に元の利用者環境から再判定され、後者では継承された値が次回の自動判定に使われる（同 `:358-368`）。

## ログと測定値

Strata はこの変数を設定したこと自体について専用ログを出さない。診断時は `graphics_environment()` が `std::env::var` で取得できた値を `WEBKIT_DISABLE_DMABUF_RENDERER=<値>` として収集する。未設定なら一覧に現れず、空文字なら名前と `=` が記録される。Unicode 文字列として取得できない値は `.ok()` で除外される（`app/desktop/src-tauri/src/desktoplog.rs:186-193`）。この一覧はウィンドウのクラッシュレポートと `--save-logs` 出力に含まれる（同 `:241-259,310-319`）。

## 根拠

- Linux での存在確認・自動設定と実行順序: `app/desktop/src-tauri/src/main.rs:901-945`
- sysfs のカード列挙、許可 driver 名、NVIDIA 検出、最終判定: `app/desktop/src-tauri/src/renderer_choice.rs:14-50`
- 診断用の値読み取り・出力先: `app/desktop/src-tauri/src/desktoplog.rs:186-193,241-259,310-319`
- window child の環境継承と更新後の環境復元: `app/desktop/src-tauri/src/supervisor.rs:332-368,390-401,547-555`
