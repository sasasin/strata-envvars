# `STRATA_TEST_LOCALE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata の作業ツリーは `main...origin/main` で変更なし。

## 役割

ホストの `/api/locale` が返す地域情報を、開発・デモ用に指定します。値は地域タグとして parse され、通貨は常に `null` として返ります。`STRATA_PACKAGED=1` のプロセスではこの指定を使いません。通常のユーザー設定ではなく、Monitor の電気料金表示などでホストの地域情報を試すためのフックです。候補一覧 `docs/envvars/000_envvers.md:1559` に対し、本番コードでの読み取りは `apps/host/server/region.mjs:63` に確認できました。

## 値と判定

| 状態 | 処理 |
|---|---|
| 未設定 | OS から地域情報を検出し、結果をキャッシュする。 |
| 空文字 | 条件式が偽になるため未設定と同じ。 |
| 非空文字列、`STRATA_PACKAGED` が `1` 以外 | 地域タグとして parse し、`{ locale, region, currency: null, source: 'test' }` を返す。 |
| 非空文字列、`STRATA_PACKAGED=1` | テスト値を無視し、OS からの検出へ進む。 |

変換は `parseLocaleTag()` が行います。値を文字列化して前後の空白を除き、最初の `.` または `@` 以降を削り、`_` を `-` に置き換えます。先頭要素が2〜3文字のASCII英字なら小文字の言語コードとして採用し、それ以降で最初に見つかる2文字のASCII英字を大文字の地域コードとして採用します。例: `de-DE` / `de_DE.UTF-8` は `locale: "de-DE", region: "DE"`、`ja` は `locale: "ja", region: null` です。空、`C`、`POSIX`、言語要素が不正な値は locale と region が `null` になります。大文字小文字を区別するのは `C` / `POSIX` 判定だけで、同判定は大文字小文字を区別しません。数値変換や範囲 clamp はありません（`apps/host/server/region.mjs:14-22,63`）。

無効なタグも非空ならテスト値の分岐に入ります。その場合は null の locale / region、null の currency、`source: 'test'` を返し、OS 検出へ fallback しません。空文字だけは分岐に入らず、OS 検出に進みます（`apps/host/server/region.mjs:63-65`）。

## 有効になる条件

- Strata host の `/api/locale` 経路が `systemLocale()` を呼ぶ場合に使われます。GPU backend、モデル状態、CLI 引数には依存しません（`apps/host/server/index.mjs:1951`）。
- `STRATA_PACKAGED` が文字列として厳密に `1` のときだけ無効です。未設定、空文字、`0` などはこのガードを通過します（`apps/host/server/region.mjs:63`）。
- Monitor の電気料金表示では、返された region に対応する自動通貨の選択に使われます。後段で Settings の通貨 override が指定されていれば、その override が自動検出通貨より優先されます（`apps/host/src/lib/currency.ts:54-66`; `apps/host/src/components/ElectricityPrice.tsx:12-27`）。テスト値による currency 自体の指定はなく、地域別通貨が解決できない場合の後続 fallback は同 resolver によります。

## 実行時の詳細

`systemLocale()` は `/api/locale` リクエストの処理中に呼ばれます。テスト値の有無はその呼び出しごとに確認し、テスト値の結果自体はサーバー側で cache しません。したがって、実行中に環境値を変えた場合、次の `systemLocale()` 呼び出しで反映されます。テスト値が使われず OS 検出へ進んだ場合は `cached ??= detectRegion()` で検出結果を cache します（`apps/host/server/region.mjs:58-65`）。フロントエンド側は `/api/locale` の最初の取得 Promise を module 変数 `asked` に保存して再利用するため、同じ画面プロセス内で後から環境を変えても通常は再取得しません（`apps/host/src/lib/money.ts:7-18`）。

API は `systemLocale()` の戻り値を JSON の HTTP 200 応答として返します。テスト値のパース失敗について専用ログ、警告、例外終了はありません。OS 検出へ進んだ場合の例外も `detectRegion()` 内で捕捉され、全フィールド null の結果になります（`apps/host/server/index.mjs:1951`; `apps/host/server/region.mjs:32-55`）。

## 根拠

- 読み取り、`STRATA_PACKAGED` ガード、test source 設定、OS 検出 cache: `apps/host/server/region.mjs:58-65`
- locale タグ変換規則: `apps/host/server/region.mjs:14-22`
- API 応答: `apps/host/server/index.mjs:1951`
- フロントエンドの取得 cache: `apps/host/src/lib/money.ts:7-18`
- 地域情報からの通貨解決と Settings override の優先順位: `apps/host/src/lib/currency.ts:54-66`
- Monitor の表示用途: `apps/host/src/components/ElectricityPrice.tsx:8-27`

`docs/DETAILS.md` にこの環境変数やホストの地域情報 API の説明は見つからず、上記の挙動はコードから確認しました。
