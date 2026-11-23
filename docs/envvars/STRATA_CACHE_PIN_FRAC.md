# `STRATA_CACHE_PIN_FRAC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`--serve` の適応 fetch が GPU expert cache の resident expert を入れ替えるとき、profile の上位 expert を何 slot 分 eviction 候補から除外するかを割合で指定する。値から pin 数を計算するだけでは保護処理は走らず、実際には `STRATA_ADAPT_FETCH` が有効な fetch 経路でのみこの pin 配列が参照される。通常の起動時 profile fill や適応 tier 自身の入れ替えをこの変数が直接変更するコードはない（`engine/src/program/generate.cpp:14883-14904`、`engine/src/core/expert_source.cpp:5637-5658`）。

## 値と判定

serve の cache/profile 条件を満たした初期化時に `std::getenv` で一度読み、共通 helper が `std::atof` で数値変換する。未設定または空文字なら、resident slot が全 expert の 25% 未満の場合だけ割合 `0.25`、それ以外は `0`。空でない値は先頭から `atof` が読める数値を使い、`0.0..0.75` に clamp する。文字列全体の妥当性検査、空白除去、エラー通知はない。

| 条件 | unset | 有効になる値 | 無効・境界の例 |
|---|---|---|---|
| `--serve` の pin 数計算 | resident slot が全 expert の 25% 未満なら 0.25、それ以外は 0 | `0.25` なら resident slot 数の約 25%（端数切り捨て）を上限に profile 上位を pin | 空文字は unset と同じ。`0`、`0abc`、`-1`、`abc` は 0 slot。`1` は 0.75 に clamp。`0.5tail` は数値接頭辞 `0.5` として扱う |

算出数は `(int64_t)(resident_slots * frac)` で小数部を切り捨てる。したがって割合が正でも計算結果が 0 なら pin は作られず、ログも出ない。`atof` 後の clamp 以外に値域検証はなく、CLI 引数でこの割合を直接上書きする経路もない（`engine/include/strata/core/low_vram_rules.hpp:104-116`）。

## 有効になる条件

- `--serve` で、読み込んだ `--expert-profile` が空でなく、host residency table があり、GPU cache slot が 1 つ以上あり、全 expert が GPU 常駐ではないこと。これを満たさない場合は `STRATA_CACHE_PIN_FRAC` の読み取り自体が行われない（`engine/src/program/generate.cpp:14840-14857,14883-14885`）。
- pin 対象は profile の先頭から走査し、host residency table 上で現在 GPU resident の expert を最大 `pin_n` 個選ぶ。 profile 外や非 resident の expert は pin されない。profile のロード失敗は `strata generate: <error>` を stderr に出して終了コード 1 で返る（`engine/src/program/generate.cpp:6718-6724,14889-14904`）。
- pin が eviction 防止として効くには、さらに `STRATA_ADAPT_FETCH` が正の値で、適応 fetch が使える実行経路であること。serve 側では residency table/cache slot があることに加え、single GPU、非 peer・非 helper、非 split、非 `--spec-split`、非 `--adapt-async`、非 `--pipeline-windows`、非 batch、`STRATA_ADAPT_OVERLAP` が有効でないこと、PCIe share と GPU plan が使えることなどが gate される。`STRATA_ADAPT_OVERLAP` は値の先頭文字が `1` なら有効扱い（Windows HIP では `STRATA_WIN_HIP_RISKY` による拒否判定もある）。`--pcie-mode dma` / `direct`、resident RAM mode も対象外（`engine/src/program/generate.cpp:14960-14977,2264-2283`）。
- 適応 fetch が off でも、上記 profile/cache 条件を満たせば pin 数の計算と pin 件数ログまでは行われる。しかし `fetch_pin` を参照するのは `fetch_on && fetches > 0` の fetch eviction 処理だけである（`engine/src/core/expert_source.cpp:5555-5558,5637-5658`）。
- 同じ `generate.cpp` の通常 generate 経路では `fetch_pin` への設定が見つからず、この変数による pin 配列は設定されない（唯一の設定箇所: `engine/src/program/generate.cpp:14897`）。
- 名前は `terminal/data/settings-register.json:3339` にも設定項目 metadata として載るが、Strata が実行時に環境値を読む箇所は serve 側の `std::getenv` だけである。索引 `000_envvers.md` の候補名だけでなく、この読み取りと helper の全参照を確認した。

## 実行時の詳細

profile と cache の準備後、serve の初期化で `live_gpu_slots` を primary と各 stage の cache slot 数から求め、`total_expert_pairs` を layer 数と expert 数の積として算出する。helper はこの2数と環境値から pin 数を計算する（`engine/src/program/generate.cpp:14855-14857,14883-14885`、`engine/include/strata/core/low_vram_rules.hpp:106-116`）。

pin 数が正の場合、profile 順に resident expert の bitmap を作り、その配列を `drive.d.fetch_pin` に渡す。fetch eviction は各 layer で resident かつ現在の window で使われていない候補を選ぶ際、pin bitmap が立っている expert を飛ばす。そのため保護されるのは適応 fetch が入れ替え先を選ぶ際の eviction 候補からであり、初期 cache 配置、cache 容量、route 選択を変える設定ではない（`engine/src/program/generate.cpp:14887-14898`、`engine/src/core/expert_source.cpp:5640-5671`）。

環境値そのものはこの初期化箇所で都度読み、static cache には保存しない。初期化を通過した後のプロセス内環境変更は、すでに作られた pin 配列には反映されない。なお `STRATA_ADAPT_FETCH` 自体は `adapt_fetch()` 内の関数 static に一度だけ読み込まれ、`atoi` の値を `0..2` に clamp する。実値 1 または 2 で fetch が有効になる（`engine/src/program/generate.cpp:2340-2343`）。

## ログと測定値

pin が1件以上作られた場合、stderr に次の形式で出る（`%lld` は実数値）。

```text
strata serve: tiny expert cache: pinned top %lld of %lld profile experts against eviction (STRATA_CACHE_PIN_FRAC=0 turns it off)
```

表示される2数は順に実際に pin できた件数と `live_gpu_slots`。profile/cache gate を通らない、pin 数が 0、または resident profile expert が見つからない場合はこの行は出ない。`STRATA_ADAPT_FETCH` が無効でも pin 作成が行われればログは出るため、このログ単独では fetch eviction での効果を示さない。Strata の `docs/DETAILS.md` にこの環境変数名の記載は確認できなかったため、性能・正確性の測定値は記載しない（`engine/src/program/generate.cpp:14896-14904`）。

## 根拠

- `engine/src/program/generate.cpp:14855-14857,14883-14904` — slot 数、環境読み取り、profile 順の pin bitmap 作成、serve ログ。
- `engine/include/strata/core/low_vram_rules.hpp:104-116` — default、`atof`、clamp、slot 数への変換。
- `engine/src/core/expert_source.cpp:5271-5275,5555-5558,5637-5672` — fetch 条件と eviction 候補から pin 済み expert を除外する処理。
- `engine/include/strata/core/expert_source.hpp:674-685` — `fetch_pin` の役割。
- `engine/src/program/generate.cpp:6718-6724,14960-14994` — profile の読み込み失敗経路と serve 側適応 fetch gate。
