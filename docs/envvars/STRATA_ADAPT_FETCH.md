# `STRATA_ADAPT_FETCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の `strata generate` と `strata serve` で、PCIe share が GPU キャッシュにコピーする expert miss を、キャッシュへの admission にも使う制御値です。通常は PCIe share で取得した expert を staging してその window の計算に使います。有効時は、条件を満たす取得 expert を既存の resident expert の slot に直接コピーし、residency table を更新します。`1` は tier 自身の次回 swap を残し、`2` は PCIe admission があった layer について tier 自身の swap をその round で行わないようにします。CPU/GPU のどちらで expert を計算するかやキャッシュの置換先が変わり得るため、出力が bit-for-bit 同一とは限りません。`adapt_fetch()` と `ExpertDispatch::fetch_can()` が設定と実行条件を扱います（`engine/src/program/generate.cpp:2342-2347,15067-15089,24580-24603`; `engine/src/core/expert_source.cpp:5271-5275,5637-5676`; `engine/src/program/generate.cpp:15355-15366`）。

## 値と判定

`adapt_fetch()` は `std::getenv` で値を取得し、未設定なら `0`、設定済みなら `std::atoi` の結果を `0` から `2` に clamp します。文字列全体の妥当性検査はありません。空文字・数値で始まらない文字列は `atoi` が `0` にし、数値の後ろの文字は無視されます。符号や先頭空白も `atoi` の変換規則に従います（`engine/src/program/generate.cpp:2345-2347`）。

| 条件 | unset | 有効になる値 | 無効になる値・境界外入力 |
|---|---|---|---|
| 通常の読み取り | `0` | clamp 後の `1` または `2`。例: `1`, `2`, `2tail`, `3`（`3` は `2` に clamp） | 無効化される例: 空文字、`true`、`0anything`, `-1`（`-1` は `0` に clamp）。`0` は無効。負数は `0`、`2` より大きい数は `2` に clamp |
| CUDA の NVIDIA 既定値適用時 | 条件を満たすカードでは未設定の値を `2` にする。それ以外は `0` | 上記に加え、明示値が優先 | 対象変数が空文字を含め設定済みなら自動既定値を注入しない。明示 `0` は無効のまま |

`apply_nv_defaults()` は対象変数の設定有無だけを調べます。従って空文字や `0` もユーザー設定として扱い、既定値で上書きしません（`engine/src/core/nv_defaults.cpp:222-239`）。自動既定値は `STRATA_DEFAULTS=026` が有効なら適用されず、カード種別ごとの perf default が無効な場合も適用されません（sm_86: `STRATA_SM86_PERF=0`、sm_89: `STRATA_SM89_PERF=0`、sm_120: `STRATA_SM120_PERF=0`; `engine/src/core/nv_defaults.cpp:41-43,73,75-83,104-106,130-135`）。

## 有効になる条件

- 有効値は `1` または `2` ですが、実際に admission を行うには adaptive tier、residency table、expert cache、GPU plan、PCIe share が必要です。`--adapt-every` と `--adapt-swaps` が有効であることも必要です（`engine/src/program/generate.cpp:15067-15084,24570-24598`）。
- `generate` と `serve` の開始時判定は、residency table がない、cache slot が 0、`--spec-split`、layer split / peer tier / helper GPU、`--adapt-async`、`--pipeline-windows`、`--batch`、`STRATA_ADAPT_OVERLAP=1`、`--pcie-mode dma` / `direct`、GPU plan がない、PCIe share が 0、resident RAM mode などを無効理由として扱います。理由は各開始ログに出ます（`engine/src/program/generate.cpp:15055-15077,24571-24589`）。
- 実際の dispatch 側でも、`fetch_can()` は `pcie_mode == 2`、staging destination が存在すること、peer/helper/swap-space がないこと、PCIe share が正であること、対象 layer が PCIe から供給可能なことを要求します（`engine/src/core/expert_source.cpp:5271-5275`）。
- `fetch_on` はその window に PCIe share で処理する miss 数 `m` が 1 以上のときだけ成立します。tail skip された miss、resident expert、peer/helper が持つ expert、pinned でない blob は admission 対象になりません（`engine/src/core/expert_source.cpp:5491-5500,5555-5571,5563-5568`）。
- CUDA build の既定値は、全可視 CUDA device の compute capability が同一のときだけ適用されます。既定 `2` の対象は compute capability 12.x かつ main card の VRAM が 16 GiB 以下、または sm_86 / sm_89 かつ 13 GiB 以下です。main card は `STRATA_PRIMARY_DEVICE`（未設定なら device 0）から選び、範囲外の device 番号は 0 に戻します。混在 compute capability ではこの既定値適用経路を通りません（`engine/src/program/generate.cpp:4421-4449`; `engine/src/core/nv_defaults.cpp:21-27,73,102,134`）。
- `STRATA_ADAPT_ASYNC` による adaptive-async 自動選択でも値を参照し、値が正なら async tier の自動選択を抑止します。明示 `--adapt-async` の選択は別経路です（`engine/src/program/generate.cpp:11777-11795`; `engine/include/strata/core/adapt_async_default.hpp:41-60`）。

