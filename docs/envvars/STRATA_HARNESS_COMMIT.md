# `STRATA_HARNESS_COMMIT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Desktop 配布物にステージする DeepSeek Harness の commit を、生成物 `BUNDLE.json` の provenance 情報として記録します。Harness の機能や Strata の実行時設定を切り替える用途ではありません。この値を読む Strata 所有コードは `apps/desktop/scripts/stage-harness.mjs` のみです。同スクリプトは `apps/desktop/package.json` の通常の `build` script からは呼ばれず、ソース checkout を指定して個別に実行する staging 用スクリプトです。

## 値と判定

値は文字列として読み、形式、長さ、SHA であることの検証や trim はしません。

| `STRATA_HARNESS_COMMIT` | 採用する `commit` |
|---|---|
| 未設定 | `src` checkout で実行した `git rev-parse HEAD` の結果（成功時） |
| 空文字 | 未設定と同じく `git rev-parse HEAD` に fallback |
| 空白を含む文字列など、空でない値 | 環境変数の文字列をそのまま採用 |
| `git rev-parse HEAD` が失敗し、環境変数も未設定または空 | `null` |

`process.env.STRATA_HARNESS_COMMIT ?? null` の後、JavaScript の truthiness で fallback を判定します。そのため空文字は fallback しますが、空白だけの値や任意の非空文字列は採用されます。短縮 SHA や無関係な文字列でも拒否されず、値の正しさは検証されません。

## 有効になる条件

`apps/desktop/scripts/stage-harness.mjs` を実行したときだけ参照されます。ソース Harness checkout は `--src` または `STRATA_HARNESS_SRC` で指定し、出力先は `--out` で指定できます。`--src` がない場合や checkout 内の `apps/cli/lib/bin.js` がない場合は案内を stderr に出し、終了コード 2 で停止します。このスクリプトに `--commit` 引数はなく、commit 値に対する CLI 上書きはありません。`--src` は対象 checkout の選択に使われ、明示された `STRATA_HARNESS_COMMIT` との一致確認はしません。

## 実行時の詳細

スクリプトはまず出力先を作り直し、`pnpm deploy --legacy --prod` などで Harness をステージします。その後 `STRATA_HARNESS_COMMIT` を一度読み、値が空なら `git rev-parse HEAD` を `cwd: src` で同期実行します。Git 成功時は stdout を trim して採用し、失敗時は `null` のまま進みます。選んだ値は `BUNDLE.json` の `commit` フィールドに書かれます。最終ログではその値の先頭8文字だけ（値が `null` なら `no commit`）を表示します。

環境変数はステージングスクリプト実行中に読み取られ、生成後の Harness プロセスがこの値を読み直す実装はありません。読み取り結果を環境変数へ書き戻したり、Harness の起動引数として渡したりもしません。値は起動時・リクエストごとに評価される Strata 実行時設定ではありません。

ほかの失敗経路では、`pnpm deploy` 失敗時にコマンドと status/error を stderr に出して終了コード 1、ステージ済み Harness の `--version` 起動失敗時に stderr を出して終了コード 1 になります。これらは stage 処理全体の失敗であり、commit 値そのものの検証エラーではありません。

## 根拠

- `apps/desktop/scripts/stage-harness.mjs:24-30` — `--src` と `STRATA_HARNESS_SRC` の選択、および checkout 不備時の終了。
- `apps/desktop/scripts/stage-harness.mjs:33-43` — 同期コマンド実行と `pnpm deploy` の失敗処理。
- `apps/desktop/scripts/stage-harness.mjs:155-165` — `STRATA_HARNESS_COMMIT` の読み取り、Git HEAD fallback、`BUNDLE.json` への記録。
- `apps/desktop/scripts/stage-harness.mjs:169-181` — ステージ検証、commit 先頭8文字を含むログ、起動失敗の処理。
- `apps/desktop/package.json:7-15` — Desktop の npm scripts。通常の `build` script から staging script は呼ばれていない。

