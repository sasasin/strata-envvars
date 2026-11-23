# `STRATA_COMPACTION_THRESHOLD_RATIO`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata のホストアプリにある Harness エージェントの会話要約（compaction）開始比率を指定する。比率の既定値は `0.8`、有効範囲は `0.1` 以上 `0.99` 以下。Strata はモデルごとの Harness プロファイル `modelPolicies` に比率を含める。またローカルモデルへの送信前に行うコンテキスト適合判定も、同じ比率を使った閾値を参照して、必要なら古い会話を先に要約する。プロファイル生成部と判定処理は `app/host/server/agent/profile.mjs:172-177,203-207,217-225,314-324,338-368,373-417`、Harness の compaction 設定組み立ては `app/host/server/agent/preset.mjs:95-102` にある。

これは Strata ホストの JavaScript サーバーが読む設定であり、Strata の C++/GPU エンジン設定ではない。ホストの設定 API でユーザーが比率を保存すると、その保存値が環境変数に優先する。対象名の実行コード参照は `app/host/server/agent/profile.mjs:205` と `app/host/server/index.mjs:269`。同ファイル内の他の直接一致はコメントで、テスト内の一致は実装根拠に含めていない。

## 値と判定

`thresholdRatio(env = process.env)` は環境オブジェクトの `STRATA_COMPACTION_THRESHOLD_RATIO` を `Number.parseFloat` に渡し、有限数かつ `[0.1, 0.99]` の範囲内なら採用する。それ以外は既定値 `0.8`。文字列全体の数値変換ではないため、先頭の数値を parse できれば後続文字は検査されない。空白は `parseFloat` の規則で処理される。大文字小文字の比較はない。根拠: `app/host/server/agent/profile.mjs:177,203-207`。

| 条件 | unset | 有効になる値（例） | 無効値の例と結果 |
| --- | --- | --- | --- |
| 保存済みのアプリ設定が無効または未選択 | 環境変数を評価し、値がなければ `0.8` | `0.1`, `0.8`, `0.99`; `0.8tail` も `parseFloat` が `0.8` を返すため有効 | 空文字、`0`, `0.099`, `1`, `-0.8`, `abc` は既定値 `0.8` |
| 保存済みのアプリ設定が有効 | 環境変数より保存値を優先 | 設定 API では `0.1`〜`0.99` を含む有限数 | 範囲外や parse 不能な保存値は有効な選択として扱われず、環境変数へ戻る |

保存値は `compactionNumber` で検証され、`null`、未設定、空文字、boolean、有限でない数、範囲外は有効値にならない。文字列の場合は同じく `Number.parseFloat(String(value))` なので、数値の後ろの文字を無視し得る。設定 API は `null` を自動設定への復帰として受け付け、無効な非 null 値には HTTP 400 を返す。根拠: `app/host/server/agent/profile.mjs:189-199`、`app/host/server/index.mjs:2056-2069`。

`STRATA_COMPACTION_HEADROOM_FRACTION` は別の比率で、既定値 `0.125`、有効範囲 `[0, 0.5]`。実際のトークン閾値は、`window * thresholdRatio` と `window - outputBudget - headroomTokens` の小さい方を切り捨てて求めるため、この別変数や返信用予算により、対象変数だけから最終閾値は決まらない。根拠: `app/host/server/agent/profile.mjs:167-170,209-225`。

## 有効になる条件

- Strata のホストアプリで Harness エージェントのプロファイルを生成する経路で使われる。各ローカルモデル・API 接続モデルの compaction policy に比率を載せる（`app/host/server/agent/profile.mjs:314-324,338-368,373-417`）。それを標準 preset の `compaction-basic` 設定として出力する（`app/host/server/agent/preset.mjs:95-102`）。このコードが確認できる事実は Strata が設定を生成・渡すところまでであり、外部 Harness 内部の実行規則はここでは Strata の挙動として説明しない。
- 送信前の独自適合判定で対象環境変数由来の値が使われるのは、通常のローカルモデル経路（`!goal && !adopt && route.kind === 'local'`）に限る。対象モデルのインスタンスと正の `contextWindow` が必要で、メッセージが 3000 文字未満ならトークン計数を省略する。トークン計数に失敗した場合も判定を省略する。根拠: `app/host/server/agent/agent-bridge.mjs:1846-1868,610-625`、`app/host/server/agent/context-fit.mjs:14-15,42-59`。
- ユーザーが設定画面/API から `thresholdRatio` を保存している間は、その値が環境変数を上書きする。`null` に戻すと環境変数が再び候補になる。起動時に保存済み設定から選択状態を読み、POST の更新時にも選択状態を差し替える。根拠: `app/host/server/index.mjs:247-248,2056-2069`、`app/host/server/agent/profile.mjs:180-207`。
- OS、GPU backend、モデルのエンジンビルド macro による分岐は、この値の読み取り・計算にはない。CLI 引数や別の環境変数がこの比率を直接上書きする処理も見つからない。

