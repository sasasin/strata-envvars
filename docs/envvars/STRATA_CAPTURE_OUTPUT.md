# `STRATA_CAPTURE_OUTPUT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

この名前を読むのは `apps/host/tests/fixtures/onboarding-ui-host.mjs` のローカル onboarding UI fixture だけです。値を指定すると、fixture に PNG export 用 UI と依存スクリプトを追加し、fixture の capture endpoint が受け取った PNG を指定パスへ保存します。エンジン、通常の Strata UI/server、その他の製品コードにおける読み取りは確認できません。候補一覧の名前は製品向け設定ではなく、この screenshot fixture 専用フックとして解釈する必要があります。

## 値と判定

値の文字列全体や数値は parse しません。JavaScript の truthiness で設定有無を判定し、truthy の値を保存先パスとして `writeFile` に渡します。

| 値 | fixture の扱い |
|---|---|
| 未設定 | falsy。export UI / endpoint を有効にしない |
| 空文字 | falsy。未設定と同じ |
| 空でない文字列 | truthy。export UI / endpoint を有効にし、その文字列を出力パスに使う |

値の形式・パスの事前検証、既定パス、CLI 引数や他の環境変数との優先順位、無効値時の fallback はありません。相対パスの解決基準や出力先ディレクトリの作成も、この fixture のコードでは指定されていません。

## 有効になる条件

- `apps/host/tests/fixtures/onboarding-ui-host.mjs` を起動したときだけ作用します。`apps/host/scripts/preview-ui.mjs` と `apps/host/scripts/language-shots.mjs` はこの fixture を子プロセスとして起動し、子の `env` に `process.env` を展開して渡すため、呼び出し元で設定した値は上書きされず継承されます (`apps/host/scripts/preview-ui.mjs:13,24`; `apps/host/scripts/language-shots.mjs:26-30,40`)。
- 値が truthy の場合でも、capture endpoint は `POST /__fixture/capture` のときだけ保存処理をします。HTML と export 用 JavaScript の fixture route、および `/index.html` への script 注入も同じ truthy 判定です (`apps/host/tests/fixtures/onboarding-ui-host.mjs:69-79,118-121`)。
- OS、GPU backend、build macro、モデル状態はこのフックの判定に関与しません。通常の製品実行経路で有効になる条件はありません。

## 実行時の詳細

fixture は環境変数を module 起動時に cache せず、HTTP request の処理中に `process.env.STRATA_CAPTURE_OUTPUT` を参照します。truthy の状態で capture endpoint に POST すると、`body.dataUrl` が文字列で `data:image/png;base64,` から始まることを確認します。満たさなければ `A PNG export is required` の例外になり、満たす場合はその prefix を除いた内容を `Buffer.from(..., 'base64')` に渡し、環境変数の値をパスとして `writeFile` します。成功時は `{saved:true,width,height}` を HTTP 200 で返します (`apps/host/tests/fixtures/onboarding-ui-host.mjs:66-72`)。

fixture server の request handler は例外を捕捉し、例外メッセージを JSON `{error:...}` として HTTP 400 で返します (`apps/host/tests/fixtures/onboarding-ui-host.mjs:66-67,122`)。export 用ブラウザスクリプトは失敗時に `Export failed: ...` を画面に表示します (`apps/host/tests/fixtures/onboarding-export.js:41-48`)。したがって、保存先への書き込み失敗も fixture の HTTP 400 と画面上の export failure になります。成功時には保存ファイルの幅・高さを画面に表示します (`apps/host/tests/fixtures/onboarding-export.js:41-44`)。

## 根拠

- 全参照検索では、候補名の使用箇所は `apps/host/tests/fixtures/onboarding-ui-host.mjs:69,71,74,77,120` のみです。参照箇所はいずれも `apps/host/tests/fixtures/` 配下で、製品コードの読み取りは見つかりませんでした。
- fixture 専用であることと PNG 保存 UI の用途: `apps/host/tests/fixtures/onboarding-ui-host.mjs:69-79,118-121`; `apps/host/tests/fixtures/onboarding-export.js:1-2,35-44`。
- preview / screenshot 起動時の環境引き継ぎ: `apps/host/scripts/preview-ui.mjs:13,24`; `apps/host/scripts/language-shots.mjs:26-30,40`。
- `docs/DETAILS.md` にこの変数の説明はありません。
