# `STRATA_COALESCE_PREFILL`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Terminal の Python serve が、同じ engine で制御線を待っているリクエストの prompt を、先に制御線を取ったリクエストとまとめて読む上限を設定する。`N > 1` の場合、先行リクエストを含む最大 `N` 件（後続は最大 `N-1` 件）を候補にし、空き batch slot がある後続 prompt を engine の `BCO` protocol に送る。対応 engine は prompt 群を同じ layer-major pass で読み、後続リクエストは予約 slot の prompt を再利用する。通常の単独読みや出力 token の生成上限を直接変更する設定ではない。Python 側の読み取りと選別は `terminal/serve/server_parts/base.py:271-275`、`terminal/serve/server.py:1868-1909,2197-2199`、engine 側の protocol と co-read は `engine/src/program/generate.cpp:18338-18350,20708-20767`。

これは serve process の実験的な制御で、値を読むのは `terminal/serve/server_parts/base.py` である。`terminal/serve/server.py:73-80` がその定数を import する。候補一覧のほかの出現はコメントや `terminal/tools/par/variants/` の実験設定であり、追加の読み取り箇所ではない。

## 値と判定

Python の `os.environ.get(...) or 0` の結果を `int` に変換し、`max(0, ...)` で負数を 0 にする。`unset` と空文字はどちらも 0。整数の文字列表現（前後の空白や符号を含む Python `int` が受理する形式）は変換され、値が 0 または 1 なら co-read は呼ばれない。2 以上で有効になる。小数、`true`、`1x`、空白だけなど `int` が受理しない値は import 時の `ValueError` となり、独自の fallback や設定警告はない。上限値の clamp はなく、大きな値も Python 整数として受理されるが、実際に選ばれる後続数は空き slot 数・待機数などで制限される。根拠: `terminal/serve/server_parts/base.py:271-275`、判定箇所 `terminal/serve/server.py:2022-2024,2197-2199`。

| 値 | 判定 |
|---|---|
| 未設定、空文字、`0`、負の整数（例 `-2`） | 0 に評価され、無効 |
| `1` | 1 に評価されるが、実行条件が `> 1` のため無効 |
| 2 以上（例 `2`, `8`, `+3`, ` 3 `） | 最大候補数として有効 |
| `true`, `1x`, `1.0`, 空白だけ | `int` 変換で `ValueError`。serve module の読み込みに失敗 |

この変数に対する CLI 引数や設定ファイルからの上書きは見つからない。値は server module import 時に定数へ変換され、その server process の実行中には再読込されない。server が起動する engine にも環境は渡されるが、engine はこの名前を環境から読まず、server が送る `BCO` protocol を処理する。根拠: `terminal/serve/server_parts/base.py:275`、`terminal/serve/server.py:73-80,827-829`、`engine/src/program/generate.cpp:18338-18350`。

## 有効になる条件

- Terminal serve の batch-slot 経路で、`COALESCE_PREFILL > 1` かつ embeddings ではないリクエストであること。初回 admission の control line を取得した後の batch slot admission で `_coalesce` が呼ばれる。embeddings は候補登録・実行の両方から外れる。`terminal/serve/server.py:2022-2024,2197-2199`。
- 後続リクエストが同じ engine の待ち行列にあり、まだ preslot を持たず、coalesce 済みでもなく、prompt が 32 token 以上であること。先行 prompt と候補 prompt の合計が `STRATA_COALESCE_TOKENS`（未設定・空文字なら 16384、下限 256）の範囲内で、`pick_slot` が空き slot を返す必要もある。選択数は `STRATA_COALESCE_PREFILL - 1` 以下。`terminal/serve/server.py:1886-1905`、`terminal/serve/server_parts/base.py:278`。
- 適応条件として、直近 `STRATA_COALESCE_BURST_MS`（既定 250 ms、下限 10 ms）内の arrival 数または待ち数が `STRATA_COALESCE_MIN_REQS`（既定 3、下限 2）以上であること。閾値未満でも `STRATA_COALESCE_WAIT_MS` が正なら最初に 10 ms 待って再確認し、それでも未満なら通常の prompt read に戻る。閾値以上なら設定された `STRATA_COALESCE_WAIT_MS`（既定 0 ms、負値は 0）だけ待って候補を集める。これらは独立した環境変数で、CLI 引数からの優先指定はこの箇所にない。`terminal/serve/server.py:1874-1885`、`terminal/serve/server_parts/base.py:278-291`。
- Engine が `BCO` を受理し、次の `BGEN` で取り込めること。engine は範囲内 slot かつ 3 token 以上の `BCO` だけを pending にし、次の BGEN admission に渡す。共読み込み対象が実際に残らない場合は通常の `sp.run` を使う。`engine/src/program/generate.cpp:18338-18350,18376-18395,20719-20735`。

OS やこの変数専用の backend/build macro による追加分岐は、確認した読み取り・呼び出し箇所にはない。実際に利用可能な engine protocol や空き batch slot がなければ候補は選ばれず、通常の処理になる。

## 実行時の詳細

serve module の import 時に一度評価されるため、server process 起動後に環境を書き換えても定数には反映されない。`_take_control` は待機 prompt と request を `wait_lens` に登録し、制御線を取得したリクエストが `_coalesce` を呼ぶ。候補の slot を busy として予約し、request に preslot を記録してから `BCO <slot> <token IDs>` を送信する。続いて通常の `BGEN` を送る。先行分と後続分は engine の同じ co-read pass に渡され、成功した後続 slot には `BCOK <slot> <tokens>` が返る。serve は `BCOK` を制御行として受け取る（その行自体では追加処理をしない）。後続 request は自分の admission 時に preslot を使う。キャンセルなどで先行 admission 前に後続 request が離れた場合は予約 slot を解放する。根拠: `terminal/serve/server_parts/base.py:275`、`terminal/serve/server.py:1791-1796,1857-1866,1868-1909,1568-1569,2022-2034`、`engine/src/program/generate.cpp:18338-18350,20744-20767`。

## ログと測定値

候補が選ばれ、server が少なくとも一つの `BCO` を送ったとき、serve は stdout に `[strata] coalesce: {件数} waiting prompt(s) ({token数} tokens) read with this request's {先行prompt長}` を出す。engine は stderr に `strata batch: co-read starting: ...` を出し、成功時は `strata batch: co-read: ... read in the same pass ...` を出す。multi-prompt read が `prefill: multi-prompt read declined` で辞退された場合は、engine が `strata batch: co-read of ... declined (...)` を stderr に出して通常の単独 `sp.run` に戻る。その他の co-read 失敗はその場で `false` を返し、通常 read に置き換えず失敗経路へ進む。根拠: `terminal/serve/server.py:1906-1910`、`engine/src/program/generate.cpp:20744-20767`。

この変数による速度・token 同一性の測定値は記載しない。参照した `docs/DETAILS.md` と関連する文書に、この名前に関する測定条件つきの説明は見つからなかった。

## 根拠

- 環境読み取り・変換: `terminal/serve/server_parts/base.py:271-275`
- Server への import: `terminal/serve/server.py:73-80`
- 適用箇所と制限: `terminal/serve/server.py:1868-1909,2022-2034,2197-2199`
- Engine protocol の取り込み・実行・fallback: `engine/src/program/generate.cpp:18338-18350,18376-18395,20708-20767`
- 関連する coalesce 設定: `terminal/serve/server_parts/base.py:278-291`
