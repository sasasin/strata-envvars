# `STRATA_COMPACTION_HEADROOM_FRACTION`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の Host agent が会話の compaction 開始位置を計算するとき、モデルの context window から reply 用予算を引いた残りに対する headroom の割合を指定します。設定値が `f` の場合、Strata はその残りに `f` を掛けて切り捨て、さらに headroom を 512〜65,536 token に収めます。既定の割合は `0.125` です。計算結果はモデルごとの compaction policy として agent profile に入り、ローカルモデルの送信前 fit 判定にも使われます（`app/host/server/agent/profile.mjs:162-170,209-225,332-367,416`、`app/host/server/agent/agent-bridge.mjs:1846-1868`）。

この値は compaction 自体を有効化するスイッチではありません。Strata が算出する headroom と threshold に影響します。threshold は別の `STRATA_COMPACTION_THRESHOLD_RATIO` による pressure threshold と、reply 予算・headroom 後の空きのうち小さい方です（`app/host/server/agent/profile.mjs:172-177,222-225`）。

## 値と判定

Strata は `process.env.STRATA_COMPACTION_HEADROOM_FRACTION` を `Number.parseFloat` で数値化し、有限かつ `0 <= 値 <= 0.5` の場合に採用します。それ以外は既定値 `0.125` に戻ります（`app/host/server/agent/profile.mjs:209-215`）。

| 条件 | unset | 有効になる値（例） | 無効になり既定値になる値（例） |
|---|---|---|---|
| 保存済みの Chat 設定が未選択（null） | `0.125` | `0`、`0.125`、`0.5` | 空文字、`-0.01`、`0.5001`、`x`、`Infinity` |
| 保存済みの Chat 設定に有効な headroom がある | 環境変数を参照しない | 保存値 `0..0.5` が採用される | 保存値が無効なら未選択として扱い、環境変数に進む |

`parseFloat` は文字列全体の厳密な検証ではありません。先頭の空白は数値変換時に許容され、数値の後ろに文字が続いても数値部分を採用します。そのため `0.2junk` は `0.2` として有効、`0x1` は先頭の `0` として有効です。`true` や `1` は有効な割合ではなく、`1` は範囲外なので既定値になります。大文字小文字の比較はありません（`app/host/server/agent/profile.mjs:213-215`）。

## 有効になる条件

- Host server の agent profile でモデル別 compaction policy を組み立てる経路では、その時点の環境値（または保存値）から headroom token 数が算出されます。ローカル・外部 API connection の各モデルに policy が追加されます（`app/host/server/agent/profile.mjs:314-322,332-367,373-416`）。
- ローカルモデルの送信前 fit 判定では `compactionThreshold` が同じ headroom 計算を呼び出します（`app/host/server/agent/agent-bridge.mjs:1846-1868`）。
- ユーザーが Settings の compaction 値を保存している場合、その有効な `headroomFraction` が環境変数より優先されます。API の `null` は自動選択に戻し、数値は `0..0.5` の範囲で検証されます（`app/host/server/index.mjs:247-248,2056-2069`）。
- headroom が増えても最終 threshold が必ず同じだけ下がるわけではありません。`thresholdRatio` 側の値がより小さい場合はそちらが threshold を決めます（`app/host/server/agent/profile.mjs:222-225`）。
- OS、GPU backend、build macro による分岐は、確認したこの読み取り・計算経路にはありません。Strata の compaction policy が実際に実行される時期や、その後の compaction 内部処理は外部 Harness 側の責務であり、ここでは Strata の挙動として補いません。

## 実行時の詳細

`headroomFraction(env = process.env)` は呼び出し時に `chosen.headroomFraction` を確認し、保存値が `null` ならその呼び出しの `env`（通常は `process.env`）を読みます。環境値を関数内 static などに保存する処理はありません。したがって保存値が未選択なら、プロセス稼働中に `process.env` が変わった後の呼び出しにも新しい値が使われます。一方、保存値が選択済みなら環境変数は参照されません（`app/host/server/agent/profile.mjs:184-215`）。

Host 起動時に store の `agentChat` 設定を `setCompactionChoice` に渡し、`/api/agent/compaction` の POST は検証後に store を更新して同じプロセス内の選択値も更新します。GET は保存値、実効値、既定値、値の出所（`setting` / `environment` / `default`）を返します（`app/host/server/index.mjs:247-270,2047,2056-2069`）。設定 POST の不正値は HTTP 400 と `headroomFraction is a fraction between 0 and 0.5, or null for automatic.` を返します。環境変数の不正値は警告を出さず `0.125` にフォールバックします（同 `profile.mjs:211-215`、`index.mjs:2060-2065`）。

Strata の headroom 計算は `room = max(0, context - outputBudget)` に割合を掛けて切り捨て、その値を 512〜65,536 token に clamp します。context が有限の正数でなければ計算上の window は 32,768 です。threshold は window が有限の正数でなければ同じく 32,768 とし、`floor(min(window * thresholdRatio, window - outputBudget - headroom))` で求めます（`app/host/server/agent/profile.mjs:167-169,222-225`）。

## ログと測定値

環境変数の不正値や既定値へのフォールバックについて、Strata は専用ログを出しません。Settings 用 `GET /api/agent/compaction` の `source.headroomFraction` は環境値が有効なら `environment`、未設定・無効値なら `default`、保存値が有効なら `setting` を示し、`effective.headroomFraction` に適用値を返します（`app/host/server/index.mjs:259-270,2047`）。測定値は記載しません。

## 根拠

- 値の取得・優先順位・既定値: `app/host/server/agent/profile.mjs:184-215`
- headroom と threshold の算出: `app/host/server/agent/profile.mjs:162-170,222-225`
- モデル別 policy の作成: `app/host/server/agent/profile.mjs:314-322,332-367,373-416`
- ローカル送信前 fit 判定: `app/host/server/agent/agent-bridge.mjs:1846-1868`
- 起動時選択、設定 API、出所の表示: `app/host/server/index.mjs:247-270,2047,2056-2069`
