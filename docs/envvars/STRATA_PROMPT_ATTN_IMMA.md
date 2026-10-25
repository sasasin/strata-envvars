# `STRATA_PROMPT_ATTN_IMMA`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA（query-selected attention）の prompt 処理で、int8 KV 用 CUDA kernel を v2 から v3 に切り替えます。v3 は q.k と p.v の積を INT8 tensor core MMA で計算し、v2 は FP16 MMA を使います。対象は CUDA の int8 KV prompt attention だけです。decode attention、Q4_0 KV、K8V4 hybrid KV をこの変数が切り替えるわけではありません。

## 値と判定

`std::getenv()` の有無と値の先頭 1 文字だけで判定します。数値 parse、文字列全体の比較、大文字小文字変換はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効（v2） |
| 空文字 | 無効（v2） |
| 先頭文字が `1` | 有効要求（v3） |
| その他（`0`, `true`, `2`, 空白など） | 無効（v2） |

たとえば `1`, `10`, `1anything` は有効要求になります。`true` は無効です。

値は `qsa_prompt_attn_batch()` の int8 KV 分岐が v1/Turing 用経路を通過した後、最初に v3/v2 を選択するときに `g_pa_imma` へ保存されます。同一プロセスでは以降の呼び出しで環境を再読しないため、読み取り後に環境を変更しても反映されません。テスト用 `qsa_prompt_attn_set_imma()` はこの状態を明示的に上書きできますが、通常の実行経路からは呼ばれません。

## 有効になる条件

環境変数が有効要求でも、次の条件を満たす呼び出しに限られます。

- HIP ビルドではないこと。HIP のコードは独自 WMMA 判定の後に戻り、CUDA の `g_pa_imma` 判定へ到達しません。
- `qsa_prompt_attn_batch()` が呼ばれること。通常の prefill では `STRATA_PROMPT_ATTN_OLD` が設定されていない場合にこの関数を試します。関数が利用不可を返すと prefill 側は `qsa_decode_attn_batch()` にフォールバックします。
- KV が純粋な int8 形式であること（`k_q`, `v_q`, `k_scale`, `v_scale` が存在し、先に判定される Q4_0 / K8V4 分岐ではないこと）。
- query head geometry、ページ容量、選択 ID などが prompt kernel の要件を満たすこと。prompt tensor-core 経路は compute capability 70 未満では利用されず、v3 自体は 80 以上でなければ選択されません。
- `STRATA_PROMPT_ATTN_V1` が設定されていないこと。また、Turing 相当（compute capability 8.0 未満）では v1 / v2t 系の分岐を通るため、この変数による v3 選択に到達しません。`STRATA_QSA_WARP` などで compute capability を 7.5 相当に扱う場合も同様です。
- 実際に v3 kernel が使えること。共有メモリ属性設定が失敗すると `launch_i8v3()` は `false` を返し、呼び出し元は通常の prompt attention にフォールバックします。

## 実行時の詳細

通常の prefill 呼び出し元は `STRATA_PROMPT_ATTN_OLD` が設定されている場合、または `qsa_prompt_attn_batch()` が `false` を返す場合に、decode attention kernel を query batch ごとに実行します。`STRATA_PROMPT_ATTN_IMMA` 自体は失敗時のログやエラーを出さず、v3 を要求するだけです。

v3 の起動時には device ごとに動的共有メモリ上限を設定します。その設定に失敗した場合は起動せず `false` を返します。kernel launch 後の CUDA エラーは `qsa_prompt_attn_batch (v3): <CUDA error>` を stderr に出し、プロセスを終了します（この場合は通常経路へのフォールバックではありません）。v3 選択箇所まで進んだ CUDA sm_80 以上では、無効要求なら v2 の int8 kernel が選択されます。Turing 相当ではその選択箇所に進まず、先行する v1 / v2t 系の分岐が使われます。

## 文書・測定値

`docs/DETAILS.md` はこのスイッチを「int8-KV prompt attention on INT8 tensor cores」と記載し、rounding-level の差（KL at the floor）、prompt read +2.5% としています。表にはこの値の個別 GPU・モデル等の測定条件は示されていないため、一般的な性能向上値とは扱えません。kernel のヘッダー説明も FP32 基準の計算と bitwise 一致ではないことを述べています。

## 根拠

- 値の読み取り、v1/Turing 分岐、v3/v2 の dispatch: `src/kernels/cuda/qsa_prompt_attn.cu:2317-2340`
- v3 kernel の INT8 MMA と演算説明: `src/kernels/cuda/qsa_prompt_attn.cu:1079-1085,1147-1160`
- device 共有メモリ設定、起動エラー: `src/kernels/cuda/qsa_prompt_attn.cu:1394-1424`
- compute capability と HIP 分岐: `src/kernels/cuda/qsa_prompt_attn.cu:2254-2294`
- prefill 呼び出しと decode attention fallback: `src/prefill/prefill.cpp:3260-3272`
- parity 用 setter: `include/strata/kernels/qsa_prompt_attn.hpp:39-40`, `src/kernels/cuda/qsa_prompt_attn.cu:2252`
- 測定表: `docs/DETAILS.md:2220-2236`
