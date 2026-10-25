# `STRATA_PREFILL_RING`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

プロンプト prefill で、GPU にまだ常駐していない expert blob をホスト側から先読みして置く device ring の slot 数を指定します。大きい ring は、計算中に次の expert blob をより多く転送できる一方、blob ごとの device buffer を多く確保します。これは `Prefill` の sizing と初期化に使われ、通常の decode ring や外部 driver の設定ではありません。

## 値と判定

両実装とも `std::getenv("STRATA_PREFILL_RING")` の結果を `std::atoi` に渡します。値全体の検証はありません。未設定なら自動選択、設定済みなら変換結果を使います。空文字、数字で始まらない文字列は `atoi` により 0 になり、負数も下限処理の対象になります。`atoi` は先頭空白と符号を許し、数字の後ろにある文字列を無視します（例: `32junk` は 32）。

| 設定 | ring の扱い |
|---|---|
| 未設定 | backend、pinned share、fused 経路などから選ぶ既定値。下記参照 |
| `8` または `8junk` | 明示的に `STAGE`（8 slot）を返す。大きな chunk でも routed-only staging を選ぶ |
| その他の整数、空文字、無効文字列 | `atoi` の結果を使用。16 未満は 16、backend の `ring_cap()` 超過は上限に丸める |
| 上記の ring 値でも chunk が小さい | `STRATA_PREFILL_STREAM_MIN`（既定 1024 token）未満では `STAGE` に戻る。ただし明示値が 8 の場合は先に `STAGE` が返る |

CUDA/HIP 実装では、通常の未設定値は pinned share が 90% 以上なら fused ring で 1024、それ以外で 384 slot、pinned share が 90% 未満なら 96 slotです。これは上限処理前の値で、`ring_cap()` は通常 512、非 native の fused 経路では最大 1024 なので、native fused 経路などでは 1024 が 512 に丸められます。HIP で `STRATA_HIP_WMMA` が先頭文字 `1` の場合、かつこの変数が未設定で layer split override もない場合は、閾値以上の chunk で 96 slot、未満で 8 slot を使います。

SYCL も通常の既定値・上限式は同じですが、`STRATA_PREFILL_STREAM_ALL` による追加条件があります。未設定時は非常駐 expert の割合が 10% 未満の場合だけ大きい ring を使い、`STRATA_PREFILL_STREAM_ALL` の先頭文字が `1` なら割合にかかわらず許可します。明示値 `8` はこの条件より前に返るため routed-only staging を指定できます。条件を満たさない場合は 8 slot です。

## 有効になる条件

- 変数は CUDA/HIP (`src/prefill/prefill.cpp`) と SYCL (`sycl/src/prefill/prefill.cpp`) の prefill 実装で読み取られます。Metal の `Prefill::init` は別経路で、この ring sizing は通りません。
- `STRATA_PREFILL_STREAM_MIN` 以上の prompt chunk で、かつ backend 固有の stream-all 条件を通った場合に、8 より大きい ring が先読み ring として使われます。未満では `STAGE` になり、通常の大きな先読み経路になりません。
- layer split が `Prefill::set_ring_override()` で既定 ring を指定する場合でも、環境変数が設定されていれば環境変数の値が優先されます。環境変数が未設定なら、override が byte-budget ring より先に選ばれます。
- 変数自体は `static` cache されず、`ring_slots(T)` の呼び出しごとに `getenv` と変換が行われます。自動 chunk の容量見積もりと `Prefill::init` の両方が ring 数を参照するため、プロセス中に環境値を変更すると後続の見積もりと初期化で異なる値になる可能性があります。通常の起動設定では起動前に指定します。

## 実行時の詳細

`ring_slots(T)` の戻り値は prefill 初期化時に `m.ring` となり、その数だけ `MAXBLOB()` bytes の expert staging buffer を確保します。`bytes_needed()` / `bytes_needed_owned()` も同じ ring 数を容量見積もりに含めます。CUDA/HIP の先読み経路は ring index を `issued % m.ring` で循環し、転送済み blob を計算側が使い終わるまで slot を再利用しません。したがって指定数は「expert 数」ではなく、同時に保持する whole-blob buffer の数です。

serve の自動 chunk 選択では、解決後の chunk と slot 数を stderr に `strata serve: prompt chunk auto: ... tokens, a ...-slot ring` と表示します。layer split が override を決めた場合にも、解決 slot 数を stderr に表示します。

## 資料との照合

`docs/DETAILS.md` は 0.1.39b 以降、ring をモデル pack の blob bytes に応じて調整し、`--prefill auto` が chunk と ring のメモリを考慮すると説明しています。これは自動 sizing の説明です。`STRATA_PREFILL_RING` を明示すると、ソースの `ring_slots()` がその自動値・override・byte-budget 値より先に指定値を使います。`docs/INTEL.md` では SYCL の `STRATA_PREFILL_RING=8` を routed-only staging に使った例、`docs/AMD_HIP.md` では HIP の値 96 と既定 384 の比較例があります。これらの資料上の測定例は各記載機材・設定に限られ、他環境の性能を示すものではありません。

## 根拠

- `src/prefill/prefill.cpp:214-230,257-290,292-314` — 既定値、cap、値の parse、HIP WMMA 特例、chunk 閾値。
- `sycl/src/prefill/prefill.cpp:126-172,197-230` — SYCL の既定値、cap、`STRATA_PREFILL_STREAM_ALL` 条件と parse。
- `include/strata/prefill/prefill.hpp:84-121` — override、byte-budget、自動 chunk と解決 ring の API 契約。
- `src/prefill/prefill.cpp:1082-1093,1318-1335,1868-1870,1879-1931` — 初期化と容量見積もりでの ring 使用。
- `src/prefill/prefill.cpp:2338-2342,2436-2445,2479-2504` — 先読みと循環 slot の使用。
- `src/program/generate.cpp:7000-7010,7470-7474` — layer split override と自動 chunk/ring のログ。
- `docs/DETAILS.md:1926-1939`, `docs/INTEL.md:320-324`, `docs/AMD_HIP.md:341-342` — 資料上の説明と条件付き測定例。
