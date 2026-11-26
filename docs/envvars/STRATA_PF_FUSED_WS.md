# `STRATA_PF_FUSED_WS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の native fused prompt expert 処理で、通常の native kernel の代わりに warp-specialized kernel を選ぶ opt-in です。warp-specialized 経路は wide-batch 用で、producer warp が重みを F16 に decode して共有メモリの ring に置き、consumer warp が F16 積を計算します。`STRATA_PF_FUSED_F16` と同じ F16 products を使う実装です（`engine/src/prefill/moe_fused_iq.cu:1393-1400`）。この変数だけでは fused prompt expert 全体を有効化せず、既存の native 経路の有効条件と対応する形式の判定を通った層に限って kernel 選択を変えます（`engine/src/prefill/moe_fused_iq.cu:3415-3432,3517-3531,3856-3862`）。

環境変数を読むのは CUDA 実装の `ws_requested()` です。HIP では `d.ws` を立てず、warp-specialized kernel もコンパイル対象外です（`engine/src/prefill/moe_fused_iq.cu:2787-2790,3016-3022,3260-3269`）。

## 値と判定

`std::getenv` の戻り値が null でなく、先頭文字 `v[0]` が `'1'` の場合だけ要求を ON とします。文字列全体は parse・比較しません。空文字は OFF、`1`・`1abc` は ON、`0`・`0abc`・`true`・` 1` は OFF です。大文字小文字や数値としての妥当性検査はありません（`engine/src/prefill/moe_fused_iq.cu:2787-2790`）。

| 条件 | unset | ON になる値 | OFF になる値 |
|---|---|---|---|
| CUDA build | `ws_requested()` は false | 先頭文字が `1` | 空文字、先頭文字が `1` 以外 |
| HIP build | warp-specialized 経路を設定しない | なし | すべて（このビルドでは変数を読まない） |

## 有効になる条件

- CUDA build であること。HIP は `#if !defined(__HIPCC__)` の枝で `d.ws` を設定しません（`engine/src/prefill/moe_fused_iq.cu:2671-2673,3016-3022`）。
- CUDA device の compute capability major が 8 以上で、ベースとなる native kernel 群のセットアップ `d.ok` が成功していること。major が 8 未満では `dev_info()` が先に戻るため、この変数によるセットアップには進みません（`engine/src/prefill/moe_fused_iq.cu:2899-2905,2942-2950`）。
- `STRATA_PF_WIDE_PARAMS` が有効であること。CUDA compiler が nvcc 12.1 未満なら wide kernel の引数上限を理由に無効となり、`setup_ws()` は false を返します（`engine/src/prefill/moe_fused_iq.cu:2693-2700,2791-2801`）。
- セットアップ対象の gate/up・down kernel 全形式と、`STRATA_PF_FUSED_Q2N=1` で追加される場合の Q2_0 gate/up kernel がすべて device 上で利用可能であること。各 kernel について PTX version が 80 以上、要求する動的 shared memory 属性の設定が成功し、occupancy が 1 block 以上となる必要があります。一つでも失敗すると `d.ws` は false です（`engine/src/prefill/moe_fused_iq.cu:2791-2801,3016-3021`）。
- prompt の当該層が `native_supported()` の形式・デバイス・全体スイッチ判定を通ること。`STRATA_PF_FUSED=0` や `STRATA_PF_FUSED_NATIVE=0` などにより native 経路が無効なら、この変数はそれを上書きしません（`engine/src/prefill/moe_fused_iq.cu:3415-3432,3517-3531`）。WS 対応経路は native gate/up の i-quant/Q2_0 系と Q2_0/IQ4_NL down を基礎にし、NT=256/WS 形式のない Q5_0、K-quant、Q5_1、Q8_0、trellis、NVFP4 等はこの wide 経路から除外されます（`engine/src/prefill/moe_fused_iq.cu:3434-3469,3491-3505,3958-3968`）。

デバイスの世代名だけで利用可否を固定せず、実際の shared memory 属性設定と occupancy の成否で判定します。したがって同じ compute capability でも build/device の条件で unavailable になり得ます（`engine/src/prefill/moe_fused_iq.cu:2791-2801`）。

## 実行時の詳細

`ws_requested()` は初回呼び出し時に関数内 `static const bool` を初期化し、その後は同じ値を返します。プロセス実行中に環境を書き換えても再読込されません。デバイスごとの `DevInfo` も `dev_info()` が `g_dev[dev & 31]` に初回セットアップ結果を保存し、`done` 後は再評価しません（`engine/src/prefill/moe_fused_iq.cu:2671-2691,2787-2790,2847-2853`）。

`dev_info()` で `d.ok && ws_requested()` のときだけ各 warp-specialized kernel をセットアップします。成功すると `d.ws=true` となり、`native_supported()` が true を返す native 層を prompt loop が fused native 経路へ送り、wide batch の `experts_native()` が `ws=d.ws` と occupancy 1 を使って warp-specialized kernel を launch します。通常の `Batch` が渡された場合も `d.ws` が立っていれば `WideBatch` に包み直して同じ経路を使います（`engine/src/prefill/moe_fused_iq.cu:3016-3021,3856-3862,3952-3978`、`engine/src/prefill/prefill.cpp:5692-5703,5830-5842`）。`STRATA_PF_BATCH` は一回の launch にまとめる expert 数を決め、wide 形式を使うかに関係しますが、WS の可否そのものは `d.ws` のセットアップ判定です（`engine/src/prefill/prefill.cpp:5784-5794`）。

## ログと測定値

環境変数が要求され、かつ `d.ok` でベース kernel の初期化まで到達したものの、WS の形式一式のセットアップに失敗した場合、stderr に次の行を出します。成功時にはこの WS 専用の有効ログはありません（`engine/src/prefill/moe_fused_iq.cu:3016-3022`）。

```text
prefill fused experts (native): STRATA_PF_FUSED_WS=1 is not available here
```

ベースの `d.ok` が false のまま戻る場合はこの箇所に到達せず、この警告も出ません（`engine/src/prefill/moe_fused_iq.cu:2899-2905,3016-3022`）。`docs/DETAILS.md` は、この方式の共有メモリ量を既定で約 101 KB、sm_80/sm_90 が利用対象、それ以外では unavailable と記載し、CMP 170HX で同一 layer が 7.65 ms だったという変更作者の測定値を載せています。これは Strata 内で再測定した値ではありません。現行実装の可否判定は固定の世代名比較でなく、上記の kernel 属性・shared memory 設定・occupancy の実行時チェックです（`docs/DETAILS.md:1817-1825`、`engine/src/prefill/moe_fused_iq.cu:2791-2801`）。

## 根拠

- `engine/src/prefill/moe_fused_iq.cu:1393-1434` — WS kernel の設計と shared memory サイズ式。
- `engine/src/prefill/moe_fused_iq.cu:2671-2691,2693-2700,2787-2801,2847-2853,2899-2905,3016-3022` — 値の取得、cache、device/compiler/資源条件、警告。
- `engine/src/prefill/moe_fused_iq.cu:3415-3432,3517-3531,3856-3862,3952-3990` — native 経路選択、WideBatch 化、kernel dispatch。
- `engine/src/prefill/prefill.cpp:5692-5703,5784-5794,5830-5842` — prompt 層の fused 判定、batch サイズ、呼び出し。
- `docs/DETAILS.md:1817-1825` — 変更作者による条件付き説明と測定値。