## 実行時の詳細

`adapt_fetch()` の値は関数内 `static const` に一度だけ保持され、最初の呼び出し時点のプロセス環境を使います。後から環境を変更しても再読込されません。CUDA では GPU 情報を確認して `apply_nv_defaults()` が未設定値を補ってから engine の switch を読むため、その自動設定値も cache されます（`engine/src/program/generate.cpp:2345-2347,4421-4449`）。

開始時の条件を通ると、`drive.d.fetch_admit` に値を設定します。`STRATA_ADAPT_FETCH_MIN` と `STRATA_ADAPT_FETCH_MARGIN` が設定されていれば `atof` で読み、未設定時はそれぞれ `1.0` と `0.5` です。各 layer-window で usage の多い PCIe miss を share の候補にし、tier が退ける最小 usage の resident expert と比較します。miss usage が `fetch_min` 以上で in-flight でなく、resident victim より `fetch_margin` 以上大きければ、その victim の slot にコピーして host residency table を更新します（`engine/include/strata/core/expert_source.hpp:674-691`; `engine/src/core/expert_source.cpp:5640-5676`）。

`1` の場合、tier は次の adapt round で通常の候補選択を続けます。`2` では PCIe admission が発生した layer の取得済み・pinned expert を tier の候補から外し、同 layer では tier 自身の swap を休ませます。PCIe share がなかった layer や admission されなかった expert は通常の tier 対象です（`engine/src/program/generate.cpp:15355-15366`）。

## ログと測定値

有効値が実行条件に合わない場合、stderr に無効理由を示す `strata serve: STRATA_ADAPT_FETCH is off (%s)` または `strata generate: STRATA_ADAPT_FETCH is off (%s)` が出ます。自動既定値を注入した値が未使用なら `STRATA_ADAPT_FETCH=2 (the default for this card) is not used in this run (%s)` と出ます。有効時は閾値を含む `STRATA_ADAPT_FETCH=%d: the PCIe share takes each layer's most-routed misses and admits those routed >= ...` の開始行が出て、値が `2` なら tier 自身のコピーが無効である旨も付加されます（`engine/src/program/generate.cpp:15073-15088,24586-24602`）。

`strata generate` で `STRATA_ADAPT_FETCH_VERIFY` が設定されている場合（値の内容は問わず）、admission された slot を read-back 検証します。不一致時は `strata: FETCH VERIFY layer ...`、周期的な集計は `strata: fetch verify: ... admitted slots read back, ... differ` です。最後の標準出力には admission 数と round あたり平均が出ます。検証 API の失敗そのものは上記の不一致ログに記録されます（`engine/src/program/generate.cpp:24596-24599,25104-25123,25317-25319`）。

性能・出力に関する資料値は `docs/DETAILS.md:1262` に記載されています。そこでは IQ3_S / RTX PRO 5000 / 3,896-slot cache / `--pcie-frac 0.25` の4 roundで decode `=2` +10.2%、`=1` +5.0%、および別条件の2x RTX 5060 Ti 16 GB / UD-Q4_K_XL の3 paired roundsで decode medians 1.087–1.325、hit rate 54.4%から62.0%、KL ratio 0.948 [0.830, 1.063] とされています。これらは資料記載の特定条件での結果です。

## 根拠

- `engine/src/program/generate.cpp:2342-2347` — parse、clamp、関数内 cache。
- `engine/src/program/generate.cpp:4421-4449` — CUDA での既定値適用前後と main card 選択。
- `engine/src/core/nv_defaults.cpp:21-27,37-43,73,102,130-135,222-239` — GPU / VRAM 条件、世代別 default、明示設定優先。
- `engine/src/program/generate.cpp:15055-15089,24570-24603` — serve / generate の有効条件、理由ログ、補助 threshold 読み取り。
- `engine/src/core/expert_source.cpp:5271-5275,5555-5571,5637-5679` — dispatch 条件、PCIe miss 選別、slot admission。
- `engine/src/program/generate.cpp:15355-15366` — 値 `2` と tier 自身の swap の関係。
- `engine/src/program/generate.cpp:11777-11795`; `engine/include/strata/core/adapt_async_default.hpp:41-60` — async 自動選択との関係。
- `engine/src/program/generate.cpp:25104-25123,25317-25319` — verify と集計出力。
- `docs/DETAILS.md:1262` — 条件付きの測定記載。
