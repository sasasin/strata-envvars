# `STRATA_PREFILL_STREAM_MIN`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

プロンプト処理で、非 resident expert を全件ストリーミングする経路へ切り替える token 数の下限を設定します。これより小さい chunk は routed-only の staging 経路を使います。CUDA では、条件がそろえば fused int8 expert 経路に入る chunk の下限と、その経路用バッファの大きさにも使われます。SYCL でも ring の大きさ、全 expert のストリーミング、および fused layout の閾値に使われます。

## 値と判定

どちらの backend も `std::atoll()` で読み、整数への完全な文字列検証はしません。数値の前置部分を変換し、変換できない文字列や空文字は `0` になります。符号付き値も変換されます。

| 値 | CUDA (`src/prefill/prefill.cpp`) | SYCL (`sycl/src/prefill/prefill.cpp`) |
|---|---|---|
| unset | 通常は `1024`。CUDA の CPU prefill share が有効なら、share 用の上限値を使う | `1024` |
| `0` または数値でない文字列 | しきい値 `0` を明示 | しきい値 `0` を明示 |
| `N`（`N >= 0`） | `N` をしきい値として使用し、CPU share の上書きを抑える | `N` をしきい値として使用 |
| 負数 | 非負の環境値としては採用せず、unset と同じ fallback（CUDA CPU share、なければ `1024`） | 負数をそのまましきい値として使用 |

`atoll` のため、たとえば `128xyz` は `128`、`xyz` は `0` として扱われます。大文字小文字や空白の特別な処理はありません。両実装とも最初の `stream_all_min()` 呼び出しで環境値を `static` に保存します。以後プロセス内で環境を変更しても、この値は再読込されません。

## 有効になる条件

- CUDA で全 expert をストリーミングするには、chunk がこの値以上で、`ExpertSource` があり、ring が staging 専用の `STAGE`（8 slots）より大きい必要があります。条件を満たすかは `Prefill` 初期化、ring sizing、chunk 実行時の各所で使われます。適応 CPU share が有効な CUDA 経路では、unset/負数のとき `STRATA_PREFILL_CPU_SHARE_MAX`（通常 3072、既定 share の範囲では 1024）がしきい値になります。非負の `STRATA_PREFILL_STREAM_MIN` はこの fallback を優先します。
- CUDA の fused layout は、上記に加えて fused ring が有効で、MMQ plan に対象 layer があり、expert source がある場合に限られます。Q2_0 pack の CUDA fused kernel は sm_80 以上で、通常は `STRATA_PF_FUSED=0` で無効化できます。HIP の Q2_0 fused kernel は `STRATA_PF_FUSED` の先頭文字が `1` のときだけ有効です。native pack は fused native kernel 対応 layer など別条件を満たす必要があります。
- SYCL では `ring_slots()` が大きい ring を返すことも条件です。既定では VRAM cache が expert pair の90%以上を保持する場合に全 expert streaming を許可し、`STRATA_PREFILL_STREAM_ALL=1` で強制できます。`STRATA_PREFILL_STREAM_ALL=0` または pair の90%以上を cache に保持しない場合は `STAGE` に留まり、chunk 閾値だけでは全 expert streaming になりません。fused layout にも expert source、fused ring、MMQ plan の対象 layer が必要です。

負数は CUDA と SYCL で意味が異なります。特に SYCL は負数を有効なしきい値として扱うため、fused layout のバッファ計算にもその値が使われます。ソースには負数入力を正規化する処理がありません。負数利用時の安全性・動作保証はこのコードから確認できません。

## 実行時の詳細

CUDA の既定しきい値 1024 は「非 resident expert を全件ストリーミングする」chunk の既定境界です。これ未満では routed-only staging を使い、CPU share が利用可能なら GPU がストリームするはずだった一部 expert を CPU に割り当てます。`STRATA_PREFILL_STREAM_MIN` はこの切替を動かすため、同じ prompt chunk でも GPU への expert コピー対象や fused path の可否が変わり得ます。変数自体について専用ログはありません。fused path が実際に選ばれると、stderr に `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` が一度出ます。

SYCL でも threshold 未満は `STAGE` slots、threshold 以上は ring-all の slots を使う判定に関与します。ring-all が許可されると全 non-resident expert を layer 順に先読みするため、変数は単なる fused-kernel 選択用ではありません。fused layout の場合、MMQ 用の小 chunk バッファは `stream_all_min() - 1` tokens 分に縮小されます。

## 根拠

- `src/prefill/prefill.cpp:157-168` — CUDA 既定値、環境値の `atoll` 変換、負数時の fallback。
- `src/prefill/prefill.cpp:198-208,1960-1972` — CPU share 上限と、share が適用されるときの CUDA fallback しきい値設定。
- `src/prefill/prefill.cpp:292-314,1040-1058,2341-2352,2460-2474` — ring 判定、fused layout の閾値、全 expert streaming 経路とその適用条件。
- `src/prefill/moe_fused.cu:651-672` — CUDA/HIP の fused kernel のビルド・デバイス・環境条件。
- `sycl/src/prefill/prefill.cpp:117-124,197-229,891-909` — SYCL の既定値、ring-all 条件、fused layout の閾値とバッファ計算。
- `docs/STRIX_HALO.md:107-125` — 1,024 を既定値として説明し、128 への変更例と fused expert への適用を記載。これは Strata の文書上の説明で、測定結果の再検証ではありません。
