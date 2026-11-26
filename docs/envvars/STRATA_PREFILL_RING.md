# `STRATA_PREFILL_RING`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

プロンプト処理で非 resident expert を先読みする streamed ring の slot 数を指定する。各 slot は expert blob 1 個分の device buffer で、ring の数は slot の再利用間隔と確保量を変える。chunk の大きさ、生成 token の選択そのものをこの変数が指定するわけではない。実装は CUDA/HIP 共通の `ring_slots()` と SYCL 側の同名関数にある（`engine/src/prefill/prefill.cpp:843-879`、`engine/sycl/src/prefill/prefill.cpp:291-324`）。

## 値と判定

両実装とも `std::getenv("STRATA_PREFILL_RING")` の有無を調べ、設定されていれば `std::atoi` で整数化する。文字列全体の検証はなく、空文字・数値で始まらない文字列は `0` になり、後続文字は無視される。したがって `16junk` は `16`、`8junk` は特別値 `8` と同じ扱い。`atoi` のため先頭空白と符号も数値変換に従う。値が設定されていること自体が既定値分岐を抑止するので、空文字も「未設定」ではない（同上）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効・特別扱いになる値 |
|---|---|---|---|
| CUDA/HIP 共通の通常分岐、SYCL | 下記「unset 時の既定値」 | `16` 以上。上限を超える値は backend 上限までに clamp | `8` は `STAGE`（8 slot の routed-only staging）としてそのまま返る。`0`、負値、`1`〜`7`、`9`〜`15`、空文字、非数値文字列は `atoi` 後に 16 slot へ clamp。chunk が stream 条件を満たさない場合は 8 slot に戻る |
| 上限 | CUDA/HIP: fused ring が有効で native pack でなければ 1024、それ以外 512。SYCL: fused ring が有効で非-native pack の場合 1024、それ以外 512 | その backend の上限まで | 上限より大きい値は上限に clamp |
| HIP の matrix-core 特別分岐（`STRATA_USE_HIP`、変数 unset のときだけ） | WMMA 要求時は chunk 条件に応じ 8 または 96。gfx12 の条件では最大 256 / 192 slot | 変数を何らかの値で設定するとこの特別分岐を抑止し、通常の `atoi` 分岐へ | ― |

通常分岐では、設定値が `8`（`STAGE`）なら即座に routed-only staging を指定する。その他は `16` 未満を 16 に、ring 上限より大きい値を上限に丸める。`0` も「自動」や既定値にはならず、16 に丸められる。数値変換に失敗した文字列も同様。変換不能な範囲外整数について `atoi` の結果は実装で保証されないため、利用可能な値としては扱わない（`engine/src/prefill/prefill.cpp:843-879`、`engine/sycl/src/prefill/prefill.cpp:291-324`）。

## 有効になる条件

