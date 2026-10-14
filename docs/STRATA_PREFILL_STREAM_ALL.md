# `STRATA_PREFILL_STREAM_ALL`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL の prompt prefill で、VRAM cache にない expert を layer ごとに先読みする stream-all walk を選びます。有効時は各 chunk で、cache にない expert を routed かどうかにかかわらず layer / expert ID 順にリングへ流します。無効時は routed-only staging になり、その chunk で必要な expert を stage します。この設定は decode の expert 選択を変えるものではありません。

この環境変数を読む実装は `sycl/src/prefill/prefill.cpp` の `ring_slots()` だけです。CUDA 側の同名読み取りはありません。

## 値と判定

`std::getenv()` の結果が null かどうかと、設定値の先頭 1 文字だけを見ます。数値変換や文字列全体の比較はしません。

| 値 | `stream_all_env` | 結果 |
|---|---:|---|
| unset | -1 | VRAM cache 外の `(layer, expert)` ペアの割合 `g_nonres_share` が `0.10` 未満なら有効。それ以外は無効 |
| 先頭文字が `1` | 1 | 有効（既定の cache 条件を上書き） |
| 設定済みで先頭文字が `1` 以外 | 0 | 無効（既定の cache 条件を上書き）。空文字もここに含む |

したがって `1`, `10`, `1anything` は有効で、`0`, `true`, 空文字は無効です。大文字小文字、空白、後続文字は解釈されません。

`stream_all_env` は関数内の `static const int` です。プロセス内で最初に `ring_slots()` が呼ばれたときの値を保存し、後から環境を変更しても再評価しません。`ring_slots()` は prompt buffer のサイズ計算や chunk/ring 計画からも呼ばれるため、最初の実際の prefill より前に値が確定することがあります。

## 有効になる条件

値の判定が有効でも、stream-all walk には次の条件があります。

- `ring_slots(T)` が `STAGE` (= 8) より大きいリングを返すこと。chunk 長 `T` が `stream_all_min()` 以上であること（既定 1,024 token）。
- 実行時に expert source (`m.src`) があること。
- 変数が unset の場合は、`g_nonres_share < 0.10` であること。`generate.cpp` は cache 外のペア数を `host_res` 全体で割って設定するため、これは VRAM cache が全ペアの 90% を超えて保持する条件です。明示値 `1` はこの割合条件を上書きしますが、リングや chunk の条件は上書きしません。
- `STRATA_PREFILL_RING` が `8` を指定していないこと。実装は `atoi()` の結果が `STAGE` なら stream-all 判定より先に routed-only を返します。たとえば `8`, `8junk` はこの経路で無効化します。`STRATA_PREFILL_RING` のその他の値はリング選択に影響し、stream-all の必要リング数は少なくとも 16、最大 `ring_cap()` に丸められます。
- SYCL HIP で `STRATA_HIP_WMMA` の先頭文字が `1`、かつ `STRATA_PREFILL_RING` 未設定・ring override なしの場合は特例です。この経路は `ring_slots()` の早期 return で、chunk がしきい値以上なら 96 slot を返します。そのため `STRATA_PREFILL_STREAM_ALL=0` や nonresident share の既定条件を通らず、実行ループでは stream-all になります。

`STRATA_PREFILL_STREAM_MIN` は chunk のしきい値を変えます。`std::atoll()` で読み、未設定時は 1,024 です。別のリング設定や既定 ring が 8 以下になる場合、環境変数を `1` にしても walk は行われません。

## 実行時の詳細

`ring_slots()` は `STRATA_PREFILL_RING` と SYCL HIP の `STRATA_HIP_WMMA` 特例を確認し、通常経路では ring budget / pinned share に基づく slot 数 `r` を決めます。その後、stream-all が不許可なら 8 slot の `STAGE` を返します。許可されていれば `r` を `[16, ring_cap()]` に収めた値を使いますが、`T < stream_all_min()` の chunk では再び 8 slot を返します。`ring_cap()` は fused-ring 対応時 1,024、それ以外は 512 です。HIP 特例は `STRATA_HIP_WMMA` 有効時、`STRATA_PREFILL_RING` と ring override がない場合に早期 return するため、環境変数の明示的な off 指定が効かない経路です。

`Prefill::init()` はこの slot 数で ring buffer を確保します。chunk の実行ループは `m.ring > STAGE && T >= stream_all_min() && m.src != nullptr` を stream-all の条件として扱います。有効な chunk では layer を先行して走査し、VRAM cache にない expert をリングへ入れます。通常の routed-only 経路は layer 内の routing 結果に沿って stage します。つまり環境変数が直接指定するのは walk の許可で、コピー量や適用 chunk は cache、source、ring、chunk 条件に依存します。

この変数自体についての専用ログは見つかりません。`--prefill auto` では解決した chunk と ring slot 数を stderr に出すコードがありますが、stream-all の有効/無効を直接表示するログではありません（`sycl/src/program/generate.cpp:6806-6813`）。

## 文書と測定値

`docs/INTEL.md` は、stream-all が cache 外の全 expert を先読みする経路であり、unset 時は VRAM が 90% 超のペアを保持する場合に既定で有効、`=1` / `=0` で強制できると説明しています。資料の Coder 測定では、40K int8 prompt が routed-only 1,106 tok/s、stream-all 1,160 tok/s、128K int8 + KV streaming が 897 / 920、128K k8v4 が 1,006 / 1,041、256K int8 + KV streaming が 760 / 780 でした。資料は出力が同じとも記載しています。これらは同資料の測定条件に限られ、他の pack や GPU の性能を示すものではありません。資料はまた、RAM mirror に expert の 1/4 を保持する IQ2_XS で stream-all が 2,184-token prompt を約 560 から 254 tok/s に落とした例を示し、cache 割合を既定条件にする理由を説明しています。

## 根拠

- `sycl/src/prefill/prefill.cpp:121-124`: `STRATA_PREFILL_STREAM_MIN` の既定値・`atoll` 変換・static cache。
- `sycl/src/prefill/prefill.cpp:125-127, 1843-1845`: pinned share と nonresident share の状態。
- `sycl/src/prefill/prefill.cpp:197-229`: ring の通常値、環境値の先頭文字判定、unset 時の割合条件、HIP WMMA 早期 return、slot clamp、chunk threshold。
- `sycl/src/program/generate.cpp:6018-6032`: host-resident 配列から cache 外割合を計算して渡す箇所。
- `sycl/src/prefill/prefill.cpp:1217-1229, 2458-2463, 2517-2559`: ring buffer 確保、実行時条件、layer / expert の stream-all 計画。
- `docs/INTEL.md:613-625`: 既定条件、強制値、測定値と出力に関する資料の記述。
