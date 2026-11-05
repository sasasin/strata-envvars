# `STRATA_STREAM_BEAT_MS`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

Strata Host のチャット応答ストリームに送る beat frame の間隔をミリ秒で指定します。静かな NDJSON ストリームを開いたまま保つための Host 側のタイマー設定です。推論エンジンや GPU の処理間隔は変更しません。設定値が範囲外などで無効な場合は既定の 15 秒間隔を使います。(`apps/host/server/stream-beat.mjs:8-18`)

## 値と判定

値は JavaScript の `Number()` で数値へ変換し、有限値かつ 20 以上 60,000 以下ならその数値をミリ秒として採用します。境界値 20 と 60,000 は有効です。変換値が条件を満たさなければ `BEAT_MS` の 15,000 ミリ秒に戻ります。(`apps/host/server/stream-beat.mjs:8,11-15`)

| 環境変数の値 | 結果 |
|---|---|
| 未設定 | `Number(undefined)` は有限数でないため 15,000 ms |
| 空文字、空白だけ | `Number()` の結果は 0 なので 15,000 ms |
| `200`、`2e2`、`0x14` | それぞれ 200、200、20 ms として採用 |
| `20`、`60000` | 境界を含む範囲内なので採用 |
| `19`、`60001`、負数、`0` | 範囲外なので 15,000 ms |
| `abc`、`NaN`、`Infinity` | 有限数にならないため 15,000 ms |

文字列全体の整数 parse ではなく `Number()` の変換規則に従います。したがって、`200ms` のように数値の後ろに単位を付けた文字列は無効です。明示的な空文字も未設定と同じ既定間隔になります。(`apps/host/server/stream-beat.mjs:12-15`)

## 有効になる条件

この値を読むのは Strata Host の `apps/host/server` です。`/api/chat/stream` と `/api/plan/start-goal` は NDJSON 応答ヘッダーを書いた直後に beat timer を開始します。`/api/chat/attach` は attach 後、最初の frame を書く際に応答ヘッダーと timer を開始します。後者では最初の frame が来る前には beat timer は動きません。(`apps/host/server/index.mjs:2050-2056,2073-2093`)

値を使う backend、OS、モデル状態、CLI 引数による上書き条件はありません。ソース上、同名環境変数の読み取り箇所は `stream-beat.mjs` のみです。索引候補を追加する参照や、別の設定優先順位は確認できませんでした。(`apps/host/server/stream-beat.mjs:12-15`)

## 実行時の詳細

`keepStreamAlive()` の既定引数として `beatInterval()` を呼ぶため、環境変数は各ストリームで timer を作る時に読み直されます。モジュール読み込み時の static cache はありません。同一プロセス内で環境を変更した場合、その後に開始するストリームには反映されますが、既に動作中の timer の周期は変わりません。明示的な `ms` 引数を `keepStreamAlive()` に渡す呼び出しがあればそれが優先しますが、Host の呼び出し箇所はいずれも引数を省略しています。(`apps/host/server/stream-beat.mjs:12-19`; 呼び出し元 `apps/host/server/index.mjs:2052,2091`)

timer は `{"type":"beat"}` と改行を `res.write()` で定期送信します。応答が終了済みまたは破棄済みなら timer を止めます。送信中に例外が発生した場合も timer を止めますが、例外を記録するログや独自の終了処理はありません。`finish`、`close`、`error` の各応答イベントでも timer を解除し、解除関数は複数回呼んでも安全です。timer は `unref()` 可能な環境では unref されます。(`apps/host/server/stream-beat.mjs:17-35`)

beat は通常のチャット frame と同じ NDJSON ストリームに送られます。クライアント切断時の turn の cancel/detach は既存の response `close` 処理に任され、この timer はそれを変更しません。(`apps/host/server/stream-beat.mjs:17-35`; 呼び出し元 `apps/host/server/index.mjs:2047-2048,2091-2094`)

## 根拠

- `apps/host/server/stream-beat.mjs:8-15` — 既定値、`Number()` による変換、有限値と包含範囲の判定。
- `apps/host/server/stream-beat.mjs:17-35` — frame の送信、応答イベントに応じた停止、例外時の停止、timer の unref。
- `apps/host/server/index.mjs:56` — Host server からの helper import。
- `apps/host/server/index.mjs:2047-2059` — `/api/chat/attach` の応答開始と最初の frame 時の呼び出し、close 時の abort。
- `apps/host/server/index.mjs:2073-2094` — `/api/chat/stream` と `/api/plan/start-goal` の応答開始時の呼び出し、close 時の abort。
