# `SCHEME`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`apps/desktop/scripts/ui-flows.mjs` のヘッドレス UI フローで、新しい Playwright browser context の `colorScheme` 初期値を指定します。Strata のデスクトップアプリやサーバーの通常設定として読む箇所は見つかりませんでした。

## 値と判定

| `SCHEME` | スクリプトの処理 |
|---|---|
| 未設定 | `colorScheme` を環境変数からは指定しない |
| 空文字 | JavaScript の falsy 判定により指定しない |
| 空でない文字列 | 文字列をそのまま `colorScheme` 値として渡す |

文字列の trim、大小文字変換、値域検証、既定値の設定はこのスクリプトにはありません。文字列の意味や不正値に対する Playwright 側の動作は Strata の処理ではないため、ここでは断定しません。読み取りは `newPage()` を呼ぶたびに行われ、スクリプト内でキャッシュされません。

## 有効になる条件

このスクリプトを Node.js で実行し、該当する `newPage()` 呼び出しで context を作る場合に限ります。`newPage()` の `options` に `colorScheme` が渡されると、その値は環境変数由来の値より優先します。`ui2` / `ui2d` シナリオと `theme` シナリオは `light` / `dark` を明示して呼ぶため、`SCHEME` の値で上書きされません。また、restart シナリオは `newPage()` を通さず persistent context を作るため、この読み取りの対象外です。

## 実行時の詳細

`newPage()` は browser context の生成時に `process.env.SCHEME` を評価し、値が truthy の場合だけ `{ colorScheme: process.env.SCHEME }` をオプションに加えます。その後 `...options` を展開するため、呼び出し側の同名オプションがあれば上書きされます。未指定または空文字の場合にこのコードが指定する値はなく、context 作成時にエラーを処理・記録する専用経路もありません。

値が個別指定で上書きされない `newPage()` 呼び出しは `apps/desktop/scripts/ui-flows.mjs:192,237,278,413,496,521,546,593,617,646` です。値を明示して上書きする呼び出しは同ファイルの `331,708` 行です。環境変数を読む箇所は同ファイルの `171` 行だけで、他の Strata ソースに `SCHEME` の環境値読み取りはありません。

## 根拠

- `apps/desktop/scripts/ui-flows.mjs:3-14` はスクリプトを fake installer / fake engine を使う installed-app の headless UI flow と説明し、テスト失敗時に終了コード 1 としています。
- `apps/desktop/scripts/ui-flows.mjs:170-177` は context を作る `newPage()`、`SCHEME` の truthy 判定、`options` による後勝ちの上書きを実装しています。
- `apps/desktop/scripts/ui-flows.mjs:329-332,705-714` は `ui2` / `ui2d` と `theme` の各シナリオが `colorScheme` を明示することを示します。
- `apps/desktop/scripts/ui-flows.mjs:677-702` は restart シナリオが `launchPersistentContext()` と `context.newPage()` を直接使うことを示します。
- 調査対象リポジトリの `git status --short --branch` は `## main...origin/main` で、調査開始時点に未コミット変更はありませんでした。
