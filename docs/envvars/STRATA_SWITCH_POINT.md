# `STRATA_SWITCH_POINT`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

CUDA の単一 GPU・非 resident expert を含む prompt prefill で、staged walk から streamed walk に切り替える chunk token 数（stream floor）を固定の 1,024 からカード別の推定値へ変える。閾値以上の chunk はカードが保持しない全 expert を stream し、それ未満は routing された expert だけを stage する。閾値は cache の resident/total expert 数、expert blob 平均サイズ、起動時 link probe、SM 数から計算される。カードが全 expert を保持する場合や計算 floor が既定値のままなら変更はない。CUDA の既定有効クラスは NVIDIA discrete、単一 GPU、link probe 成功、compute capability 8.6。`=1` はそのクラス外の CUDA カードにも計算を要求する。HIP は常に無効。`src/prefill/prefill.cpp` の `default_stream_floor()` と `switch_point_on()` が実装箇所。実際に prefill の chunk 経路を変える floor と、CPU share の limit にも影響する（下記）。`include/strata/prefill/switch_point_rule.hpp:1-14, 67-124`。

`docs/SETTINGS.md:366` は対象を「NVIDIA and AMD」としているが、実装は HIP build では常に false を返すため、この表記は現行コードと一致しない。`data/settings-register.json:39522-39550` の「CUDA builds only; HIP never」という注記は実装と一致する。

## 値と判定

`switch_point_env()` は最初に呼ばれた時の環境を関数内 `static` に保存する。未設定または空文字は unset (`-1`) と同じ。`env_state()` は文字列全体が厳密に `"1"` のときだけ on (`1`)、それ以外の空でない文字列は off (`0`) とする。数値 parse、trim、大文字小文字変換はしない。したがって実行中の環境変更は反映されない。`src/prefill/prefill.cpp:449-455`; `include/strata/prefill/switch_point_rule.hpp:113-124`。

| 条件（build / device） | unset（未設定・空文字） | 有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA、既定クラス（NVIDIA discrete、1 GPU、link probe 成功、CC 8.6） | 有効 | `1` | `0`, `true`, `01`, `1 ` など `"1"` 以外の非空文字列 |
| CUDA、既定クラス外 | 無効 | `1` | `0`, `true`, `01`, `1 ` など |
| HIP build | 無効 | なし（`1` でも無効） | unset、空文字、その他すべて |

明示的に `1` でなければならないため、`0` は無効化し、`true` や `01` も有効化しない。`STRATA_SWITCH_POINT=0` は既定クラスでも計算 floor を止める。実装では `#if defined(STRATA_USE_HIP) || defined(__HIPCC__) || defined(STRATA_HIP_GFX906)` の場合に環境判定より先に false を返す。`src/prefill/prefill.cpp:459-471`; `include/strata/prefill/switch_point_rule.hpp:113-124`。

## 有効になる条件

- `STRATA_SWITCH_POINT=1` の場合は CUDA build であること。未設定時は既定クラス条件（NVIDIA discrete、単一 GPU、成功した link probe、compute capability 8.6）を満たすこと。HIP では有効にならない。`src/prefill/prefill.cpp:459-471`; `include/strata/prefill/switch_point_rule.hpp:101-111, 120-124`。
- card expert share の情報が設定済みであること。`generate.cpp` は `!multi_gpu && o.batch <= 0` の単一 GPU・batch slot なし経路で `set_card_expert_share()` を呼び、cache の resident slots、layers × experts、平均 blob、`o.pcie_probe_gbps` を渡す。カード情報は CUDA runtime から SM 数、compute capability、integrated/discrete も取得する。`src/program/generate.cpp:11555-11560`; `src/prefill/prefill.cpp:3413-3427`。
- 計算対象 floor が既定の 1,024 であること。モデル layout による既定 floor が 64 など別値なら switch-point 計算には入らない。card/link 情報が未確定または不明なら既定値を返し、その呼び出しでは cache しない。全 expert が resident の場合も 1,024 を維持する。`src/prefill/prefill.cpp:558-583`; `include/strata/prefill/stream_floor_rule.hpp:12-22`; `include/strata/prefill/switch_point_rule.hpp:67-93`。
- `STRATA_PREFILL_STREAM_MIN` が設定され、`atoll()` の結果が 0 以上なら、その値が stream floor として先に返るため、switch-point floor は使われない。文字列全体の検証はなく、空文字・非数値は `atoll()` により 0、負値は switch-point を含む既定規則へ進む。`src/prefill/prefill.cpp:614-624`。
- CPU share が有効な場合、staged chunk の上限にも switch-point が関係する。既定 share が arm され、明示 `STRATA_PREFILL_CPU_SHARE_MAX` がなく、peer CPU share でない CUDA 経路では、switch-point の floor が 1,024 より大きければその 1.6 倍を 256-token grid に切り下げた limit を使う。`STRATA_PREFILL_CPU_SHARE_MAX` を明示した場合はその値（最低 1,024）が優先する。`src/prefill/prefill.cpp:3633-3646, 681-695`; `include/strata/prefill/switch_point_rule.hpp:94-99`。

