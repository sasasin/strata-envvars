# `STRATA_TINY_CACHE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

`--serve` の起動時に、VRAM 上の expert cache が全 expert 数の 15% 未満の場合、既定の適応 swap 数を抑える処理を有効にする。また profile が読み込まれているとき、profile 上位の VRAM resident expert を eviction から守る pinning の既定割合（cache slot の 25%）を有効にする。設定がなければこの変数による swap 抑制と pinning は opt-in のまま。ただし pinning は `STRATA_CACHE_PIN_FRAC` だけでも個別に有効化できる。読み取りと分岐は `engine/src/program/generate.cpp` の serve 初期化にある。(`engine/src/program/generate.cpp:14943-14980`, `engine/include/strata/core/low_vram_rules.hpp:100-129`)

## 値と判定

`std::getenv` が返す文字列を `tiny_cache_rules_enabled` に渡し、未設定でないことに加えて、最初の文字が `'1'` かつ次が終端文字であることを確認する。文字列全体が厳密に `"1"` の場合だけ有効で、数値変換はしない。空文字、`"0"`、`"true"`、`"on"`、`"01"`、`"1anything"`、`"1 "`、`" 1"` は無効。大文字小文字や空白の正規化もない。(`engine/include/strata/core/low_vram_rules.hpp:100-106`)

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `--serve` の tiny-cache 規則 | swap 抑制なし。`STRATA_CACHE_PIN_FRAC` も空または未設定なら pinning なし | `1` のみ | 空文字、`0`、`true`、`on`、`01`、`1x`、空白を含む値など、厳密な `1` 以外 |

## 有効になる条件

- swap 抑制は `--serve` の初期化で cache coverage `live_gpu_slots / total_expert_pairs` が 15% 未満であり、かつ `STRATA_ADAPT_MID` による中間 coverage 規則の分岐が選ばれない場合に判定される。`STRATA_ADAPT_MID` の適用範囲は 15% 以上なので、この tiny-cache 分岐の coverage では該当しない。適応 swap 数が 0 以下なら、helper は値を変更しない。(`engine/src/program/generate.cpp:14948-14974`, `engine/include/strata/core/adapt_coverage_rules.hpp:37-46`, `engine/include/strata/core/low_vram_rules.hpp:108-115`)
- swap 抑制は `--adapt-swaps N` が明示されていれば適用されず、その値を保持する。未指定時の初期値は 96。未指定かつ cache coverage が 12.5% 未満なら最大 16、12.5%以上15%未満なら最大32に抑える。これは上限なので、元の値がすでに小さければ増やさない。(`engine/src/program/generate.cpp:1084-1085`, `engine/src/program/generate.cpp:4202`, `engine/include/strata/core/low_vram_rules.hpp:108-115`)
- pinning には空でない expert profile、host expert 配列、1 slot 以上の VRAM cache が必要で、全 expert が VRAM resident の場合は行わない。`STRATA_TINY_CACHE=1` なら `STRATA_CACHE_PIN_FRAC` が unset または空のとき、cache coverage が25%未満で slot 数の25%を pin する。非空の `STRATA_CACHE_PIN_FRAC` がある場合は、この変数が無効でも pinning 判定に進む。(`engine/src/program/generate.cpp:14976-14980`, `engine/include/strata/core/low_vram_rules.hpp:118-129`)
- `STRATA_CACHE_PIN_FRAC` は `atof` で変換され、0から0.75に clamp される。文字列 `"0"`、負数、数値に変換できない文字列は割合0となる。`STRATA_TINY_CACHE=1` と併用して `STRATA_CACHE_PIN_FRAC=0` を指定すれば pinning を止める。空文字は明示割合として扱われず、tiny-cache 既定値に戻る。(`engine/include/strata/core/low_vram_rules.hpp:118-129`, `engine/src/program/generate.cpp:14978-14980`)
- `--adapt-every 0` などで適応 tier が停止していても、上記 profile 条件が満たされれば pinning は独立して有効になり得る。一方 swap 数抑制は適応 swap 数が0以下なら実際の変更がない。(`engine/src/program/generate.cpp:14965-15001`)

## 実行時の詳細

serve 初期化時に `std::getenv("STRATA_TINY_CACHE")` を2箇所で評価する。1箇所目は coverage 15% 未満の適応 swap 数調整、2箇所目は profile pin 数の決定に使う。どちらもリクエスト処理ループより前の起動時設定であり、リクエストごとの再読込や関数内 static cache はない。したがって、起動後に環境値を変更しても、その serve プロセスで設定済みの値には反映されない。(`engine/src/program/generate.cpp:14943-15002`)

swap 抑制後の `o.adapt_swaps` は adaptive tier が各ラウンドで実行する swap 件数の上限として使われる。pin された profile expert は PCIe fetch の victim 選択と adaptive eviction の victim 候補から除外される。pin 対象は profile 順に選ばれ、実際に1件以上 pin された場合は `drive.d.fetch_pin` に設定される。(`engine/src/program/generate.cpp:14981-14995`, `engine/src/program/generate.cpp:15353-15379`, `engine/src/core/expert_source.cpp:5653-5670`)

## ログと測定値

swap 数が変わった場合は stderr に `strata serve: tiny expert cache (%lld of %lld slots, %.1f%%): dampening adaptive swaps %d -> %d to avoid PCIe thrashing (--adapt-swaps N overrides)` が出る。pin が1件以上設定された場合は stderr に `strata serve: tiny expert cache: pinned top %lld of %lld profile experts against eviction (STRATA_CACHE_PIN_FRAC=0 turns it off)` が出る。変数が無効、条件不足、または swap 数が変わらない場合、これらの該当ログは出ない。起動時に失敗または終了させる専用経路はこの処理にはない。(`engine/src/program/generate.cpp:14965-14999`)

`docs/DETAILS.md` は RTX 5080 の測定例と従来 16 swap / 上位 profile pin の説明を載せるが、同文書の「13-22% decode」記述はコード上の保証ではなく測定結果として扱う。測定条件の詳細はソースコメントにあり、RTX 5080（sm_120、16 GB）、Qwen3.8-Flash-Next IQ2_XS、`--expert-cache 3000`（expert の12.2%）、同一 binary、各 arm 1回起動、交互実行5 round。現行コードではこの規則は `STRATA_TINY_CACHE=1` の opt-in。(`docs/DETAILS.md:147`, `engine/include/strata/core/low_vram_rules.hpp:100-105`)

## 根拠

- 値判定と規則の説明: `engine/include/strata/core/low_vram_rules.hpp:100-129`
- serve 初期化、coverage 分岐、swap 調整、profile pin: `engine/src/program/generate.cpp:14943-15002`
- adaptive eviction 候補と pin 除外: `engine/src/program/generate.cpp:15353-15379`
- PCIe fetch の victim 選択と pin 除外: `engine/src/core/expert_source.cpp:5653-5670`
- 設定引数の既定値と明示指定: `engine/src/program/generate.cpp:1084-1085`, `engine/src/program/generate.cpp:4202`
- ソース記載の測定条件: `engine/include/strata/core/low_vram_rules.hpp:100-105`
