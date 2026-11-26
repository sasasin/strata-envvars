# `STRATA_ADAPT_NOWAIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

適応 expert tier が前の refill で入れ替えた expert のコピーを待たずに、次の verify window を進めるかを切り替える。`1` のとき pending コピーの完了確認を非ブロッキングで行い、完了していなければその window では pending の適用を保留する。unset または `1` 以外では、`STRATA_ADAPT_LAG` の window 数に達した時点でコピー完了を待つ。CUDA/HIP 共通生成経路と SYCL 生成経路に実装がある（`engine/src/program/generate.cpp:2237-2241,22812-22835`、`engine/sycl/src/program/generate.cpp:1377-1381,12739-12743`）。

これは adaptive tier のコピー完了待ち方を変える設定であり、adaptive tier 自体を有効化する設定ではない。adaptive tier が無効なら待機対象となる refill がなく、`STRATA_ADAPT_NOWAIT` の分岐による効果もない（`engine/src/program/generate.cpp:15001-15002,15251-15252`）。

## 値と判定

両実装とも `std::getenv` の結果を関数内 `static const bool` に保存し、値の先頭 1 文字が文字 `'1'` かだけを判定する。文字列全体の parse や真偽値変換はしない（`engine/src/program/generate.cpp:2238-2240`、`engine/sycl/src/program/generate.cpp:1378-1380`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| CUDA/HIP 共通生成経路、SYCL 生成経路 | `adapt_nowait()` は `false` | `1`, `10`, `1anything`（先頭が `1`） | 空文字、`0`, `true`, `01`, ` 1`、その他先頭が `1` でない値 |
| CUDA sm_60 の起動時既定値適用後 | 通常は unset のままなら既定表が `1` を設定。ただし `STRATA_SM60_PERF` が `0` で始まる場合は表を適用しない | 利用者が事前設定していないとき、単一 compute capability sm_60 の既定表が設定する `1` | 明示した空文字を含む利用者設定は既定値適用を止める。`STRATA_SM60_PERF=0...` も既定表を止める |

CUDA の `apply_nv_defaults` は env が既に存在するかだけで既定値の適用を判断するため、空文字も利用者設定として優先される。sm_60 の表は `STRATA_SM60_PERF` が先頭 `'0'` の場合に適用されず、その表に `STRATA_ADAPT_NOWAIT=1` が含まれる（`engine/src/core/nv_defaults.cpp:15-18,164-175,222-234`）。

## 有効になる条件

- adaptive tier が動作すること。少なくとも生成経路では `--adapt-every` と `--adapt-swaps` が正で、expert cache に空き枠があり全 expert resident ではない場合に usage が初期化される。条件を満たさない場合、この設定が変える pending refill はない（`engine/src/program/generate.cpp:15001-15002,24563-24570`）。
- コピー待ちの pending swap があること。空のとき `apply_pending` は pending copy を同期しない。`1` の場合は CUDA event の query が未完了なら pending の適用を返し、完了済みなら続行する（`engine/src/program/generate.cpp:15197-15215`）。
- 適応 tier の window を進める CUDA/HIP または SYCL の生成経路であること。値の分岐は `generate.cpp` のそれぞれの経路に置かれている（`engine/src/program/generate.cpp:22808-22835,25101-25103`、`engine/sycl/src/program/generate.cpp:12739-12743,14109-14114`）。
- `STRATA_ADAPT_LAG` との相互作用: `STRATA_ADAPT_NOWAIT` が有効なら、通常の次の window で `apply_pending(false)` を呼び、`adapt_lag()` による wait 分岐は選ばれない。無効なら `pending_age` が `adapt_lag()` に達するまで待機を遅らせる（`engine/src/program/generate.cpp:2248-2250,22818-22835`）。
- CUDA sm_60 の既定値設定は CUDA build に限られる。起動時に全可視 NVIDIA device が同じ compute capability であるとき `apply_nv_defaults` が呼ばれ、sm_60 表は `STRATA_SM60_PERF` が `'0'` で始まらない場合に適用される。SYCL/Metal はこの `nv_defaults.cpp` による既定値設定対象ではない（`engine/src/program/generate.cpp:4421-4449`、`engine/src/core/nv_defaults.cpp:164-175`、`engine/include/strata/core/nv_defaults.hpp:48-52`）。