## 実行時の詳細

switch-point の値自体は `switch_point_env()` の初回呼び出し時に一度だけ読み、以降は static cache を使う。カード情報は prefill 初期化時の `set_card_expert_share()` で記録される。`default_stream_floor()` は expert layout が未ロードの早期呼び出しでは既定値を返して cache せず、layout/card 情報が使える段階で floor を決めて atomic cache に保存する。`src/prefill/prefill.cpp:449-455, 558-583, 3413-3427`。

カード別 floor は non-resident 数 `X = total_pairs - resident_slots` に対する staged/streamed walk の推定コストを 256-token 単位で走査し、既定 1,024 から最大 8,192 の範囲で決める。card scaling は mean blob MB / link GB/s でコピー項、`84 / SM数` で計算項を補正する。1,024 で staged が優位でなければ既定値、card 情報が未知または全 expert resident の場合も 1,024。`include/strata/prefill/switch_point_rule.hpp:15-99`。

決定した `stream_all_min()` は chunk が streamed walk を使うか staged walk を使うかに使われ、関連する ring slot、buffer sizing 等の prefill 設計にも参照される。`src/prefill/prefill.cpp:614-624, 2184-2192, 4390`。CLI の `o.prefill_chunk` は prompt chunk の大きさを決める入力だが、switch-point floor を直接上書きする引数ではない。CPU share が arm される場合は `arm_cpu_share()` がその limit を floor × 1.6 に設定する条件があり、明示 `STRATA_PREFILL_CPU_SHARE_MAX` が優先する。`src/program/generate.cpp:21555-21561`; `src/prefill/prefill.cpp:3633-3646, 681-695`。

## ログと測定値

計算 floor が 1,024 から変わった場合、通常の MMQ build は stderr に `prefill: prompt chunks of %lld tokens or more stream every expert the card does not hold ...` の行を出す。build without MMQ (`STRATA_PF_OWN_ONLY`) では floor 表示を deferred startup line として flush する。floor が変わらない場合、この switch-point 用ログは出ない。`src/prefill/prefill.cpp:572-595`; `src/prefill/prefill.cpp:549-556, 626-635`。

ヘッダーの測定根拠は RTX A6000 (48 GB, 12 GB/s link)、Qwen3.8-Flash-Next UD-Q4_K_XL、CPU share off の fit と、RTX A6000/A4000 の crossing の記述である。別カードへの一般的な性能保証ではなく、ヘッダー自身も既定クラス外の CUDA カードは未測定と記している。`include/strata/prefill/switch_point_rule.hpp:5-14, 43-66, 101-111`。

## 根拠

- 読み取り、static cache、CUDA/HIP gating、floor 反映、ログ: `src/prefill/prefill.cpp:441-471, 558-595`。
- 値判定、default device class、cost/floor 計算: `include/strata/prefill/switch_point_rule.hpp:15-124`。
- card data の設定と単一 GPU 経路: `src/prefill/prefill.cpp:3413-3427`; `src/program/generate.cpp:11555-11560`。
- floor の優先関係と prefill path での利用: `src/prefill/prefill.cpp:614-624, 2184-2192, 4390`。
- CPU share limit への連動と明示上書き: `src/prefill/prefill.cpp:3633-3646, 681-695`。
- docs との比較: `docs/SETTINGS.md:366`; `data/settings-register.json:39522-39550`。
