# `STRATA_ADMIT_MAX_WAIT_S`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`strata serve --batch` のサーバー側で、新規要求の prompt 読み込み順を短い prompt 優先にするとき、長い prompt も待機時間がこの秒数に達したら「短い要求」と同じ優先グループに入れます。これにより短い要求を先に処理しつつ、長い要求が短い要求に際限なく後回しにされることを避けます。

この変数だけでは優先制御は有効になりません。別変数 `STRATA_ADMIT_SHORT_FIRST` が正の token 数に設定されている必要があります。

## 値と判定

サーバーモジュールの import 時に `_timeout_env("STRATA_ADMIT_MAX_WAIT_S", 30.0)` で読み取ります。`float()` による変換で、文字列全体を数値として解釈します。

| 環境変数値 | 読み取り結果 | 優先順位上の扱い |
|---|---:|---|
| 未設定 | 30.0 秒 | 長い prompt は待機が30秒以上になると短い要求と同じ優先グループ |
| 正の有限数 | その秒数 | その時間以上待った長い prompt は短い要求と同じグループ |
| `0` または負数 | 0.0 秒 | 待機中の全要求が直ちに同じ優先グループになり、prompt 長による優先差がなくなる |
| 空文字、数値でない文字列 | 変換失敗として30.0秒 | 既定値に戻る |
| `nan` | NaN | 比較 `待機秒数 >= NaN` は偽となるため、長い prompt は待機時間によって短い要求グループに入らない |
| `inf` | 正の無限大 | 有限時間の待機では長い prompt は短い要求グループに入らない |

`float()` が受け付ける数値表記を使えます。整数への丸めや秒数の上限 clamp はありません。`_timeout_env` は `ValueError` のみを捕捉し、変換後の値が `<= 0` の場合は `None` を返します。呼び出し側の `or 0.0` により、この場合の実際の比較閾値は `0.0` です。

## 有効になる条件

- サーバーの `--batch` 経路で、新規要求が control lines（prompt 読み込みを含む制御操作）を待つ場合に関係します。
- `STRATA_ADMIT_SHORT_FIRST` が正の整数として読み取られている必要があります。未設定、空文字、`0`、負数、整数変換不能値では短い要求優先判定自体が使われません。整数以外の数値表記（例 `1.5`）も `int()` 変換に失敗し、0扱いです。
- 優先順位を決める対象は `_take_control(..., new=True)` で登録された新規要求の初回 admission です。slot から戻って control lines を取り直す要求 (`new=False`) はこの並べ替えの対象外です。
- 既に進行中の prompt 読み込みを中断しません。複数要求が待っている間に、次に control lines を取る要求を選ぶための順序制御です。
- 変数はサーバープロセスの Python モジュール読み込み時に一度評価されます。起動後の環境変更は反映されません。個別要求ごとの設定や CLI/config による上書きは、この値の読み取り経路にはありません。

## 実行時の詳細

`_take_control` は待機要求を `(prompt token 数, 到着時刻, 新規か)` として記録します。`STRATA_ADMIT_SHORT_FIRST > 0` の場合、control lock を得る前と得た直後に `_admit_next()` を確認し、待機中の新規要求のうち次に進める要求だけに lock を保持させます。短いグループは prompt 長が `STRATA_ADMIT_SHORT_FIRST` 以下の要求、または待機時間が `ADMIT_MAX_WAIT_S` 以上になった要求です。各グループ内では到着時刻順に選択します。

`STRATA_ADMIT_MAX_WAIT_S <= 0` は機能全体を無効にする設定ではありません。比較上すべての待機要求が即時に短いグループとなるため、正の `STRATA_ADMIT_SHORT_FIRST` が併用されても prompt 長に基づく優先差はなくなり、待機中の新規要求は到着順で選ばれます。キュー期限を過ぎた場合は通常の `_take_control` 処理により `QueueWaitExpired` となり、文言 `the inference queue wait deadline expired; retry later` が設定されます。この期限は本変数とは別の要求期限です。

この変数自体によるログ出力はありません。`docs/BATCHING.md` は `STRATA_ADMIT_SHORT_FIRST` の説明内で本変数の既定値を30秒と記しています。

## 根拠

- `serve/server.py:295-300` — 共通 timeout helper の `float()` 変換、無効文字列 fallback、0以下の扱い。
- `serve/server.py:310-318` — `STRATA_ADMIT_SHORT_FIRST` と本変数の import 時設定、既定値30秒。
- `serve/server.py:1658-1689` — 待機 entry の登録、新規要求のみの順序判定、lock 獲得後の再確認。
- `serve/server.py:1706-1714` — 待機 entry の削除と制御権取得後の通知。
- `serve/server.py:1716-1726` — 短い要求/待機時間によるグループ分けと到着順 tie-break。
- `docs/BATCHING.md:110-125` — batch のサーバー側機能と `STRATA_ADMIT_SHORT_FIRST` の概要。本変数の既定値を30秒と記載。