## 実行時の詳細

`adapt_nowait()` の最初の呼び出し時に環境を読み、その後は同一プロセス内の呼び出しで cache 済み bool を返す。実行中に環境を変更しても反映されない（`engine/src/program/generate.cpp:2238-2240`、`engine/sycl/src/program/generate.cpp:1378-1380`）。CUDA の sm_60 既定値は `apply_nv_defaults` が各生成 switch の読み取り前に設定する。利用者が先に設定した値は内容にかかわらず保持する（`engine/src/program/generate.cpp:4425-4449`、`engine/src/core/nv_defaults.cpp:227-234`）。

CUDA/HIP の serve 生成ループと通常の speculative decode ループでは、nowait が有効だと各 window の前に `apply_pending(false)` を呼ぶ。未完了の適応コピーがあれば event query が成功するまで pending を適用せずに戻り、window は続行する。無効時は pending がないか、待ち window 数 `adapt_lag()` に達したとき `apply_pending(true)` を呼び、adapt event と必要な stage event を同期してから table と residency state を更新する（`engine/src/program/generate.cpp:15197-15235,22808-22835,25101-25103`）。

適応 tier がコピーを待たずに eviction を進める組み合わせでは、device residency table の更新を次の window の前に反映するため `evict_sync` を設定し、必要に応じて変更 entry を patch する経路がある。同期済みの適応 tierではこの条件に入らない（`engine/src/program/generate.cpp:15236-15257,24615-24630`; `engine/include/strata/core/expert_source.hpp:662-669`）。SYCL でも speculative generation と通常 generation の window 前に同じ nowait / lag 分岐がある（`engine/sycl/src/program/generate.cpp:12739-12743,14109-14114`）。

## ログと測定値

この変数専用の有効・無効ログや失敗メッセージは、確認した読み取り・分岐箇所にはない。CUDA の sm_60 既定表が1つ以上の環境変数を設定した場合は、`apply_nv_defaults` が stderr に `strata: sm_60 (Pascal): ... speed switches on by default ...` の行を出し、設定した名前を列挙する。利用者がこの変数を設定済みなら既定適用リストに入らず、この行で当変数は列挙されない（`engine/src/core/nv_defaults.cpp:222-255`）。

`docs/DETAILS.md` の現行表には sm_86 既定値として本変数が載っているが、現在の `nv_default_env` の sm_86 表は `STRATA_ADAPT_LAG=2` などを設定し、本変数を含めない。一方、現行コードの sm_60 表は本変数を `1` に設定する。文書の当該表と実装に差があるため、既定条件はソースコードに基づいて記載した（`docs/DETAILS.md:1478-1493`、`engine/src/core/nv_defaults.cpp:41-58,164-175`）。

## 根拠

- 値の読み取り・cache: `engine/src/program/generate.cpp:2237-2250`; `engine/sycl/src/program/generate.cpp:1377-1390`
- pending swap 適用と wait/query: `engine/src/program/generate.cpp:15197-15235,22808-22835,25101-25103`; `engine/sycl/src/program/generate.cpp:12739-12747,14109-14124`
- 適応 tier 有効条件と eviction 同期: `engine/src/program/generate.cpp:15001-15002,15236-15257,24563-24570,24615-24630`; `engine/include/strata/core/expert_source.hpp:659-669`
- CUDA の既定値適用条件と優先順位: `engine/src/program/generate.cpp:4421-4449`; `engine/src/core/nv_defaults.cpp:15-18,164-175,222-255`; `engine/include/strata/core/nv_defaults.hpp:48-52`
- 既定値資料との比較: `docs/DETAILS.md:1478-1493`