## 実行時の詳細

保存済み設定はサーバー起動時に `setCompactionChoice(store.get().agentChat)` へ渡され、設定 API の POST ごとに更新される。環境変数は `thresholdRatio()` の呼び出しごとに `process.env` から parse され、関数内 static cache はない。プロファイル生成時にはモデルごとに計算される policy 配列が生成済みプロファイルへ入る。Harness 子プロセスの環境は `agentEnvironment` がホスト環境から許可名だけを残す方式で、`STRATA_COMPACTION_THRESHOLD_RATIO` 自体は許可リストに含まれない。比率は環境変数として子へ転送されるのでなく、Strata が生成するプロファイルの設定値として渡される。根拠: `app/host/server/index.mjs:247-248`、`app/host/server/agent/profile.mjs:203-225,314-324,338-368,373-417`、`app/host/server/agent/harness-runtime.mjs:20-36,75-83`。

ローカルモデルへの通常メッセージでは、Strata はモデルサーバーにトークン数を問い合わせ、現在の会話圧力と新しいメッセージ数を閾値と比較する。古い会話を残す価値があり、かつ `pressure + messageTokens > threshold` なら送信前に Harness の `/compact` を呼び、完了時は要約前後の使用率をチャットに通知する。閾値未満ならそのまま送る。メッセージ自体が現在の会話には収まらない場合、比率に関係なく先に要約を試す。空の会話にしても収まらない場合は `CONTEXT_MESSAGE_TOO_LARGE` エラーを返して送信を止める。根拠: `app/host/server/agent/context-fit.mjs:26-39`、`app/host/server/agent/agent-bridge.mjs:1846-1868,607-625`。

送信前要約の条件を満たす場合に `/compact` が失敗しても、この呼び出し箇所はその失敗を理由にメッセージ送信を中断せず後続処理へ進む。直接要約コマンドの失敗時は Busy、何も要約するものがない、または失敗の区別をチャット表示に使う。通常ログには `/compact` の結果として `agent · compact: ...`、停止後の試行では `agent · compact after a stopped turn: ...` または `agent · compact after a stopped turn failed: ...` を出す。環境変数が無効または未設定であること自体を警告するログはない。根拠: `app/host/server/agent/agent-bridge.mjs:619-628,1875-1887,1900-1928,1931-1936`。

## ログと測定値

無効値の警告ログはなく、既定値への fallback は無言で行われる。設定画面向けの `/api/agent/compaction` GET 応答には `effective.thresholdRatio` と `source.thresholdRatio`（`setting`、`environment`、`default`）が含まれる。送信前に要約した場合はステータス `Summarizing earlier messages…` と、成功後の `Older messages were summarized to make room...` を表示する。これは環境変数値のログではない。根拠: `app/host/server/index.mjs:258-271`、`app/host/server/agent/agent-bridge.mjs:619-624`、`app/host/server/agent/context-fit.mjs:67-70`。

この環境変数による速度・品質・トークン削減量の測定値は、対象ソースと関連するホスト文書では確認できなかった。測定値は記載しない。

## 根拠

- `app/host/server/agent/profile.mjs:172-225` — 既定値、環境変数 parse、保存値の優先、閾値計算。
- `app/host/server/agent/profile.mjs:314-324,338-368,373-417` — ローカル/API 各モデル向け compaction policy の生成。
- `app/host/server/agent/preset.mjs:95-102` — 生成 policy を `compaction-basic` の `modelPolicies` に設定。
- `app/host/server/index.mjs:247-271,2056-2069` — 起動時の保存値反映、設定表示と出所、設定 API。
- `app/host/server/agent/harness-runtime.mjs:20-36,75-83` — Harness 子プロセス環境のフィルタリングと起動。
- `app/host/server/agent/context-fit.mjs:14-15,26-59` — 送信前判定、閾値到達時の要約判定、計数失敗時の扱い。
- `app/host/server/agent/agent-bridge.mjs:607-628,1836-1887,1900-1936` — 判定の適用条件、要約呼び出し、表示・ログと失敗経路。
