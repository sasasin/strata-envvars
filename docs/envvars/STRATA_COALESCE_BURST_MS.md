# `STRATA_COALESCE_BURST_MS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `main...origin/main` で、未コミット変更はありません。

## 役割

Python の HTTP サーバーが、同じ engine の直近の到着要求数を数える時間幅（ミリ秒）です。`STRATA_COALESCE_PREFILL` による複数 prompt の同時 prefill 判定で使われます。この変数自体は coalescing を有効にしません。

## 値と判定

サーバーの `serve.server` モジュール読み込み時に、`os.environ.get(...) or 250` の結果を `int()` で変換し、`max(10, ...)` を適用します（`serve/server.py:352`）。

| 環境値 | 実効値・結果 |
|---|---|
| 未設定 | 250 ms |
| 空文字 | `or 250` により 250 ms |
| 整数文字列 | 整数へ変換し、10 未満なら 10 ms。例: `500` → 500 ms、`0` / `-1` → 10 ms |
| 整数でない文字列 | `int()` の `ValueError`。この代入を含むモジュール読み込みが失敗する。ここで独自の警告や fallback は行わない |

正の値に上限 clamp はありません。前後の空白を含む整数文字列は Python の `int()` が受理する形式に従います。小数表記（例 `10.5`）や数値の後ろに文字が続く値は整数変換できません。

## 有効になる条件

- `StrataEngine` が batch slot を使うこと。`generate()` は `self.batch` が truthy の場合に `generate_batched()` を呼びます（`serve/server.py:2327-2336`）。batch は CLI の `--batch` / `--slots`、または設定の `parallel` から構成されます（`serve/server.py:1167-1172,3303-3324`）。
- `STRATA_COALESCE_PREFILL` が 2 以上で、要求が embeddings ではないこと。batch admission でこの条件を満たすと `_coalesce()` を呼びます（`serve/server.py:2078-2080`）。
- `_coalesce()` が、この時間窓内に `COALESCE_MIN_REQS` 以上の要求を観測すること。`COALESCE_MIN_REQS` は別環境変数 `STRATA_COALESCE_MIN_REQS` 由来で、既定 3、最小 2 です（`serve/server.py:351,1823-1832`）。

したがって batch slot がない場合、coalescing 設定が 2 未満の場合、または要求数が閾値に届かない場合、この値は prompt のまとめ読みを発生させません。閾値に届かない場合でも `STRATA_COALESCE_WAIT_MS` が正なら 10 ms 後に一度だけ再計数します。同変数が 0（既定）なら再計数待ちはありません（`serve/server.py:346,1828-1834`）。

## 実行時の詳細

要求が control lines を待つとき、サーバーは monotonic clock の到着時刻を `arrivals` に記録します。deque は直近 64 件を保持します（`serve/server.py:1211-1214,1751-1756`）。`_coalesce()` は現在時刻から `COALESCE_BURST_MS / 1000.0` 秒以内の到着数を数え、`1 + len(wait_lens)` と比べた大きい方を `recent` とします。ここで `wait_lens` は control lines を待っている要求です（`serve/server.py:1751-1756,1821-1827`）。つまり閾値判定は「時間窓内の到着数」だけでなく、現在待機中の要求数も反映します。

閾値を満たすと、別変数 `STRATA_COALESCE_WAIT_MS` が正の場合はその時間だけ待ってから、待機中の要求を候補として選びます。選択数は `STRATA_COALESCE_PREFILL - 1` 以下で、各 prompt は 32 token 以上、合計 token 数は `STRATA_COALESCE_TOKENS` 以下、free slot があることなどが必要です。選ばれた prompt は `BCO` 行で engine に送り、成功して一つ以上選ばれた場合に `[strata] coalesce: ...` を stdout に出します（`serve/server.py:1833-1859`）。選ばれなければこのログは出ません。

この環境変数はモジュール読み込み時に一度評価され、`COALESCE_BURST_MS` に保持されます。要求ごとの再読み取りはありません。サーバー実行中に環境を変更しても値は更新されません（`serve/server.py:352,1823-1827`）。CLI 引数による同じ値の上書きはありません。

## 根拠

- `serve/server.py:352` — 環境値の取得、空文字時の既定値 250、整数変換、下限 10 ms。
- `serve/server.py:1211-1214,1751-1756,1821-1827` — 到着時刻と待機要求を記録し、burst window 内の件数を算出。
- `serve/server.py:340-351,1828-1859,2078-2080` — 他の coalescing 条件、閾値未達時の扱い、候補選択、engine への送信とログ。
- `serve/server.py:1167-1172,2327-2336,3303-3324` — batch slot の設定と batch 実行経路。

候補一覧 `docs/envvars/000_envvers.md:646` に名前があります。Strata ソース全体の完全一致検索では、環境値の読み取りは `serve/server.py:352` の一箇所でした。読み取った値の利用は `serve/server.py:1826` です。`docs/DETAILS.md` にはこの変数固有の追加仕様・測定値を確認できませんでした。
