# `HEIGHT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata 同梱の画面キャプチャ用スクリプト `apps/host/scripts/language-shots.mjs` が、新規 Playwright page に設定する viewport の高さを指定します。これは Strata engine やサーバーの環境変数ではなく、`apps/host` の言語別スクリーンショット作成経路で使う値です。同スクリプトは `npm run build` 後に `node scripts/language-shots.mjs ...` として実行します（`apps/host/scripts/language-shots.mjs:3-7`, `apps/host/README.md:24`）。

## 値と判定

スクリプトは `process.env.HEIGHT ?? 800` の結果を JavaScript の `Number(...)` に渡します。未設定なら既定値 `800` を使用します。空文字は nullish ではないため既定値に置き換わらず、`Number("")` の結果 `0` が渡されます。数値文字列は数値へ変換され、小数、負数、空白文字列、数値でない文字列などもスクリプト側では検査・丸め・clamp されません。たとえば数値でない文字列は `NaN` になります。

| `HEIGHT` | スクリプトが viewport height に渡す値 |
|---|---:|
| 未設定 | `800` |
| `"720"` | `720` |
| `""` | `0` |
| `"720.5"` | `720.5` |
| `"-1"` | `-1` |
| 数値に変換できない文字列 | `NaN` |

これらは `Number` までの Strata スクリプト上の変換結果です。受け取った Playwright/browser が範囲外や `NaN` をどう扱うかは外部側の動作なので、本調査では規定しません。

## 有効になる条件

- `apps/host/scripts/language-shots.mjs` を実行し、Playwright の page 作成まで到達した場合に限り使われます。
- CLI 引数に viewport 高さの指定はありません。言語、出力先、route の引数とは独立しており、他の環境変数による `HEIGHT` の上書きもこのスクリプトにはありません。
- `HEIGHT` が設定されていても、ビルド済み `dist/index.html` がない場合や Chrome/Edge が見つからない場合は、それぞれ `Run npm run build first.`、`No Chrome or Edge found; set CHROME.` を stderr に出して終了し、viewport 設定には到達しません（同ファイル `:20-22`）。

## 実行時の詳細

環境変数は各スクリプト実行中、新しい page を作る箇所で直接読み取られます。値を static cache する処理や再読込する処理はありません。高さは `width` と並べて `browser.newPage({ viewport: ... })` に一度渡され、その page で route を順に開いて PNG を保存します（`apps/host/scripts/language-shots.mjs:47-59`）。スクリプトは子プロセス起動時に親環境を継承しますが、その子プロセス環境を組み立てる処理は `HEIGHT` を別値で設定しません（同ファイル `:26-30`）。

`HEIGHT` 専用のログ、警告、fallback、終了処理はありません。スクリプト自身は変換結果を検査せず page 作成 API に渡します。従って高さが受理されない値の場合のエラーや終了挙動は、Playwright/browser 側の処理に依存し、Strata のコードからは特定できません。

## 根拠

- `apps/host/scripts/language-shots.mjs:9` — `HEIGHT` と既定値 `800` の説明。
- `apps/host/scripts/language-shots.mjs:47-49` — `Number(process.env.HEIGHT ?? 800)` を viewport height として page 作成へ渡す唯一の読み取り箇所。
- `apps/host/scripts/language-shots.mjs:20-22,53-59` — page 作成前の明示的終了経路と、その後の画面遷移・PNG 保存。
- `apps/host/README.md:24` — 言語別スクリーンショットスクリプトの利用方法。
