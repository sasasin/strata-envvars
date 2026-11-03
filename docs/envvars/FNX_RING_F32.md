# `FNX_RING_F32`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

複数カードに分割した sFNX engine の decode 中にカード間で部分和を受け渡す ring の値形式を選びます。既定は fp16 のペアで、`1` を指定すると fp32 の値を受け渡します。参照されるのは `src/split` の `strata-split` 実行系で、`sfnx` サーバーと `fnx_run` の engine が対象です。通常の Strata 実行全般を切り替える変数ではありません（`src/split/src/engine_common.cu:1011-1018`, `src/split/src/engine.cu:31-36,237-242`, `src/split/CMakeLists.txt:92-117`）。

## 値と判定

`env_int("FNX_RING_F32", 0)` が値を整数として読み、結果が `0` か `1` かを検査します。未設定なら既定値 `0`、すなわち fp16 ペアです。設定値は符号付き十進整数として文字列全体を読むため、`1` と `+1` は fp32、`0`、`-0` は fp16 です。空文字、前後の空白、`1x`、`0x1`、小数、整数範囲外は整数変換エラーになります。整数として読めても `-1`、`2` など `0`/`1` 以外は許可されません。CLI 引数や別環境変数による上書きはありません。

| 状態 | 結果 |
| --- | --- |
| 未設定 | `0` として fp16 ペア |
| `0`（または `-0`） | fp16 ペア |
| `1`（または `+1`） | fp32 |
| 空文字、整数以外、整数範囲外 | `FNX_RING_F32: '<値>' is not a whole number` 例外 |
| 整数だが `0`/`1` 以外 | `FNX_RING_F32: 0 or 1, got <整数>` 例外 |

変換規則は `src/split/src/env.hpp:15-22,33-40`、対象変数の既定値・値域検査は `src/split/src/engine_common.cu:1011-1018` にあります。

## 有効になる条件

- CMake の sFNX split engine（CUDA または HIP）に限られます。確認した CMake 設定ではカード数 2、3、4 の実行ファイルが対象です（`src/split/CMakeLists.txt:92-117`）。
- Engine の構築時に各カードの ring 設定へ値が入ります。window の各 layer で行うカード間 `ring_sum` に適用されます（`src/split/src/engine.cu:237-242,951-988,1073-1076`; FFN の和は `935`）。
- `FNX_ONEHOP` が既定値のまま有効でも、fp32 ring では one-hop 経路を選びません。`NCARD > 2` かつ `FNX_ONEHOP != 0` の場合は stderr に `fnx: FNX_RING_F32: the one-hop sum carries fp16 words only, the rings stay` と出し、通常の ring 経路を使います。`FNX_ONEHOP=0` ならこの警告は出ません。2 カードでは `FNX_ONEHOP` が有効でも警告条件に該当しません（`src/split/src/engine.cu:266-273`）。
- prompt prefill の和にはこの指定は適用されません。prefill の copy-engine ring は別の `PfRing` 経路で、GPU-thread ring を選ぶ `FNX_PF_RING_SM` 経路でも `p->ring.f32 = false` に戻します（`src/split/src/prefill.cu:738-745,1299-1306`）。

## 実行時の詳細

`ring_f32()` は static cache を持たず、呼ばれるたびに環境を読み直します。Engine はカードごとの初期化ループでこの関数を呼ぶため、構築時にカードごとに評価されます（`src/split/src/engine_common.cu:1011-1018`, `src/split/src/engine.cu:237-242`）。通常、プロセス起動後に環境を変更しても OS の環境変数は自動では変わりませんが、コード上の値の cache はありません。sfnx は Engine 構築後にも起動ログの形式表示で `ring_f32()` を呼びます（`src/split/tools/sfnx.cpp:1055-1076`）。`fnx_run` の exact/lab identity も build 行を記録する際に同関数を呼びます（`src/split/tools/fnx_run.cpp:398-418`）。別の参照 `fnx_run.cpp:781` は、identity に build 行がない旧記録について保存済み `env` 行に `FNX_RING_F32=1` が含まれるかを調べる文字列比較で、現在のプロセス環境を読む箇所ではありません（`src/split/tools/fnx_run.cpp:776-782`）。

fp32 ring は各 float のビット列をタグ付き 64-bit word で送り、受信側で fp32 に戻して加算し、結果を `x` に書き戻します。fp16 経路は各ペアを `__half2` に変換して送受信します（`src/split/src/kernels.cu:832-868,886-945`）。dispatch は `r.f32` で `k_ring<true>` と `k_ring<false>` を選びます。`r.onehop` または HIP peer push が選ばれる場合の経路は別 dispatch ですが、Engine 初期化時に fp32 なら `onehop` を無効にしています（`src/split/src/kernels.cu:1566-1598`; `src/split/src/engine.cu:266-270`）。

読み取り値が不正なら Engine 構築中に例外になります。`sfnx` は `ERR <理由>` を stdout に出し、stderr に `sfnx: failed: <理由>` を出して終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1030-1035,1055-1062`）。`fnx_run` は stderr に `fnx_run: <理由>` を出して終了コード 1 になります（`src/split/tools/fnx_run.cpp:1364-1373`）。有効時の sfnx 起動ログはカード間和を `fp32`、既定時は `fp16` と表示します（`src/split/tools/sfnx.cpp:1068-1076`）。

## 根拠

- 読み取り、値の検査、bool 化: `src/split/src/engine_common.cu:1011-1018`。
- 環境値の完全な整数変換と未設定時 fallback: `src/split/src/env.hpp:15-22,33-40`。
- Engine のリングへの設定、one-hop の抑止と条件付き警告: `src/split/src/engine.cu:237-273`。
- fp32/fp16 の送受信・加算および実行経路の選択: `src/split/src/kernels.cu:832-868,886-945,1566-1598`。
- prefill が別経路であること: `src/split/src/prefill.cu:738-745,1299-1306`。
- 環境変数を読む tool の実行時ログ・identity 記録: `src/split/tools/sfnx.cpp:1055-1076`, `src/split/tools/fnx_run.cpp:398-418`。
