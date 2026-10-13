# `STRATA_PREFILL_STREAM_ALL`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版の batched prompt prefill で、VRAM cache にない expert の先読み方法を選びます。有効時は各 layer の非 resident expert を expert ID 順に読み込み、GPU 計算より先に複数 layer 分を ring buffer へ流します。無効時は、その layer の routing が選んだ非 resident expert だけを短い staging queue に先読みします。変わるのは prefill 時の expert の I/O と staging で、decode や CUDA/HIP 版の経路からこの変数は読まれません。

環境変数を直接読む箇所は `sycl/src/prefill/prefill.cpp` の `ring_slots()` 内の一箇所です。設定値の判定結果は関数内 `static const int` に保存されるため、最初の評価後にプロセス環境を変更しても再評価されません。

## 値と判定

変数の文字列全体ではなく、設定値の先頭文字だけを判定します。未設定だけが自動選択を意味します。

| 値 | `stream_all_env` | 効果 |
|---|---:|---|
| 未設定 | `-1` | VRAM cache 外の expert 割合が 10% 未満なら stream-all を選ぶ。10%以上なら routed-only staging。 |
| 空文字 | `0` | stream-all を無効化し、routed-only staging。 |
| 先頭文字が `1`（例: `1`, `10`, `1foo`） | `1` | stream-all を要求する。 |
| その他（例: `0`, `true`, `-1`, ` 1`） | `0` | stream-all を無効化し、routed-only staging。 |

大文字小文字、数値としての妥当性、後続文字は検査されません。`atoi` のような数値変換はありません。根拠: `sycl/src/prefill/prefill.cpp:219-225`。

## 有効になる条件

値の判定に加えて、実際に stream-all 経路が選ばれるには、prefill chunk の ring slot 数が `STAGE`（8）より大きく、現在の chunk 長 `T` が `STRATA_PREFILL_STREAM_MIN` 以上で、expert source `m.src` が存在する必要があります。したがって、環境変数を `1` にしても、これらの条件が揃わない chunk は routed-only staging になります (`sycl/src/prefill/prefill.cpp:103,115-121,223-227,2460-2465`)。

ring slot 数には別の `STRATA_PREFILL_RING`、自動 chunk 計画の ring budget、pinned share に基づく既定値も関係します。特に `STRATA_PREFILL_RING` が設定され、その `atoi` 結果が 8 なら、`ring_slots()` は stream-all 判定前に 8 を返すため、この変数を `1` にしても routed-only です (`sycl/src/prefill/prefill.cpp:195-227`)。`STRATA_PREFILL_STREAM_MIN` は未設定時 1024 token で、コードは `atoll` を使って読みます。

自動選択で使う非 resident share は、prefill chunk があり `srcp` が存在する場合に `generate.cpp` が `(layer, expert)` のうち `host_res` の値が負の組数から計算します。既定で stream-all になるのはこの割合が **10% 未満**のときです。割合がちょうど 10% なら無効です (`sycl/src/program/generate.cpp:5932-5945`; `sycl/src/prefill/prefill.cpp:123-125,224`)。

## 実行時の詳細

`ring_slots(T)` は stream-all が許可されると、元の ring 候補値を 16 以上かつ backend / expert layout ごとの上限以下に clamp し、`T >= STRATA_PREFILL_STREAM_MIN` の場合にその ring を返します。未満なら 8 slot を返します。stream-all が許可されなければ 8 slot です。`Prefill::init()` はこの値で ring buffer を確保し (`sycl/src/prefill/prefill.cpp:1224-1241`)、prefill 実行時は `m.ring > STAGE && T >= stream_all_min() && m.src != nullptr` を改めて確認して walk を選択します (`sycl/src/prefill/prefill.cpp:2460-2465`)。

stream-all walk は現在の layer にある非 resident expert を ID 順に走査します。routing されている expert はコピー後に計算し、routing されていない expert はその ring slot を解放します。比較対象の routed-only 経路は routing 順に必要 expert を staging queue へ先読みします (`sycl/src/prefill/prefill.cpp:4159-4177,4178-4229`)。この環境変数固有の stdout/stderr ログやエラーはありません。

## 文書・測定値との照合

`docs/INTEL.md:613-625` は、2026-10-03 の変更記録として、stream-all を非 resident expert の割合が 10% 未満なら既定で使い、`=1` / `=0` で強制すると説明しています。40K int8 prompt の比較は routed-only 1,106 tok/s、stream-all 1,160 tok/s などと記載されていますが、これは同資料の測定条件の値であり、他環境での性能を示すものではありません。

一方、同じ `docs/INTEL.md:318-324` の80K promptの説明には routed-only が port の既定で `STRATA_PREFILL_STREAM_ALL=1` が他方を復元するとあり、上記の2026-10-03節と現行コードの既定動作に一致しません。調査対象 HEAD のコードでは `g_nonres_share < 0.10` の自動条件と `=0` の明示無効化が実装されています。資料中の前段説明は過去の状態として扱い、現在の条件はソースコードに基づいています。

## 根拠

- `sycl/src/prefill/prefill.cpp:195-227` — ring slot の既定値・上書きと環境変数の判定、非 resident share 条件、chunk threshold。
- `sycl/src/program/generate.cpp:5932-5945` — 自動判定に渡す non-resident share の算出。
- `sycl/src/prefill/prefill.cpp:1224-1241,2460-2465,4159-4229` — ring の確保、実行経路の選択、各 walk の処理。
- `docs/INTEL.md:318-324,613-625` — 過去状態の記述との不一致、および記載された測定値。
