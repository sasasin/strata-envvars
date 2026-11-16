# `STRATA_TEST_TIMEOUT_MS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`apps/host` のテストランナー `scripts/test.mjs` が Node.js の `node --test` に渡す、各テストのタイムアウト値（ミリ秒）を決める。`npm test` のテスト実行にだけ使われ、Strata の通常のホスト／エンジン実行時間は制御しない。既定値は 600,000 ms（10 分）。このスクリプトは対象ファイルを列挙して `node --test --test-timeout=<値>` を起動し、標準入出力を継承する。`apps/host/package.json` の `test` script がこのランナーを呼び出す。 (`apps/host/scripts/test.mjs:1-7,17-21`, `apps/host/package.json:20-26`, `apps/host/README.md:22-27`)

## 値と判定

値は `Number(process.env.STRATA_TEST_TIMEOUT_MS) || 600000` で一度数値化する。文字列全体を JavaScript の `Number` で変換し、`parseInt` のように整数部分だけを読む処理ではない。変換結果が `0`、`-0` または `NaN` に相当する falsy 値なら 600,000 に戻す。変換結果の範囲・整数性をスクリプト側で検査または clamp する処理はない。 (`apps/host/scripts/test.mjs:18-19`)

| 条件 | unset | 既定値になる例 | `node --test` に渡される値の例 |
|---|---|---|---|
| `npm test` を直接実行 | `process.env` は `undefined`。600000 | 空文字、`0`、`-0`、`false`、`true`、`0anything`、数値に変換できない文字列。いずれも最終的に 600000 | `1` → `--test-timeout=1`、`1.5` → `--test-timeout=1.5`、`-1` → `--test-timeout=-1`。スクリプトは正負や小数を検査しない |
| `tools/check` の `host-test` step 経由 | 呼び出し元の設定にかかわらず、子プロセス環境を `180000` に上書き | 該当なし（同 step は常に `180000` を設定） | `--test-timeout=180000` |

`Number` 変換なので、空白だけの文字列や `0.0` も 0 となり既定値になります。文字列全体が数値として変換できない場合は `NaN` となって既定値に戻ります。負数、小数、`Infinity` のように falsy でない変換結果はそのまま文字列化されて引数になります。Node.js がその引数をどう受理するかはこの Strata コードでは検証していません。 (`apps/host/scripts/test.mjs:18-19`)

## 有効になる条件

- `apps/host` で `npm test` を実行し、`scripts/test.mjs` が起動されること。`package.json` では `test` script が `node scripts/test.mjs` に結び付いている。 (`apps/host/package.json:26`)
- `tools/check` 経由では `host-test` step が対象であり、Node.js が利用可能かつ `v24.12` 以上、npm が存在し、依存関係が利用可能であること。満たさない場合は host test は開始されず、この変数もその実行では使われない。 (`tools/check:136-147,350-367`)
- `tools/check` は `host-test` 子プロセス環境に `STRATA_TEST_TIMEOUT_MS=180000` を明示設定するため、呼び出し元から渡した値よりこの値が優先される。`tools/check --timeout-scale` が調整するのは step 全体の外側の上限であり、同変数の 180000 ms は変えない。 (`tools/check:46-49,77-83,378-382,443-444,469`)
- OS、GPU backend、モデル状態による Strata エンジン側の条件は該当しない。これは Node.js のホストテストランナー用設定である。Windows では同スクリプトが PowerShell module path を調整する別分岐があるが、timeout 値の読み取り・指定は共通である。 (`apps/host/scripts/test.mjs:14-19`)

## 実行時の詳細

`scripts/test.mjs` は起動時に環境変数を一度読み、`timeout` に数値化した値を保持して子プロセスの起動引数へ組み立てる。ファイルごとに再読込する処理やキャッシュ更新処理はなく、実行中の環境変更はこの起動引数を変えない。対象は `apps/host/tests` 直下にある `.test.mjs` ファイルで、名前順に列挙される。追加の CLI 引数は `--test-timeout` の後ろに `node --test` へ渡される。 (`apps/host/scripts/test.mjs:6-7,17-21`)

`tools/check` の `host-test` step は通常の子環境コピーに加えて値を `180000` に設定してから `npm test` を起動する。この step には別に既定 1800 秒の外側 timeout があり、`--timeout-scale` で倍率変更される。外側上限に達すると `run_cmd` は子プロセス群を終了し、ログに `[tools/check: timed out after %d s, killed]` を記録する。これは `STRATA_TEST_TIMEOUT_MS` が指定する per-test 値とは別の上限である。 (`tools/check:46-49,77-83,91-123,378-382,443-444`)

## ログと測定値

ランナーは `node --test` の標準入出力を継承し、子プロセスの起動エラーを `console.error(error.message)` で出力して終了コード 1 を設定する。正常に起動した場合は Node の終了コードを親プロセスの終了コードに設定し、signal 終了なら 1 とする。timeout 時にテスト失敗として Node が出力する内容は Node.js 側の処理であり、この文書では Strata のログ文言として扱わない。 (`apps/host/scripts/test.mjs:19-21`)

`apps/host/README.md` は `npm test` について、ハングしたテストは 10 分後に失敗すると説明している。これはランナーの既定値 600000 ms と一致する。`tools/check` は別途 180000 ms を環境へ設定する。`docs/DETAILS.md` にこの変数の記載は見つからなかった。 (`apps/host/README.md:22-27`, `apps/host/scripts/test.mjs:17-19`, `tools/check:378-382`)

## 根拠

- `apps/host/scripts/test.mjs:1-21` — 対象テストファイル、設定値の変換、Node CLI 引数、標準入出力・終了コード。
- `apps/host/package.json:20-26` — `npm test` とランナースクリプトの対応。
- `apps/host/README.md:22-27` — 利用者向けの 10 分既定値の説明。
- `tools/check:46-49,77-83,91-123,136-147,350-367,378-382,443-444,469` — step timeout、環境コピーと上書き、host test の実行条件。
