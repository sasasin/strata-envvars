# `FNX_RING_F32`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

split engine の decode でカード間の部分和を運ぶ ring の要素形式を選びます。未設定または `0` では fp16 2 要素を 1 語に詰め、各 hop で fp16 に丸めます。`1` では要素ごとに fp32 を送受信し、カード間の部分和を fp32 のまま加算します。engine の各カードバッファにこの設定を保持し、層の attention 出力や MoE 出力などを `ring_sum` で合算します。生成や logits が同一になる保証はコードにありません。`FNX_RING_F32` は decode ring 用で、prompt の copy-engine ring は fp16 です（`engine/src/split/src/engine.cu:279-284, 976-980`; `engine/src/split/src/kernels.cu:882-941, 1582-1614`; `engine/src/split/src/prefill.cu:967-990`）。

## 値と判定

`ring_f32()` は `env_int("FNX_RING_F32", 0)` を呼び、未設定なら `0` を使います。`env_int` は `getenv` 後、符号付き base-10 整数として文字列全体を `strtoll` で解析します。空文字・空白・数値以外の文字・整数範囲外は `FNX_RING_F32: '<値>' is not a whole number` の例外です。解析後は `0` と `1` だけを受け入れ、それ以外は `FNX_RING_F32: 0 or 1, got <数値>` で例外にします（`engine/src/split/src/env.hpp:15-21, 33-40`; `engine/src/split/src/engine_common.cu:1035-1042`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| split engine の `ring_f32()` | `0` として fp16 pairs | `1`, `+1`, `01` → fp32 | `0` は fp16 pairs。`2`, `-1` は範囲外。空文字、`true`、`0anything`、`1.0`、前後の空白、整数範囲外は整数解析エラー |

符号と先頭ゼロは整数解析で許されます（したがって `-0` は `0` 扱いです）。大文字小文字の比較はなく、`true` / `false` は整数ではないため受け付けません。明示的な空文字は未設定扱いではありません。既定値を変える CLI 引数や設定ファイルの読み取りはこの設定にありません（`engine/src/split/src/env.hpp:15-21, 33-40`; `engine/src/split/src/engine_common.cu:1039-1041`）。

## 有効になる条件

- `fnx::Engine` が使われる Strata split engine の decode ring で有効です。値を読む関数自体にカード数条件はありません。ソースには CUDA/HIP の split engine があり、この判定に `FNX_HIP` など backend 別の値分岐はありません（`engine/src/split/src/engine.cu:279-284`; `docs/SPLIT_ENGINE.md:67-71`）。
- prompt 経路の ring はこの値で fp32 になりません。`FNX_PF_RING_SM=1` の GPU-thread prompt ring でも、engine の ring 設定をコピーした後に `f32=false` に戻します。copy-engine ring の送受信バッファも `__half` です（`engine/src/split/src/prefill.cu:967-990`）。
- decode ring の one-hop 経路は `!ring.f32` を条件に含むため、値が `1` なら `FNX_ONEHOP` や peer 状態にかかわらず使われず、通常の ring kernel に進みます。3 枚以上で `FNX_ONEHOP` が非 0 の場合は、`fnx: FNX_RING_F32: the one-hop sum carries fp16 words only, the rings stay` を stderr に出します。`FNX_ONEHOP=0` ならこの警告条件を満たしません（`engine/src/split/src/engine.cu:308-316`; `engine/src/split/src/kernels.cu:1602-1614`）。
- sFNX server や `fnx_run` の lab 実行の engine 作成時に読み取られます。CLI 引数による上書き条件はありません（`engine/src/split/tools/sfnx.cpp:1123-1135`; `engine/src/split/tools/fnx_run.cpp:978-989`）。

## 実行時の詳細

値の解析は `ring_f32()` の呼び出しごとで、関数内 static cache はありません。`Engine` のカードバッファ作成ループで各カードの `Ring::f32` に結果を保存するため、その engine の動作は作成時に決まります（`engine/src/split/src/engine.hpp:35-37`; `engine/src/split/src/engine.cu:279-284`）。同じ関数は sFNX の起動ログと `fnx_run` の lab identity 作成でも再度呼ばれます。そのため、その後にプロセス環境が変更された場合にログや identity の判定値が engine の保存値と異なり得ますが、通常の engine 処理は保存済みの `Ring::f32` を使います（`engine/src/split/tools/sfnx.cpp:1139-1151`; `engine/src/split/tools/fnx_run.cpp:386-418`）。

`ring_sum` は fp32 設定の場合 `k_ring<true>` を起動し、2 要素を別々の fp32 語で運びます。fp16 設定は `k_ring<false>` で、各 hop の書き込み時に fp16 pair へ丸めます。`ring_sum` は attention の出力合算、FFN/MoE の合算などから呼ばれます（`engine/src/split/src/kernels.cu:833-864, 882-941, 1612-1614`; `engine/src/split/src/engine.cu:972-981, 1029-1033, 1115-1120`）。`fnx_run` は lab identity に `ring fp32` または `ring fp16-pairs` を記録し、古い identity に build 行がない場合は記録済みの環境行に `FNX_RING_F32=1` があるかを使って ring 設定を復元します（`engine/src/split/tools/fnx_run.cpp:386-418, 776-788`）。

## ログと測定値

- sFNX の起動成功ログ `sfnx: loaded in ...; ... sums between them fp32; ...` は選択された値を表示します（`engine/src/split/tools/sfnx.cpp:1142-1151`）。
- 3 枚以上で `FNX_ONEHOP` が非 0 なら、one-hop が fp16 words 専用のため ring を使うという上記 stderr 警告が出ます（`engine/src/split/src/engine.cu:315-316`）。
- sFNX の Engine 作成時に値が不正だと例外を捕捉し、標準出力へ `ERR FNX_RING_F32: ...`、stderr へ `sfnx: failed: FNX_RING_F32: ...` を出して終了コード 1 で終了します。`fnx_run` では `fnx_run: FNX_RING_F32: ...` を stderr に出し終了コード 1 です（`engine/src/split/tools/sfnx.cpp:1097-1103, 1131-1136`; `engine/src/split/tools/fnx_run.cpp:1364-1373`）。
- `engine_common.cu` のコメントには fp32 の decode 負荷と KL の比較値がありますが、再現に必要な機種・モデル・量子化・測定条件が揃っていないため、ここでは測定結果として一般化しません（`engine/src/split/src/engine_common.cu:1035-1040`）。

## 根拠

- 読み取り・整数判定: `engine/src/split/src/env.hpp:15-21, 33-40`; `engine/src/split/src/engine_common.cu:1035-1042`
- Engine 設定、one-hop 条件と警告: `engine/src/split/src/engine.cu:279-316`
- decode ring の fp32 / fp16 実装と dispatch: `engine/src/split/src/kernels.cu:833-864, 882-941, 1582-1614`
- prompt ring の扱い: `engine/src/split/src/prefill.cu:967-990`
- server 表示と例外処理: `engine/src/split/tools/sfnx.cpp:1097-1103, 1123-1151`
- lab identity: `engine/src/split/tools/fnx_run.cpp:386-418, 776-788, 1364-1373`
