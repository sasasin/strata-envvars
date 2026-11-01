# `STRATA_UI_PREVIEW`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

UI preview / 言語別 screenshot 用の onboarding fixture が、native 状態データをどこから初期化するかを選びます。`STRATA_UI_PREVIEW` を読むのは `apps/host/tests/fixtures/onboarding-ui-host.mjs` だけです。通常の Strata engine/server の環境設定として使う実装は確認できませんでした。この fixture はコメントでも「Screenshot-only」とされ、preview script が画面表示のために起動するシミュレーションです。

## 値と判定

値は文字列全体で厳密に比較されます。

| 値 | fixture の初期化 |
|---|---|
| `"1"` | 同梱の `ui-preview-native.json` を読み、JSON として parse する |
| 未設定、空文字、その他すべて | `STRATA_ONBOARDING_UPSTREAM`（未設定なら `http://127.0.0.1:5161`）の `/api/native` を fetch し、応答を JSON として読む |

空白、大文字小文字、数値変換、先頭文字判定はありません。たとえば `"01"` や `"true"` は `"1"` と一致せず、upstream 経路になります。ローカル JSON の読み込みまたは parse に失敗した場合、fallback はありません。upstream 経路でも fetch / JSON parse の失敗を fixture 内で捕捉・置換する処理はありません。いずれもサーバー生成前の top-level 初期化です。

## 有効になる条件

- `apps/host/scripts/preview-ui.mjs` と `apps/host/scripts/language-shots.mjs` は、fixture を子プロセスとして起動する際に `STRATA_UI_PREVIEW: '1'` を明示設定します。これらの起動経路では、親プロセスから継承した同名値があっても `"1"` で上書きされます。
- fixture を直接起動した場合は、起動時の環境値がそのまま判定されます。CLI 引数や設定ファイルによる優先順位はありません。
- この分岐が変えるのは fixture が使う native 状態 JSON の取得元です。fixture はその後、ハードウェア情報やモデル状態などを模擬値で上書きします。実推論や本番 engine の動作を有効化するスイッチではありません。

## 実行時の詳細

fixture のモジュール初期化時に一度だけ `process.env.STRATA_UI_PREVIEW === '1'` を評価します。値を後から変更して再評価する処理や cache helper はありません。preview 用の2スクリプトは fixture に加え `STRATA_ONBOARDING_UPSTREAM`、port、scenario なども渡しますが、native JSON の選択に関わるのは `STRATA_UI_PREVIEW` です。分岐自体に専用ログはありません。上位 preview scripts は host 起動待ちの期限超過時に stderr へエラーを出して終了処理を開始しますが、native JSON の branch-specific な警告や fallback は実装されていません。

## 根拠

- `apps/host/tests/fixtures/onboarding-ui-host.mjs:1-8` — screenshot 専用 fixture であること、環境値の厳密比較、JSON または upstream からの native 状態取得、直後の模擬 hardware 上書き。
- `apps/host/scripts/preview-ui.mjs:13-25` — 隔離 preview host と fixture を起動し、fixture の子プロセス環境へ値 `'1'` を渡す。
- `apps/host/scripts/language-shots.mjs:3-4,26-40` — screenshot 専用の隔離 host と fixture を起動し、同じく値 `'1'` を渡す。
- `apps/host/package.json:26-27` — `preview:ui` script が `preview-ui.mjs` を起動する。
- `apps/host/README.md:24` — 言語別 screenshot の実行方法を記載。

`STRATA_UI_PREVIEW` のソース全体検索では、上記2つの preview script による設定と fixture の読み取り以外に参照はありませんでした。
