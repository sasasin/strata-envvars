# `STRATA_ONBOARDING_UPSTREAM`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/host/tests/fixtures/onboarding-ui-host.mjs` が、UI プレビュー fixture の GET `/api/...` リクエストを転送する upstream の URL 基点として読み取ります。これは `apps/host` の UI プレビュー／スクリーンショット用 fixture の設定で、エンジン本体や通常の Strata サーバーの環境変数読み取りではありません。fixture のコメントもスクリーンショット専用であることを示しています（`apps/host/tests/fixtures/onboarding-ui-host.mjs:1,6-7,110-116`）。

## 値と判定

| 環境値 | fixture が使う値 |
|---|---|
| 未設定（`process.env.STRATA_ONBOARDING_UPSTREAM` が `undefined`） | `http://127.0.0.1:5161` |
| 空文字 | 空文字のまま。既定 URL へは置き換わらない |
| その他 | 文字列をそのまま URL 基点として使う |

判定は JavaScript の nullish coalescing (`??`) だけで、空白除去、URL 検証、末尾 `/` の除去、CLI 引数との比較はありません。値はモジュール初期化時に `const upstream` へ一度読み込まれるため、起動後に環境を書き換えても fixture の値は変わりません（`apps/host/tests/fixtures/onboarding-ui-host.mjs:6`）。

## 有効になる条件

- fixture を直接起動した場合、未設定なら既定の `http://127.0.0.1:5161` が使われます。
- `STRATA_UI_PREVIEW === '1'` の場合、起動時の `/api/native` 取得はローカル fixture データに切り替わり、この変数はその取得には使われません。それ以外の場合は起動時に `${upstream}/api/native` を fetch します（`apps/host/tests/fixtures/onboarding-ui-host.mjs:6-8`）。
- いずれの場合も、fixture が後から受けた GET `/api/...` のうち、fixture 内で個別処理されない経路は `${upstream}${req.url}` へ転送します。非 GET の `/api/...` は転送せず、fixture 側でエラーにします（`apps/host/tests/fixtures/onboarding-ui-host.mjs:80-116`）。
- `scripts/preview-ui.mjs` と `scripts/language-shots.mjs` は、子 fixture の環境に `STRATA_ONBOARDING_UPSTREAM` を自身の `hostPort` に対応する `http://127.0.0.1:...` として明示設定します。両スクリプトの `run` は `{...process.env, ...extra}` の順で環境を組み立てるため、親プロセスに同名変数があってもこの設定が優先します（`apps/host/scripts/preview-ui.mjs:13,24`、`apps/host/scripts/language-shots.mjs:30,40`）。

## 実行時の詳細

fixture は `/api/native`、`/api/setup` など一部の API をローカルで応答し、それ以外の `/api/` GET を upstream に fetch します。応答 JSON を読み、`/api/hardware`、`/api/models`、`/api/runtime` では fixture 用の値を追加または置換してから、upstream の HTTP status とともにクライアントへ返します（`apps/host/tests/fixtures/onboarding-ui-host.mjs:81-116`）。このため設定値が直接変更するのは fixture の転送先です。転送先サービス側の処理や環境変数の意味はこの文書の対象外です。

転送時の fetch、JSON 読み込み、その他のリクエスト処理で例外が発生すると、fixture の catch 節が status 400 と `{error: e.message}` を返します。upstream URL が不正または到達不能なときに出るランタイム固有のエラー文言までは Strata ソースからは特定できません（`apps/host/tests/fixtures/onboarding-ui-host.mjs:66-67,110-122`）。

## 根拠

- 唯一の環境値読み取りと既定値: `apps/host/tests/fixtures/onboarding-ui-host.mjs:6`。
- 起動時の native データ取得の分岐: `apps/host/tests/fixtures/onboarding-ui-host.mjs:7-8`。
- GET API のローカル応答・upstream 転送・例外応答: `apps/host/tests/fixtures/onboarding-ui-host.mjs:80-122`。
- プレビュー起動側での値設定と親環境値の上書き: `apps/host/scripts/preview-ui.mjs:13,24`、`apps/host/scripts/language-shots.mjs:30,40`。

候補名の全参照をソースツリーで検索した結果、上記 fixture と2つの起動スクリプトの計3箇所でした。本番エンジン／通常サーバーの読み取りは確認できませんでした。候補一覧にはこの test/preview fixture 専用の参照が含まれています。
