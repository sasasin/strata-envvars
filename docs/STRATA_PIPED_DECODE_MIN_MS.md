# `STRATA_PIPED_DECODE_MIN_MS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。調査対象は Strata 所有ソース。外部ライブラリや GPU driver の内部動作は対象外。

## 役割

layer split 上で pipelined slot groups が稼働しているとき、分割した prompt read の合間に slot groups が decode する時間の下限（ミリ秒）を指定します。read piece の処理時間に `STRATA_BATCH_DECODE_SHARE` を掛けた decode budget がこの値より小さいとき、下限まで延ばします。read は piece ごとに pipeline を drain してから decode を進め、次の piece に移ります。

## 値と判定

環境変数は `std::atof()` で変換し、`std::max(0.0, 値)` で負数を 0 にします。値はミリ秒の `double` です。

| 値 | `pr_floor` |
|---|---:|
| 未設定 | `0.0` |
| 空文字、数値に変換できない文字列 | `0.0`（`atof` の変換結果） |
| 数値文字列 | 変換された値。ただし負数は `0.0` |

`atof` は文字列全体の厳密な検証をしません。先頭の空白を許し、数値として読める先頭部分を変換します。したがって `12.5ms` は `12.5` として扱われ、`-3` は clamp により `0` になります。コードに上限 clamp はありません。

この値は関数内の `static const double` に保存され、該当コードを最初に実行したときに一度読み取られます。その後プロセス内で環境を書き換えても再評価されません。根拠: `src/program/generate.cpp:13126-13134`。

## 有効になる条件

この値が decode budget に使われるのは、次の条件を満たす場合です。

- `piped` が真であること。実装では `--batch` が正、`--batch-groups` が 1 より大きく、layer split による stage 数が 1 より大きい条件です（`src/program/generate.cpp:11092-11095`）。
- `STRATA_PIPED_READ_PIECE` が正であること。未設定時は 0 なので、piecewise read は opt-in されません。`pr_on` は `piped && pr_piece > 0` で決まります（`src/program/generate.cpp:13117-13135`）。
- Decode budget を実際に走らせる箇所では batch slot が稼働していること。slot が止まっていれば、piece のログだけを出して次へ進み、この下限による decode は行いません（`src/program/generate.cpp:13211-13226`）。

したがって、この変数だけでは piecewise read や slot decode を有効にしません。`STRATA_PIPED_READ_PIECE` が未設定・0以下、pipelined groups が使われない、または slot が稼働していない場合は値を読んでも実際の budget に影響しません。

## 実行時の詳細

通常の piece 間 decode budget は、`piped_decode_budget_ms()` が次の順で計算します。

1. `max(0, STRATA_BATCH_DECODE_SHARE) × max(0, piece の処理時間 ms)` を求める。
2. `STRATA_PIPED_DECODE_MAX_MS` が正なら、その値で上限をかける。
3. 最後に `max(計算値, STRATA_PIPED_DECODE_MIN_MS)` を取る。

このため floor は cap の後に適用され、floor が cap より大きい設定では最終 budget は cap を超えて floor になります。`STRATA_PIPED_DECODE_MAX_MS` が未設定・0以下なら上限はありません。計算は `include/strata/program/batch_read.hpp:69-75` にあります。

budget を受け取る処理は少なくとも一回 pipeline を pump し、slot batch が稼働中かつ経過時間が budget 未満の間 pump を続け、最後に in-flight group を drain します。従って指定値は時間判定の下限であり、実時間を厳密にその値へ一致させる指定ではありません（`src/program/generate.cpp:13140-13159`）。

piecewise read の直後に別の read が続く場合にも lead-in decode budget を使います。前の read の piece 時間が記録されていれば同じ share/cap/floor 計算を行います。まだ前の piece がない場合は、cap が正なら cap、そうでなければ `max(floor, 200.0)` ms を lead-in budget にします（`src/program/generate.cpp:13160-13175`）。この分岐では cap が正のとき floor と cap の大小を比較しません。

実行中は piece ごとに `strata batch: piped read ... then the slots decoded ...` の stderr ログが出ます。slot が稼働していない場合は decode 部分のない piece ログです。floor 値そのものを表示する専用ログは確認できません（`src/program/generate.cpp:13211-13225`）。

## 文書との照合

`docs/BATCHING.md:287-310` は、pipelined groups による opt-in の prompt read について、piece 間 decode 時間を share 値から計算し、`STRATA_PIPED_DECODE_MAX_MS` と `STRATA_PIPED_DECODE_MIN_MS` で上下させると説明しています。計算関数の実装と一致します。

## 根拠

- `src/program/generate.cpp:11092-11100` — pipelined groups の成立条件。
- `src/program/generate.cpp:13117-13159` — read piece 設定、cap/floor の読み取り、適用条件、decode budget 実行。
- `src/program/generate.cpp:13160-13175,13211-13225` — 連続 read の lead-in budget と piece ごとの処理・ログ。
- `include/strata/program/batch_read.hpp:69-75` — share、cap、floor の計算順。
- `docs/BATCHING.md:287-310` — 設計説明との照合。
