# `STRATA_PREFILL_COPY_EVENT_EVERY`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

長い prompt chunk の非常駐 expert を host から GPU へ流すとき、copy stream 上の「コピー完了」event をどの間隔で記録するかを指定する。既定相当の `1` では各 expert entry のコピー後に event を記録する。`2` 以上では間隔を空け、compute stream は必要な entry 以降で最初に記録された event を待つ。コピー順や ring slot は同じで、変わるのは event の記録と待機の粒度である（`engine/src/prefill/prefill.cpp:4807-4816, 4865-4914, 4920-4940`、`engine/include/strata/prefill/copy_events.hpp:18-33`）。

## 値と判定

prefill 処理が最初にこの宣言を実行した際、関数内 `static` 初期化で一度 `std::getenv` し、設定値には `std::atoi` を適用した後 `copy_event_every_from` で正規化する。未設定は `1`。設定済みでも parse 結果が `1` 以下なら `1`、`2..63` はその値、`64` 以上は `64` になる（`engine/src/prefill/prefill.cpp:4761-4764`、`engine/include/strata/prefill/copy_events.hpp:15-16`）。

| 入力例 | parse / 有効値 |
|---|---|
| 未設定、空文字、`0`、`1`、`-2`、`true` | いずれも実効値 `1`（未設定は明示的な既定値。空文字・`true` は `atoi` が `0` を返し、`<=1` は `1` に正規化） |
| `2`, `63` | `2`, `63` |
| `64`, `65` | `64` |
| `2tail`, `  +3x` | `atoi` が読む先頭の整数部分を採用し、それぞれ `2`, `3` |

文字列全体の数値妥当性は検証せず、空白や符号、数字の後ろの文字も `atoi` の規則に従う。したがって `1tail` は `1` 相当、数字で始まらない文字列は `0` 相当となる。無効入力専用の警告やエラー処理はない（同上）。

## 有効になる条件

- `prefill.cpp` を含む GPU engine の prefill 経路で有効。CUDA/HIP engine の共通ターゲット、SYCL ターゲット、Metal ターゲットが同じ `src/prefill/prefill.cpp` を含む（`engine/cmake/strata_gpu_engine.cmake:482-488`、`engine/sycl/CMakeLists.txt:303-308`、`engine/metal/CMakeLists.txt:135-146`）。この変数自体に OS、build macro、server/CLI の個別条件はない。
- 実際に作用するのは、その chunk で `stream_all` が真、すなわち ring が `STAGE`（8）より大きく、chunk token 数 `T` が `stream_all_min()` 以上で、expert source `m.src` がある場合（`engine/src/prefill/prefill.cpp:321, 4625-4629`）。しきい値は `STRATA_PREFILL_STREAM_MIN` や build / device 側の規則で変わり得る（同:648-658）。モデルに非常駐 expert がなく source がない場合など、この streaming 条件に入らない経路では影響しない。
- さらに issuer thread が動く必要がある。`STRATA_PREFILL_ISSUER=0`（`atoi` 結果が 0）なら issuer は inline となり、この値による sparse event 記録は使われない（同:4757-4764, 4807-4816）。他の値の parse 詳細は当該変数の文書を参照。
- `STRATA_PREFILL_ROUTED_STREAM=1` との併用では、copy event 間隔が `1` 以外だと routed walk は使われず、通常の issuer walk が残る。peer prompt ring も routed walk を止める条件だが、copy event 間隔自体の適用条件ではない（`engine/include/strata/prefill/routed_stream.hpp:42-58`、`engine/src/prefill/prefill.cpp:4777-4795`）。
- chunk サイズを決める CLI 引数等が間接的に `T` を変えることはあるが、この環境変数を上書きする CLI / 設定値はこの読み取り経路にはない。

## 実行時の詳細

値は prefill 関数内の局所 `static` に保存されるため、最初にこの宣言を実行した時に一度読み、以後の prompt chunk や同一プロセス内の環境変更では再評価しない（`engine/src/prefill/prefill.cpp:4761-4764`）。

実効値 `1` では各 copy 後に slot の `copied` event を記録する。`2..64` では通常は N 個ごとと最後の entry に記録するが、issuer が待ちに入る前にも、未記録のコピー範囲を consumer が待てるよう補助記録を行う。consumer は必要な entry 以降で最初に記録された event を探し、それを compute stream で待つ。copy stream の順序により、その event は対象 entry のコピーも完了した位置を示す（`engine/include/strata/prefill/copy_events.hpp:18-33`、`engine/src/prefill/prefill.cpp:4865-4914, 4920-4940`）。consumer 側は entry 単位または MMQ group の最後の entry で待つ（同:5815-5820, 7117-7124, 7202-7209, 7564-7574）。

この設定は prompt の streamed expert copy に限られ、token ごとの decode や他の upload event の設定ではない。ソース上でこの値による独自の終了・fallback はなく、`atoi` 後の正規化で無効値も `1` 相当として扱われる。

## ログと測定値

issuer thread が有効で、実効値が `1` より大きいと、初回に次の stderr 行を出す（`copy_wait_dedupe` が有効なら `%s` 部分は `one wait per release event`、そうでなければ `a wait per slot`）。

```text
strata: prompt copies: a copied event every %d streamed experts (STRATA_PREFILL_COPY_EVENT_EVERY), %s (STRATA_PREFILL_COPY_WAIT_DEDUPE)
```

`%d` は正規化後の値。値が `1` のみで wait dedupe も無効ならこの行は出ない（`engine/src/prefill/prefill.cpp:4816-4824`）。この変数の値だけを理由に出る error / warning / 終了ログはない。

## 根拠

- `engine/src/prefill/prefill.cpp:4761-4764` — 環境からの読み取り、`atoi`、cache。
- `engine/include/strata/prefill/copy_events.hpp:15-33` — clamp、記録間隔、consumer が待つ entry の選択。
- `engine/src/prefill/prefill.cpp:4625-4629, 4807-4816, 4865-4940` — streaming / threaded issuer 条件、event の記録と待機。
- `engine/src/prefill/prefill.cpp:5815-5820, 7117-7124, 7202-7209, 7564-7574` — consumer が copy event を待つ地点。
- `engine/include/strata/prefill/routed_stream.hpp:42-58` — routed stream との適用条件。
