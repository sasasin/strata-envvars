# `FNX_ONEHOP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

sFNX（Qwen3.8-Flash-Next を複数カードに分割する `strata-split`）の decode 中に、カード間の window sum と attention merge で one-hop の通信カーネルを使うかを切り替えます。既定値は有効です。`FNX_RING_F32=1` のときは one-hop が使えず、従来の ring 経路になります。

この環境変数を読むのは `src/split/src/engine.cu` の Engine 構築時だけです。通常の `strata` エンジン全般に適用される設定ではありません。

## 値と判定

`src/split/src/env.hpp` の `env_int()` は `getenv()` で値を取得し、`parse_whole()` を通して符号付き base-10 整数として文字列全体を `strtoll()` で変換します。範囲制限はなく、値が `0` かどうかで on/off を決めます。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 既定値 `1`。有効 |
| `0`、`+0`、`-0` など整数として 0 | 無効 |
| 0 以外の整数（負値も含む） | 有効 |
| 空文字、空白、`true`、`1x`、整数範囲外 | 整数として不正。例外で Engine 構築に失敗 |

先頭・末尾の空白、末尾の文字、空文字は受け付けません。`+` または `-` だけの値も不正です。`parse_whole()` が `strtoll()` の終端位置と `ERANGE` を検査します（`src/split/src/env.hpp:15-21,33-40`）。

## 有効になる条件

値が有効でも、Engine が次の条件を満たす場合に限り one-hop が設定されます。

- 対象は sFNX の分割 Engine。ビルド時に `FNX_NCARD` でカード数を固定し、`strata-split` は Linux CUDA または HIP の opt-in ビルドです（`src/split/src/model.hpp:1-3,14-21`; `src/split/CMakeLists.txt:1-5,92-115`）。
- `NCARD > 2`、または HIP 経路で `peer_on` が有効であること。
- `FNX_RING_F32` による `ring.f32` が無効であること。`FNX_RING_F32` は別途 0 または 1 のみを受け付け、既定値は 0 です（`src/split/src/engine_common.cu:1011-1018`）。

CUDA では `peer_on` は常に false なので、2 カード構成では `FNX_ONEHOP` を有効にしても one-hop になりません。3 カード以上では上記条件のもとで有効になります。HIP では `peer_on` が true なら2カードでも one-hop が選択され得ます。`FNX_PEER` の判定と結果設定は `src/split/src/engine.cu:81-94` にあります。

値が 0 なら、カード数などの条件に関わらず `onehop` は false となり、window sum と attention merge は ring カーネルを選びます。値が非 0 でも `FNX_RING_F32=1` なら one-hop は無効です。カード数が 3 以上で `FNX_ONEHOP` が非 0、かつ fp32 ring の場合、stderr に `fnx: FNX_RING_F32: the one-hop sum carries fp16 words only, the rings stay` と出ます。2カードで HIP peer が有効、というケースではこの警告条件を満たしません。

## 実行時の詳細

`Engine::Engine()` が各カードの ring buffer を用意した後、カードごとに `env_int("FNX_ONEHOP", 1)` を評価し、同じ判定を `ring.onehop` と `att_ring.onehop` に格納します。さらにカード初期化後にも警告条件のため同じ環境変数を読みます。static cache はなく、設定値は要求・CLI 引数から上書きされません。sFNX の起動ではモデルと draft layer のロード後、Engine 構築時に評価されます（`src/split/src/engine.cu:31-36,237-273`; `src/split/tools/sfnx.cpp:1050-1062`）。

window sum は `ring_sum()` が `r.onehop && T <= MAXT` のとき one-hop カーネルを選びます。HIP の peer push 用 buffer がある場合はそのカーネルが先に選ばれます。`T > MAXT` のチャンク経路はこの判定より前に処理されるため、そこでは `FNX_ONEHOP` による one-hop 分岐を通りません（`src/split/src/kernels.cu:1566-1598`）。attention の通常経路と lane 経路は `ar.onehop` に応じて one-hop merge または ring merge のカーネルを選びます（`src/split/src/kernels.cu:1388-1403,1416-1424`）。

不正値は `env_int()` が `runtime_error` を送出します。sFNX は Engine 構築時の例外を `fail()` で `ERR ...` として出力し、stderr に `sfnx: failed: ...` を出して終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1030-1035,1055-1062`）。`fnx_run` でも同じ Engine を使い、例外時は stderr に `fnx_run: ...` を出して終了コード 1 です（`src/split/tools/fnx_run.cpp:1364-1373`）。

## 根拠

- 直接参照は `src/split/src/engine.cu:266-273` の2か所で、どちらも上記 `env_int()` に環境変数名を渡しています。
- helper の環境読み取りと整数変換は `src/split/src/env.hpp:15-21,33-40`。
- `FNX_RING_F32` の既定値と許容値は `src/split/src/engine_common.cu:1011-1018`。
- one-hop を使う window sum と attention merge の分岐は `src/split/src/kernels.cu:1388-1403,1416-1424,1566-1598`。
- `docs/DETAILS.md` には `FNX_ONEHOP` の説明が見当たらず、文書に基づく追加の条件・測定値は確認できませんでした。
