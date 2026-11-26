# `STRATA_BATCH_DECODE_SHARE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--batch` の prompt 読み込み中、読み込みの各 chunk の後に、実行中 slot の decode を続ける時間の比率を指定する。通常の chunk 処理では、直前の prompt chunk（実装上は各 piece）の所要時間にこの値を掛けた時間を decode に割り当てる。prompt の計算や token 選択を変える値ではなく、読み込みと slot decode の時間配分を変える値である。CUDA/HIP 側の `engine/src/program/generate.cpp` と SYCL 側の `engine/sycl/src/program/generate.cpp` に読み取りがある（`engine/src/program/generate.cpp:20737-20745`, `engine/sycl/src/program/generate.cpp:11453-11461`）。

## 値と判定

両方の実装で `std::getenv` の結果を `std::atof` に渡し、設定時は `std::max(0.0, ...)` で下限だけを 0 にする。未設定時だけ既定値 0.5。上限 clamp、文字列全体の parse 成功検査、エラー報告はない。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効・0扱いになる値 |
|---|---|---|---|
| CUDA/HIP の engine 経路、および SYCL の通常 `--batch` 経路 | `0.5` | `0.5`, `1`, `2` など、`atof` が正の数として読む値。上限なし | `0`, 負値、空文字、`true`、数値に変換できない文字列は 0。`0anything` は数値部分の `0`、`1anything` は数値部分の `1` として扱われる |

`atof` のため、先頭空白は許容され、後続の非数値文字列は検査されない。大文字小文字を区別する真偽値比較はなく、`true` / `false` はどちらも数値変換できず 0 になる。負数は 0 に clamp され、正数に上限はない。値が 0 以下なら通常の chunk 経路では slot decode を挟まず次の prompt chunk へ進む（`engine/src/program/generate.cpp:21390-21396`, `engine/sycl/src/program/generate.cpp:11541-11546`）。

CUDA/HIP の pipelined groups では、`STRATA_PIPED_READ_PIECE` が正の piece を有効にしたとき、この値を piece 時間に掛けた decode budget に使う。さらに `STRATA_PIPED_DECODE_MAX_MS` が正なら上限、`STRATA_PIPED_DECODE_MIN_MS` は下限として適用するため、share が 0 でも正の floor があれば decode budget は正になり得る。floor が 0 で budget が 0 でも、`piped_decode` は `do-while` で少なくとも一度 `pump(true)` を実行する。これらの別変数は未設定時 0 で、cap/floor としては無効（`engine/src/program/generate.cpp:21279-21296`, `engine/include/strata/program/batch_read.hpp:69-75`, `engine/src/program/generate.cpp:21302-21315`, `21379-21387`）。

## 有効になる条件

- engine の `--batch` が有効（`o.batch > 0`）で、prompt 読み込みの該当境界に少なくとも一つ active な batch slot があること。`batch_on()` は active slot の有無で判定する（`engine/src/program/generate.cpp:16856`, `engine/src/program/generate.cpp:21297-21300`）。
- 上の条件を満たさない場合、通常の CUDA/HIP chunk loop では `batch_on()` が false なら decode loop は実行されない。SYCL では `--batch` 無効時、piped 時、または layer split で active slot がないとき、prompt 全体を `sp.run` 系へ渡す分岐があり、この変数による chunk 間 decode は行わない（`engine/sycl/src/program/generate.cpp:11471-11482`）。
- CUDA/HIP の layer-split pipelined groups は通常の chunk 間経路とは別扱いで、`STRATA_PIPED_READ_PIECE` が正でないと piece が作られず、通常の `run` に進む。その場合この変数の share budget は使われない（`engine/src/program/generate.cpp:21297-21300`, `engine/src/program/generate.cpp:21343-21345`; `engine/include/strata/program/batch_read.hpp:56-67`）。
- `STRATA_PIPED_READ_PIECE` が正の pipelined 経路では、decode budget は share と `STRATA_PIPED_DECODE_MAX_MS` / `STRATA_PIPED_DECODE_MIN_MS` から算出され、piece ごとに pipeline を drain する（`engine/src/program/generate.cpp:21279-21296`, `engine/src/program/generate.cpp:21379-21387`）。
- 1 GPU の `STRATA_BATCH_CONCURRENT_READ` 経路が条件を満たすと prompt read 中も slot windows を並行実行するが、読み込み後の chunk boundary の decode budget は別途この share から計算される。条件には `!piped`, `stages.empty()`, `o.batch > 0`, `o.no_prefill_borrow`, active slot、画像なし、`!kvg.on` がある（`engine/src/program/generate.cpp:20893-20905`, `engine/src/program/generate.cpp:21390-21396`）。

