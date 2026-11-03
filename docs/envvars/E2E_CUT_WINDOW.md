# `E2E_CUT_WINDOW`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata 同梱の agent lost end-to-end スクリプト (`apps/host/scripts/agent-lost-e2e.mjs`) で、`cut` シナリオが agent bridge に伝えるローカルモデルの context window 値を指定します。Strata の engine に渡す `--max-context` は別変数 `E2E_WINDOW` で決まり、この変数では変更しません。通常の Strata CLI やサーバーの設定として読み取る箇所はありません。

## 値と判定

スクリプト共通の `env(name, fallback)` は `process.env[name] ?? fallback` を返し、cut シナリオで `Number(...)` に変換します。nullish fallback のため、空文字は未設定扱いになりません。文字列を整数に限定する検証や範囲制限はありません。

| 環境値 | cut bridge に渡す値 | 結果 |
| --- | ---: | --- |
| 未設定 | `24000` | 既定値を使用 |
| `24000` | `24000` | 数値化して使用 |
| 空文字 | `0` | 0 を渡す（既定値には戻らない） |
| 空白だけ | `0` | `Number` の変換結果を渡す |
| 数値にできない文字列 | `NaN` | `NaN` を渡す。スクリプト側の検証・fallback はない |
| 小数、負数、`Infinity` 等 | `Number` の変換結果 | 整数化、clamp、拒否はしない |

## 有効になる条件

スクリプト実行時に引数なしで起動した場合は全シナリオが対象となり、または CLI 引数に `cut` を指定した場合にこの環境変数が読み取られます。他のシナリオだけを指定した場合は読みません。値は cut bridge の作成時に一度読み取られ、同じ実行中に環境値を変更しても作成済み bridge の値は更新されません。

環境値の設定がなくても `cut` を実行できます。別の `E2E_WINDOW` は engine 起動時の `--max-context` と最初の bridge に使われます。cut bridge のみ `E2E_CUT_WINDOW` を使うため、両者は独立しています。

## 実行時の詳細

cut シナリオは既存 bridge を閉じた後、`E2E_CUT_WINDOW`（未設定時 `24000`）を数値化して `makeBridge` に渡します。`makeBridge` はその値を `localInstances` のモデル `context` として agent bridge に渡します (`apps/host/scripts/agent-lost-e2e.mjs:100-108,194-199`)。Strata の `buildProfile` はローカルモデルの `contextWindow` にこの値を設定し、`maxTokens` を `localOutputBudget(context)` で計算します (`apps/host/server/agent/profile.mjs:220-247`)。有限かつ正の context なら予算は `max(4096, min(32768, floor(context * 0.3)))` です。既定の 24000 では 7200 になります。context が有限でないか正でない場合、出力予算計算だけは 32768 を代用しますが、profile の `contextWindow` 自体には入力値が残ります (`profile.mjs:137-144,226-247`)。

このシナリオは長いファイル書き込みを agent bridge に依頼し、受信 frame に cut 通知があること、その通知文に `length limit` が含まれること、さらに出力ファイルが存在することを検査します。各結果は stdout に PASS/FAIL として出力され、`result.json` に保存されます。いずれかの検査が失敗すればスクリプトは終了コード 1 になります (`apps/host/scripts/agent-lost-e2e.mjs:110-137,199-209`)。外部 Harness が実際に応答を切る条件や内部処理は、この変数の Strata 側の実装事実には含めません。

## 根拠

- `apps/host/scripts/agent-lost-e2e.mjs:29-41` — 共通 env helper の nullish fallback、他の E2E 値、シナリオ選択。
- `apps/host/scripts/agent-lost-e2e.mjs:100-108,194-199` — bridge のモデル context としての受け渡し、cut bridge 作成時の読み取り。
- `apps/host/scripts/agent-lost-e2e.mjs:199-209` — cut 結果の確認、JSON 結果保存と終了コード。
- `apps/host/server/agent/profile.mjs:137-144,220-247` — context 値からの出力予算計算と local model profile への設定。

`docs/DETAILS.md` にこの E2E 専用変数の説明は見つかりませんでした。候補一覧 `docs/envvars/000_envvers.md` の掲載と実装は一致しますが、用途は通常利用者向けの engine 設定ではなく、同梱 E2E スクリプトに限定されています。
