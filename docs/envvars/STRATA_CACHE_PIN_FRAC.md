# `STRATA_CACHE_PIN_FRAC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`--serve` の適応型 VRAM expert cache が入れ替え候補を選ぶとき、`--expert-profile` の上位から指定割合の常駐 expert を eviction 対象から外す。さらに PCIe fetch admission が有効な場合も、その expert を eviction 候補にしない。値は pinned expert 数を決める割合で、0 は pinning を無効にする。`--adapt-swaps` は入れ替え数を制御する別設定で、この pinning の有効化を上書きしない（`engine/src/program/generate.cpp:14976-15000,15349-15379`、`engine/src/core/expert_source.cpp:5640-5676`）。

この環境変数を読むのは CUDA/HIP の `generate.cpp` server 経路である。profile が空でないこと、host residency 表があり、GPU cache に空き枠があり、全 experts が常駐していないことが読み取り前提になる（`engine/src/program/generate.cpp:14976-14980`）。

## 値と判定

`std::getenv` の結果を `low_vram_pin_slots` に渡し、非空文字列は `std::atof` で変換して `0.0..0.75` に clamp する。数値文字列全体の検証はなく、`atof` が読める先頭の数値部分が使われる。変換後の割合に常駐枠数を掛け、小数部を切り捨てた数を pin する（`engine/src/program/generate.cpp:14978-14980`、`engine/include/strata/core/low_vram_rules.hpp:120-129`）。

| 状態・入力 | 判定 |
|---|---|
| 未設定（`getenv` が null） | `STRATA_TINY_CACHE` が正確に `1` のときだけ helper を呼ぶ。cache が experts の 25% 未満なら既定割合 0.25、それ以外は 0。`STRATA_TINY_CACHE` が有効でなければ pin 数 0。 |
| 空文字 | 未設定相当。`STRATA_TINY_CACHE=1` なら上記の条件付き既定値、それ以外は pin 数 0。 |
| 数値 `0`（例: `0`, `0.0`） | 明示値として変換され 0 に clamp されるため無効。`STRATA_TINY_CACHE=1` の既定 pinning も抑止する。 |
| 正の数（例: `0.25`, `1`） | 上限 0.75。たとえば `1` は 0.75 として扱う。割合×常駐枠数を切り捨てるため、結果が 1 未満なら pin は発生しない。 |
| 負数（例: `-1`） | 0 に clamp され、pin しない。 |
| 上限超過（例: `0.8`, `96`） | 0.75 に clamp される。 |
| 数値で始まる文字列（例: `0.5junk`） | `atof` の数値 prefix が変換され、0.5 として扱う。先頭空白も `atof` の変換規則に従う。 |
| 数値に変換できない文字列（例: `true`, `junk`） | `atof` は 0 を返し、pin しない。無効値の警告やエラー処理はない。 |

空でない値があれば `STRATA_TINY_CACHE` が未設定または `1` 以外でもこの値による pinning を試みる。`STRATA_TINY_CACHE` は未設定・空値かどうかではなく、文字列全体がちょうど `1` かで判定される（`engine/src/program/generate.cpp:14979-14980`、`engine/include/strata/core/low_vram_rules.hpp:106,120-129`）。

## 有効になる条件

- `--serve` の適応型 cache 経路に入っていること。通常の非 server 生成経路にはこの環境変数の読み取りがない（読み取り箇所は `engine/src/program/generate.cpp:14978` のみ）。
- `--expert-profile` からランキングが読み込まれ、`profile` と `host_res` が空でないこと。profile の読み込みに失敗すると `strata generate: <理由>` を stderr に出して終了コード 1 で戻る（`engine/src/program/generate.cpp:6746-6751,14976-14980`）。
- GPU expert cache の合計 `live_gpu_slots` が正で、全 experts がすでに常駐していないこと。全 experts 常駐・0 枠・空 profile の場合、環境変数は読み取られない（`engine/src/program/generate.cpp:14932-14933,14948-14950,14976-14980`）。
- pin 数が正で、profile の順に見た pair が `host_res` 上で resident であること。該当 pair が不足すれば、要求数より実際の pin 数が少なくなる（`engine/src/program/generate.cpp:14981-14998`）。
- `STRATA_TINY_CACHE=1` は未設定または空の `STRATA_CACHE_PIN_FRAC` に 25% 未満 cache の既定 pinning を与える。明示した非空値は同変数の有無にかかわらず使われる（`engine/src/program/generate.cpp:14978-14980`）。
- pin は adapt worker が動くときに resident expert の eviction 候補を除外する。PCIe fetch admission 経由の入れ替えにも `fetch_pin` が参照されるが、その経路自体には PCIe share と `STRATA_ADAPT_FETCH` の有効化など別条件がある（`engine/src/program/generate.cpp:15067-15088,15349-15379`、`engine/src/core/expert_source.cpp:5555-5558,5640-5659`）。
- `--adapt-swaps 0` などで通常の適応型入れ替えが停止しても pin 数の計算自体は独立して行われる。ただし eviction がなければ pin の実効的な差はない。明示 `--adapt-swaps` が pin 数や割合を上書きする処理はない（`engine/src/program/generate.cpp:4202,14976-15002,15349-15379`）。

