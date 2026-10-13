# `STRATA_BATCH_DECODE_SHARE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--batch` で長い prompt を chunk ごとに読むとき、各 chunk の後に既存 batch slot をどれだけ decode させるかを決めます。値は decode の時間予算に掛ける係数です。既定値 `0.5` なら、直前に読んだ chunk の所要時間の半分を目安に slot の batch window を実行します。prompt 自体の chunk 処理や token 計算を変える設定ではありません。

## 値と判定

CUDA/HIP 系と SYCL 系の engine 実装は、同じ規則で値を読みます。

| 環境変数の状態・値 | `decode_share` |
|---|---:|
| 未設定 | `0.5` |
| 設定あり、`atof` が 0 または数値を変換できない（空文字を含む） | `0.0` |
| 負の数 | `0.0`（`std::max(0.0, atof(v))` で下限を 0 にする） |
| 0 より大きい数 | 変換された値。そのまま係数に使い、上限 clamp はない |

`std::atof` による変換のため、文字列全体の厳密な数値検証はしません。変換できる数値部分の後ろに文字があっても、その数値部分が使われます。たとえば `0.25junk` は通常 `0.25`、`junk` は `0` になります。設定値の比較や大文字小文字の判定はありません。

## 有効になる条件

- `--batch` が有効で、prompt を `read_part` の chunk 分割経路で読むこと。
- chunk の読み込み後も `batch_on()` が真、つまり少なくとも1つの batch slot が active であること。
- `decode_share` が 0 より大きいこと。

条件に合わないときは slot decode の追加時間を設けません。特に、batch slot が存在しない/active でない場合、この値だけでは decode は始まりません。pipelined prompt read では `batch_read_piece()` が 0 を返して残りを一括して読むため、chunk 境界での slot decode はこの経路では行われません。layer split で slot が active でない場合は、`STRATA_BATCH_YIELD_CHUNKS` に応じた複数 chunk 単位で読むことがありますが、slot がないため本変数による decode は発生しません。

## 実行時の詳細

各 prompt piece を `sp.run()` で読んだ後、piece が prompt の終端でなければ、実装は `decode_share * chunk_read_ms` を時間予算にします。少なくとも1回 `batch_step()` を実行し、その経過時間が予算に達するか、slot がなくなって `batch_on()` が偽になるまで追加 window を実行します。したがって実時間は window 単位で進み、必ず予算と一致するわけではありません。値が大きいほどこの間の slot decode が長くなり、prompt read に割く時間との配分も変わります。

読み取り結果は `static const double` に保存されます。各 engine プロセスで最初に `read_part` がこの初期化へ到達した時点の値を使い、その後プロセス内で環境変数を変更しても再読込しません。CUDA/HIP 系と SYCL 系はそれぞれの engine 実装内で同じ処理を持ちます。

slot decode が一度でも行われると、prompt 完了時に stderr へ `strata batch: the prompt was read in ... parts, the slots decoding ... ms between them` を出します。`STRATA_TRACE` が有効なら、chunk ごとの decode 時間も `strata trace: prompt chunk to ...` として stderr に出ます。`decode_share <= 0` なら追加 decode はなく、この batch interleave の集計ログも出ません。

## 文書との照合

`docs/BATCHING.md` は batch slot が prompt chunk の間に動き、既定値 `0.5` で chunk 所要時間の半分 decode すると説明しています。これは既定値と意図について実装に一致します。実装上は「半分」の時間を window 単位で使う予算として評価し、少なくとも1 window は実行するため、厳密な時間比率を保証する記述ではありません。文書中の一般的な chunk サイズ（2048–8192 tokens）は本変数自体の値域ではありません。

## 根拠

- `src/program/generate.cpp:10824-10832` — batch prompt の chunk 読み込み説明と環境変数 parse、既定値・下限 clamp。
- `src/program/generate.cpp:10842-10856,10907-10920` — piece ごとの prompt read、slot decode の時間予算とループ、trace。
- `src/program/generate.cpp:9236` — `batch_on()` は active slot の有無を返す。
- `include/strata/program/batch_read.hpp:13-28` — batch/pipeline/layer split/slot 状態による piece サイズ。
- `sycl/src/program/generate.cpp:10135-10143,10153-10160,10212-10224` — SYCL 実装も同じ環境変数判定と時間予算を使う。
- `src/program/generate.cpp:11093-11100` — slot decode の有無に応じた batch 集計ログ。
- `docs/BATCHING.md:128-130` — 既定値 `0.5` と chunk 間 decode の説明。
