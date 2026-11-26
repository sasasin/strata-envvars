# `MOCK_PORT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`MOCK_PORT` は、ホストアプリのテスト用ローカル API モックを単独起動するときに、ループバック上で待ち受けるポート番号を指定する。参照は `app/host/tests/mock-model-api.mjs` の直接実行ブロックだけにあり、engine や通常のアプリ起動設定ではない。同ファイルを import してテストから `createMockModelApi()` を呼ぶ場合はこの環境変数を読まず、引数省略時のポート `0` を使う（同ファイル:4,45-48）。

## 値と判定

直接実行時は `process.env.MOCK_PORT ?? 5181` の結果を `Number(...)` に渡す。未設定の場合だけ既定値 `5181` となる。空文字は nullish ではないため既定値に置き換わらず、`Number("")` の結果 `0` が渡る。文字列全体を数値変換し、先頭文字だけの判定や `parseInt` は行わない（`app/host/tests/mock-model-api.mjs:45-46`）。

| 条件 | unset | 有効になる値（変換結果の例） | 無効・境界となる値の扱い |
|---|---|---|---|
| ファイルを直接実行 | `5181` | `"1"` → `1`、`"0"` → `0`、`" 12 "` → `12` | `""` と空白だけの文字列は `0`、`"true"`・`"false"`・`"0anything"` は `NaN` に変換され、その値をそのまま待受 API に渡す。負数・小数・`65536` などについて Strata 独自の範囲・整数検査や clamp はない。 |
| `createMockModelApi()` を import して引数省略で呼ぶ | `MOCK_PORT` を読まない | 引数省略時の `0` | `MOCK_PORT` はこの呼び出し経路に適用されない。 |

ここでの「有効」は Strata が数値変換して待受処理へ渡すことを指す。変換後のポート値の受理範囲や `NaN` 等に対するエラー動作は Node.js の `server.listen` 側に属し、このコードでは検証・fallback を実装していない（同ファイル:4,42,45-46）。

## 有効になる条件

- `app/host/tests/mock-model-api.mjs` が Node.js のエントリーポイントとして直接実行され、`process.argv[1]` が存在し、`import.meta.url` がそのパスの file URL と一致すること。この条件を満たすと環境変数を読み、値を `createMockModelApi` に渡す（同ファイル:45-46）。
- モジュールを import する経路では、直接実行ブロックが動かないため `MOCK_PORT` は参照されない。テスト群は同モジュールの `createMockModelApi` を import して使っている（`app/host/tests/api-reasoning-effort.test.mjs:11,17`、`app/host/tests/model-providers.test.mjs:7,33`、`app/host/tests/user-rules.test.mjs:12,75`）。
- OS、GPU backend、build macro、サーバーモード、CLI 引数、モデル状態、他の環境変数による追加条件は、この読み取り箇所にはない。

## 実行時の詳細

環境変数は直接実行ブロックが評価される際に一度読み取られ、`Number` の結果を `createMockModelApi` に明示的に渡すため、関数側の引数既定値 `0` はこの経路では使われない。モジュール読み込み時に保存する cache や、後から環境変数を再読込する処理はない（`app/host/tests/mock-model-api.mjs:4,45-46`）。

関数は `127.0.0.1` を bind address として `server.listen` を呼び、待受開始後に実際の bound port を含む `baseUrl` を返す。直接実行経路はその URL を `Mock model API: ...` として標準出力へ表示する。コード内に別ポートへの再試行や変数値の警告・fallback はない（`app/host/tests/mock-model-api.mjs:42-48`）。

## ログと測定値

測定値に関する記述はない。待受開始後に `Mock model API: ${mock.baseUrl}` を `console.log` する（`app/host/tests/mock-model-api.mjs:47`）。待受処理に渡す値の事前検証や、失敗時の専用ログ・catch/fallback はこのファイルにない（同ファイル:42-47）。

## 根拠

- `app/host/tests/mock-model-api.mjs:1-4` — モック API の用途コメントと関数の引数既定値。
- `app/host/tests/mock-model-api.mjs:42-48` — loopback bind、base URL、直接起動条件、環境変数の読み取り、表示。
- `app/host/tests/api-reasoning-effort.test.mjs:11,17`、`app/host/tests/model-providers.test.mjs:7,33`、`app/host/tests/user-rules.test.mjs:12,75` — テストからの import と関数呼び出し。
