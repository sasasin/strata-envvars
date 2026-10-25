# `STRATA_PA_V2T`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

int8 KV を使う QSA の prompt attention で、Turing（compute capability 7.5）上の v1 カーネルの代わりに v2 カーネルを選びます。v2 は Turing では `cp.async` を使わず、レジスタ経由で次のデータをステージします。これは明示的な opt-in です。既定では Turing は v1 を使います。

この環境変数は prompt attention の経路にだけ関係します。prompt prefill が `qsa_prompt_attn_batch()` を呼び、同関数が対応可能な入力だと判断した場合に選択されます。別経路へ fallback した場合、この変数でその経路は変更されません。

## 値と判定

環境変数の文字列全体や数値としての妥当性は調べず、設定値の先頭文字だけを比較します。

| 値 | `v2t` の判定 | Turing の int8-KV prompt attention |
|---|---:|---|
| 未設定 | false | v1 を選択 |
| 空文字 | false | v1 を選択 |
| 先頭文字が `1`（例: `1`, `10`, `1anything`） | true | v1 に切り替える別条件がなければ v2 を選択 |
| その他（例: `0`, `true`, ` 1`） | false | v1 を選択 |

判定結果は `static const bool` に保存されます。最初に該当コードへ到達した後でプロセス環境を書き換えても、再評価されません。読み取りが実際に起きるのは、`qsa_prompt_attn_batch()` が有効な int8 K/V pools を処理する分岐へ進んだときです。

## 有効になる条件

- CUDA の prompt-attention 実装であること。HIP では関数が先に HIP 用の WMMA 経路を試し、その後 `false` を返すため、この CUDA 側の `STRATA_PA_V2T` 分岐には到達しません。
- `qsa_prompt_attn_batch()` が扱える形状であること（head dimension 256、query head 数が KV head 数の12倍、`cap > 0`、必要な IDs・steps・page table が存在すること）。`n_q <= 0` なら直ちに成功扱いで戻ります。
- Turing として判定されたデバイスであること。compute capability 7.5 は Turing 判定です。コード上は `cc < 8.0` を `turing` とするため、`STRATA_QSA_WARP` や `STRATA_EMULATE_CC` により 7.5 相当に扱われる経路も該当します。
- pools が int8 K/V 形式（`k_q`, `v_q` と両スケールがある）であること。Q4 KV、hybrid K8V4、FP KV は別分岐です。
- `STRATA_PROMPT_ATTN_V1` が設定されていないこと。これは値を問わず設定有無で v1 を選び、`STRATA_PA_V2T` より優先します。

`STRATA_PROMPT_ATTN_OLD` が設定されると、prefill 呼び出し側はそもそもこの prompt attention 関数を呼ばず、decode attention の旧経路へ進みます。形状非対応などでこの関数が `false` を返す場合も、呼び出し側は decode attention に fallback します。

## 実行時の詳細

`src/prefill/prefill.cpp` の QSA prefill 処理は、`STRATA_PROMPT_ATTN_OLD` が設定されていないとき `qsa_prompt_attn_batch()` を呼びます。関数は int8 K/V 分岐に入ると `STRATA_PROMPT_ATTN_V1` の設定有無と `STRATA_PA_V2T` を確認します。Volta 判定なら sm_70 用の v1 を使います。そうでなければ、`STRATA_PROMPT_ATTN_V1` が設定されているか、Turing 判定かつ `STRATA_PA_V2T` が有効でない場合に v1 を起動します。それ以外は `launch_i8()` を起動し、Turing では v2 のレジスタステージ経路になります。sm_80 以降でも同じ `launch_i8()` が使われますが、`STRATA_PA_V2T` はその選択を変えません。

v1 と v2 は加算順序が異なり、同じ回答になる保証をする設定ではありません。`docs/DETAILS.md` はこの変数を「回答が変わる」選択肢として、v2 prompt attention の opt-in と記載しています。Turing の v2 用の直接測定値や性能保証は、確認した資料にはありません。

カーネル起動後に CUDA エラーがあれば `qsa_prompt_attn_batch: <CUDA error>` を stderr に出して `exit(1)` します。環境変数自体の有効化・無効化を知らせるログはこの実装にはありません。

## 根拠

- `src/kernels/cuda/qsa_prompt_attn.cu:35-44` — v2 カーネルの sm_75 / sm_80 条件と、Turing で `cp.async` を使わないビルド経路。
- `src/kernels/cuda/qsa_prompt_attn.cu:2254-2295` — prompt attention の入力条件、デバイス判定、HIP の早期 return。
- `src/kernels/cuda/qsa_prompt_attn.cu:2312-2340` — KV 形式ごとの分岐、`STRATA_PROMPT_ATTN_V1` の優先、`STRATA_PA_V2T` の値判定と v1 / v2 起動選択。
- `src/kernels/cuda/qsa_prompt_attn.cu:591-610` — sm_80 未満でレジスタから共有メモリへステージする v2 の処理。
- `src/kernels/cuda/qsa_prompt_attn.cu:1043-1076` — `launch_i8()` の起動と CUDA エラー処理。
- `src/prefill/prefill.cpp:3257-3271` — prompt prefill からの呼び出しと旧 decode-attention への fallback。
- `docs/DETAILS.md:2244-2261` — Turing kernel series の説明と、この変数が回答を変える opt-in であること。