## 実行時の詳細

値は両方の engine 実装で関数内 `static const double` として、その読み取り箇所に初めて到達した時に読み込まれ、そのプロセス内で cache される。初回読み取り後の環境変更は反映されない。未設定時の 0.5 はコード上の fallback であり、CLI 引数との値の優先順位はない（`engine/src/program/generate.cpp:20742-20745`, `engine/sycl/src/program/generate.cpp:11458-11461`）。

通常経路は prompt の chunk を読み終えた時点で経過時間を測り、その時間に share を掛けた budget の間 `batch_step()` を少なくとも一度実行し、budget 経過または active slot がなくなるまで続ける。したがって実際の decode 時間は window 単位で budget を超えることがある。layer split の pipelined piece 経路では、`piped_decode_budget_ms` が share を piece の時間に掛け、設定された cap/floor を適用してから `pump(true)` と `pipe_drain()` を行う（`engine/src/program/generate.cpp:21390-21399`, `engine/src/program/generate.cpp:21302-21320`, `engine/include/strata/program/batch_read.hpp:72-75`）。

実行中に失敗すると、通常経路では `batch_step()` の失敗を `batch_fatal` とし、エラー文字列 `a batch window failed` を設定して prompt 処理を失敗させる。pipelined 経路の失敗文字列は `a pipelined batch window failed`（`engine/src/program/generate.cpp:21302-21315`, `engine/src/program/generate.cpp:21390-21396`; SYCL: `engine/sycl/src/program/generate.cpp:11541-11546`）。

## ログと測定値

通常経路の各 chunk 後に詳細 trace が有効なら、stderr に `strata trace: prompt chunk to ..., then the slots decoded ... ms` を出す。prompt 完了時に一度でも slot decode を挟んだ場合は、stderr に `strata batch: the prompt was read in ... parts, the slots decoding ... ms between them` を出す。pipelined piece 経路は各 piece の decode 有無と行数を stderr に記録する（`engine/src/program/generate.cpp:21400-21403`, `engine/src/program/generate.cpp:21632-21634`, `engine/src/program/generate.cpp:21373-21387`; SYCL: `engine/sycl/src/program/generate.cpp:11549-11552`, `engine/sycl/src/program/generate.cpp:11692-11694`）。

`docs/BATCHING.md:406-409` は、1 枚の RTX 5090、layer split なし、6 slots で、冷たい 64K prompt に 4 streams が加わる例として、`STRATA_BATCH_DECODE_SHARE=2.0` の longest stop 2.4 秒 / TTFT 37.2 秒、`=0` の longest stop 14.0 秒 / TTFT 13.8 秒を記載する。資料にある条件付きの記録であり、他構成の性能値を示すものではない。

## 根拠

- `engine/src/program/generate.cpp:20737-20745` — CUDA/HIP 側の読み取り、既定値、chunk 間 decode の説明。
- `engine/sycl/src/program/generate.cpp:11453-11461` — SYCL 側の読み取りと既定値。
- `engine/src/program/generate.cpp:16856`, `21297-21300`, `21390-21396` — active slot 条件と通常経路の budget。
- `engine/sycl/src/program/generate.cpp:11471-11482`, `11541-11552` — SYCL の適用条件・decode loop・trace。
- `engine/include/strata/program/batch_read.hpp:56-75`, `engine/src/program/generate.cpp:21279-21296`, `21379-21387` — pipelined piece 経路と cap/floor。
- `engine/src/program/generate.cpp:20893-20905`, `21302-21320` — concurrent read 経路と slot decode。
- `engine/src/program/generate.cpp:21632-21634`, `engine/sycl/src/program/generate.cpp:11692-11694` — prompt 完了時のログ。
- `docs/BATCHING.md:406-409` — 条件付きの測定値。
