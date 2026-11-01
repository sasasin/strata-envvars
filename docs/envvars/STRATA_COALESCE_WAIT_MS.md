# `STRATA_COALESCE_WAIT_MS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業ツリーは clean。

## 役割

`serve/server.py` のバッチ推論で、複数リクエストの prompt をまとめて読み込む coalesced prefill の前に待つ時間をミリ秒で指定します。単独で coalescing を有効にする変数ではありません。`STRATA_COALESCE_PREFILL` が 2 以上で、embedding ではないリクエストを処理するときだけ `_coalesce()` が呼ばれます。

## 値と判定

モジュール読み込み時に `os.environ.get(...) or 0` の結果を Python の `int()` で変換し、`max(0, ...)` を適用します（`serve/server.py:346`）。

| 環境値 | 結果 |
|---|---|
| 未設定、空文字 | `0`。待ち時間なし |
| 整数 `0`、負の整数 | `0` に clamp。待ち時間なし |
| 正の整数 | 指定値をミリ秒として使用 |
| 整数に変換できない文字列 | `int()` の `ValueError`。この読み取り箇所には例外処理や fallback がない |

空白や符号を含む値の受理は Python `int()` の規則に従います。CLI 引数や設定ファイルによる上書き箇所はありません。この設定はモジュール import 時に一度評価されるため、起動後に環境を書き換えても再読込されません。

## 有効になる条件

- `STRATA_COALESCE_PREFILL` が 2 以上であること。未設定・空文字・0・負値では `_coalesce()` を呼びません（`serve/server.py:344,1916-1917,2078-2079`）。
- embedding ではない推論リクエストであること（同上）。
- `_coalesce()` 内で直近リクエスト数が `STRATA_COALESCE_MIN_REQS` に達すること。既定値は 3、最小値は 2 です（`serve/server.py:351,1823-1832`）。最初の確認で不足し、待ち時間が正なら 10 ms 待って再確認します。なお不足のままなら coalescing を行わず戻ります。
- しきい値を満たしたとき、待ち時間が正なら指定時間を `time.sleep()` してから待機中のリクエストを選びます。0 の場合はこの待機も、前述の 10 ms の再確認待ちもありません（`serve/server.py:1828-1834`）。

待ち時間は「最大待ち時間」ではなく、条件を満たした経路で実際に追加する固定 sleep です。正の値でも、候補 prompt がない、prompt が 32 token 未満、合計 token 数が `STRATA_COALESCE_TOKENS` を超える、空き slot がない場合などはまとめるリクエスト数が減るかゼロになります（`serve/server.py:1835-1854`）。候補数は `STRATA_COALESCE_PREFILL - 1` までで、合計 prompt token 上限は既定 16384（最小 256）です（`serve/server.py:344-345,1837-1847`）。

## 実行時の詳細

リクエストが制御線の順番を得てバッチ slot を確保すると、サーバーは `_coalesce()` を呼んで、選んだ待機リクエストの slot を予約し、prompt を `BCO <slot> <ids>` 制御行でエンジンへ送り、その後に先頭リクエストの `BGEN` を送信します（`serve/server.py:1817-1820,1845-1859,2076-2081`）。サーバーは選んだ prompt が先頭 request の prompt と同じ layer-major pass で読まれる前提で処理し、成功時は `[strata] coalesce: ...` を出力します。`BCOK` 行は読み取りループで受信して無処理で通します（`serve/server.py:1594-1595`）。待ち時間単独のログ、警告、終了処理はありません。

変換できない環境値は import 時に `ValueError` となり、この設定読み取り箇所では捕捉されません。極端に大きい正値は `time.sleep()` に渡される可能性がありますが、その値の上限・個別 fallback は Strata 側で定義されていません（`serve/server.py:346,1833-1834`）。

## 根拠

- `serve/server.py:340-352` — coalescing 関連設定、既定値、関連するしきい値。
- `serve/server.py:1817-1859` — 到着数の判定、待機、候補選別、slot 予約、送信、成功ログ。
- `serve/server.py:1913-1917,1923-1926,2076-2081` — prompt の登録と feature の呼び出し条件、エンジンへの送信。
- `serve/server.py:1594-1595` — エンジンからの `BCOK` 行の処理。

候補一覧 `docs/envvars/000_envvers.md:650` に名前があります。Strata のソース全体で値の読み取りを確認できた箇所は `serve/server.py:346` です。ほかの完全一致は `tools/par/` の実験用 variant 設定・起動環境の指定であり、別の読み取り実装ではありません。関連する設計資料に追加の条件や測定値は見つからなかったため、性能効果は記載していません。