## 実行時の詳細

profile をロードして GPU cache と host residency を整えた後、serve 経路の初期化中に `std::getenv("STRATA_CACHE_PIN_FRAC")` を一度呼び、`pinned_pair` を構築する。関数 static ではないが、同じ初期化中に何度も読み直す処理でもないため、プロセス実行中に環境値を変えてもこの run の pinning 設定は更新されない（`engine/src/program/generate.cpp:14976-15000`）。

pin 数は `profile` の先頭から順に `(layer, expert)` を調べ、`host_res` が resident を示す pair だけを最大 `pin_n` 個選ぶ。配列は `drive.d.fetch_pin` に渡され、通常の適応型入れ替えでは `pinned_pair` が立った resident pair を victim 候補 `vict` に入れない。fetch admission では `fetch_pin` の立った pair を victim 探索から飛ばす（`engine/src/program/generate.cpp:14981-14998,15354-15379`、`engine/src/core/expert_source.cpp:5653-5659`）。

影響は cache の eviction 選択であり、profile の順位や token 計算を直接変更する処理はここにはない。pin で除外した枠の代わりの victim が見つからなければ、その入れ替えは成立しない（`engine/src/program/generate.cpp:15364-15375`）。

## ログと測定値

1 件以上 pin したときだけ stderr に次の行を出す。表示するのは実際に pin できた数と cache 枠数である。pin 数 0、適用条件不成立、profile 内の該当 resident 不足ではこのログは出ない。無効な文字列専用の警告・終了経路はない（`engine/src/program/generate.cpp:14981-14998`）。

```text
strata serve: tiny expert cache: pinned top <pinned_ct> of <live_gpu_slots> profile experts against eviction (STRATA_CACHE_PIN_FRAC=0 turns it off)
```

`low_vram_rules.hpp` のコメントは、RTX 5080（sm_120、16 GB）、Qwen3.8-Flash-Next IQ2_XS、`--expert-cache 3000`（experts の 12.2%）、同一 binary、arms alternating、5 rounds の比較を記録する。0.1.65 比で tiny-cache rules 有効時の decode は code / chat / 8K document でそれぞれ -22% / -18% / -13%、`--adapt-swaps 96` 明示時は -10% / -10% / -3%、さらに pin 無効（`STRATA_CACHE_PIN_FRAC=0` と `96`）では -5.5% / -6.4% / -4.4% と記載されている。これは設定の組合せの比較であり、この環境変数単独の効果値とは読めない。同コメントは cache 7.6%（`--expert-cache 1800`）の途中 2 rounds についても、rules 有効時 -25% / -18% / -18%、96 swaps 時 -10% / -8% / -5% と記す（`engine/include/strata/core/low_vram_rules.hpp:100-105`）。`docs/DETAILS.md:147` は `STRATA_TINY_CACHE=1` と低 coverage の概要を記すが、この環境変数単独の動作説明はない。

## 根拠

- 候補名の環境読み取りは `engine/src/program/generate.cpp:14978` の `std::getenv` 1 箇所。ほかの名前参照は `engine/include/strata/core/low_vram_rules.hpp:103,105,119` のコメントと `terminal/data/settings-register.json:3386-3396` の登録情報。
- 割合変換、clamp、既定値、slot 数: `engine/include/strata/core/low_vram_rules.hpp:118-129`。
- profile 読み込み: `engine/src/program/generate.cpp:6746-6751`。
- pin bitmap の設定とログ: `engine/src/program/generate.cpp:14976-15000`。
- 通常の適応型 eviction 候補からの除外: `engine/src/program/generate.cpp:15349-15379`。
- fetch admission の eviction 候補からの除外: `engine/src/core/expert_source.cpp:5640-5676`。
- CLI `--adapt-swaps` の parse と pin とは独立した処理: `engine/src/program/generate.cpp:4202,14976-15002`。
