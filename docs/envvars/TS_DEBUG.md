# `TS_DEBUG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、`git status --short --branch` に未コミット変更は表示されなかった。

## 役割

ホストサーバーの新しい Time-skip fork 処理で、計画から「lever」を選ぶモデル応答、またはその応答要求の失敗メッセージを `console.log` に出す診断用フラグです。Strata の推論エンジンや通常の生成処理の設定ではなく、lever が選ばれるかどうかや、その結果を変更しません。ソース内の `TS_DEBUG` 参照は `apps/host/server/timeskip-fork.mjs` の1か所（1行）で、helper 経由や動的な環境変数名による読み取りはありません。

## 値と判定

文字列や数値への変換はせず、JavaScript の真偽値判定を使います。

| `process.env.TS_DEBUG` | 判定 | この箇所での動作 |
|---|---|---|
| 未設定（`undefined`） | false | 診断ログを出さない |
| 空文字（`""`） | false | 診断ログを出さない |
| 空でない文字列 | true | 診断ログを出す。`0`、`false`、`no` も true |

無効値の parse、既定値からの変換、数値境界はありません。CLI 引数や別環境変数による上書きもこの処理にはありません。

## 有効になる条件

このフラグの参照箇所に到達するのは、新しい Time-skip fork の計画が3ステップ以上で、lever をモデルに問い合わせる場合です。サーバーの `/api` Time-skip 経路は `forkTs.start()` を呼び、fork の `runFlow()` がその問い合わせを行います（`apps/host/server/index.mjs:1137-1150`, `apps/host/server/timeskip-fork.mjs:141-162,253-263`）。計画が2ステップ以下なら問い合わせ自体がなく、この変数によるログもありません。

OS、CUDA/HIP/SYCL backend、build macro、推論モデルのローカル/remote 選択による分岐は、この環境変数の判定にはありません。モデル選択や thinking 値は問い合わせ引数ですが、`TS_DEBUG` の判定値を変えません。

## 実行時の詳細

lever 問い合わせは `ask()` が `agent.runTurn()` を実行し、delta frame のテキストを連結して返します。問い合わせ成功時は、`TS_DEBUG` が truthy なら応答文字列を `JSON.stringify()` した先頭300文字を `lever said:` に続けてログ出力し、その後に通常どおり `parseLever()` で解釈します。応答が lever として不正でも、このログ出力自体は行われます（`apps/host/server/timeskip-fork.mjs:47-57,107-110,159-165`）。

問い合わせが例外で失敗した場合、truthy なら例外の `message` を `lever failed` に続けて出力します。その後は `lever = null` とし、通常どおり `defaultLever()` による既定選択に進みます。この環境変数自体は終了、失敗、fallback を発生させず、ログの有無だけを制御します（`apps/host/server/timeskip-fork.mjs:159-164`）。

値は `runFlow()` 内の各問い合わせ結果または例外処理時に `process.env.TS_DEBUG` から直接参照され、static/cache への保存はありません。Strata のコードにこの値を子プロセスへ転送する処理は見つかりませんでした。ログは `console.log` 呼び出しで出力されます。

## 根拠

- 全参照検索: `apps/host/server/timeskip-fork.mjs:161`。候補一覧には名前が載っています（`docs/envvars/000_envvers.md:1686`）。
- Time-skip の lever 問い合わせ、成功・失敗時の判定とログ: `apps/host/server/timeskip-fork.mjs:107-110,141-165`。
- lever 応答の検証と不正応答の扱い: `apps/host/server/timeskip-fork.mjs:47-57,159-165`。
- 新しい Time-skip API から fork 実装を起動する経路: `apps/host/server/index.mjs:1137-1150`; fork factory の生成: `apps/host/server/index.mjs:905-906`。
- `docs/DETAILS.md` および `STRATA_ADAPT_OVERLAP.md` に `TS_DEBUG` の説明は見つかりませんでした。