- 通常分岐で ring が 16 以上になっても、chunk `T` が `stream_all_min()` 未満なら実際の ring は `STAGE`（8）。既定の floor は 1024 token だが `STRATA_PREFILL_STREAM_MIN` や CPU share の条件で変わる（`engine/src/prefill/prefill.cpp:387-388, 843-879`、`engine/sycl/src/prefill/prefill.cpp:215-217, 291-324`）。
- SYCL の通常分岐では `STRATA_PREFILL_STREAM_ALL` が stream-all を許可しない設定なら、明示値が `8` 以外でも実 ring は `STAGE` に戻る。値の先頭文字が `1` なら強制許可、unset 時は `g_nonres_share < 0.10` の場合に許可する。CUDA/HIP 共通コードの ring 解決にはこの変数の分岐はない（`engine/sycl/src/prefill/prefill.cpp:308-323`、`engine/src/prefill/prefill.cpp:843-879`）。
- `STRATA_PREFILL_RING` は `Prefill::set_ring_override()` による layer-split ring override より優先し、auto chunk sizing の `set_ring_budget()` による値よりも優先する。CUDA/HIP の通常分岐ではこの順序で選択される（`engine/src/prefill/prefill.cpp:873-879`）。SYCL でも同じく設定値が override / budget の選択より先に使われる（`engine/sycl/src/prefill/prefill.cpp:307-310`）。
- unset 時に限り、HIP の WMMA 要求があると特別分岐が通常の既定値を置き換える。`STRATA_USE_HIP` build では WMMA 要求かつ layer-split override がない場合、gfx12 以外などは 96 slot（chunk が floor 未満なら 8）。gfx12 で WMMA が有効かつ `STRATA_GFX12_RING` が `0` で始まらない場合、chunk 6,144 以下は最大 256、6,144 超〜12,288 未満は最大 192、12,288 以上は 96（いずれも chunk が floor 未満なら 8）。`STRATA_PREFILL_RING` を空文字でさえ設定するとこの特別分岐には入らない（`engine/src/prefill/prefill.cpp:843-867`）。
- 通常分岐の unset 既定値は pinned share が 90% 以上なら fused ring 時 1024、通常 ring 時 384、90% 未満なら 96 slot。その後、auto byte-budget ring が有効で chunk が設定された `small_max` を超える場合は budget ring を使う。CUDA/HIP の `STRATA_RING_BYTES=0` はこの budget 分岐を止めるが、明示した `STRATA_PREFILL_RING` は抑止しない（`engine/src/prefill/prefill.cpp:808-841, 868-879`、`engine/sycl/src/prefill/prefill.cpp:264-290, 302-323`）。
- `--prefill N` は chunk size を決め、ring の解決はその chunk `T` を使う。従って `T` が stream floor 未満なら大きい値を指定しても通常分岐では 8 slot になる。`--prefill auto` の serve sizing は resolved ring を計算してログに出し、環境変数が設定されていれば budget ring よりその値を使う（`engine/src/program/generate.cpp:11346-11360, 11474-11517, 12747-12764`、`engine/sycl/src/program/generate.cpp:6713-6727, 6750-6767, 7386-7397`）。
- 生成経路で `ExpertSource` が無い場合は expert streaming 用 ring の効果はない。ring の大きさは `Prefill::init` の buffer layout と stream 判定に使われる（`engine/src/prefill/prefill.cpp:2262-2269, 2865-2889`）。

## 実行時の詳細

読み取りは `ring_slots(T)` が呼ばれるたびに `getenv` し、環境値自体を static cache しない。関数は buffer sizing（`bytes_needed*`）、auto sizing の `ring_slots_for()`、および `Prefill::init` からも呼ばれる。ring 数は init で `m.ring` に入り、所有 buffer なら `max_blob × max(ring, stage slots)` 分を carve し、streamed expert を ring slot に割り当てる（`engine/src/prefill/prefill.cpp:843-879, 2865-2889, 3774-3788, 3810`、SYCL: `engine/sycl/src/prefill/prefill.cpp:291-324, 1780-1797, 2497-2521`）。

環境変数を実行中に変更した場合の同期・再初期化はこの関数では行わない。buffer sizing と init の間に環境値を変えた場合の整合性も保証するコードは確認できないため、起動前に設定する。`--prefill N` と異なり、この値自体は chunk 長を直接変えない。auto mode の sizing 判定では ring の必要 slot 数として考慮される（`engine/src/program/generate.cpp:11346-11360, 11474-11517`）。

## ログと測定値

環境変数専用の parse 警告や無効値エラーはない。serve の `--prefill auto` では解決後の値を `strata serve: prompt chunk auto: %lld tokens, a %lld-slot ring` と stderr に出す。layer split override が別途設定された場合のログは `strata serve: layer split: ... the prompt path's streamed ring %d slots` だが、環境変数が設定されていれば実効 ring は `STRATA_PREFILL_RING` の値から解決される（`engine/src/program/generate.cpp:11828-11844, 12747-12755`）。

ring buffer を含む device buffer の carve に失敗した場合は `prefill: device buffers for a chunk of ... tokens do not fit (...)` を返す。これは ring 値専用のエラーではない（`engine/src/prefill/prefill.cpp:2737-2746`）。測定値は記載しない。コードコメントや `docs/DETAILS.md` の既存測定は環境・モデルなどが限定され、今回の環境変数の一般的な効果を保証しない。

## 根拠

- CUDA/HIP の値判定と backend 条件: `engine/src/prefill/prefill.cpp:808-879`
- CUDA/HIP での ring 確保と実行時使用: `engine/src/prefill/prefill.cpp:2865-2889, 3774-3788`
- SYCL の値判定と ring 確保: `engine/sycl/src/prefill/prefill.cpp:264-324, 1780-1797`
- layer split override の設定と serve の表示: `engine/src/program/generate.cpp:11828-11844, 12747-12755`
- auto chunk sizing の ring budget 判定: `engine/src/program/generate.cpp:11346-11360, 11474-11517`; SYCL: `engine/sycl/src/program/generate.cpp:6713-6767`
