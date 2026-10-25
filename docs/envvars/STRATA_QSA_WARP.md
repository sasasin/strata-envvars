# `STRATA_QSA_WARP`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。調査時の作業ツリーは `main` で変更なし。外部ライブラリの環境変数は対象外。

## 役割

CUDA の QSA prompt 処理で、GPU の compute capability に応じた新しいカーネル選択を A/B 比較用に抑制し、sm_80 未満向けの経路を選ぶための開発・診断用フックです。対象は QSA の block-score 計算と prompt attention の2か所です。`STRATA_QSA_WARP` 自体は選択スコアの warp カーネルを直接起動する指定ではありません。選択側では、さらに `STRATA_SELECT_SIMT` が有効な場合に限り FP32 tiled scorer を実行し、それ以外は呼び出し元が従来の warp scorer に fallback します。

## 値と判定

両方の CUDA 読み取り箇所で文字列全体を比較し、`"1"` または `"select"` / `"attn"` の完全一致だけを認識します。空白、大文字小文字、追加文字は許容されません。たとえば `"10"`、`"true"`、`"SELECT"` は一致しません。未設定、空文字、その他の値はいずれも capability を上書きしません。

| 読み取り経路 | 認識する値 | 上書き内容 |
|---|---|---|
| block-score scorer | `1`, `select` | 対象 GPU の compute-capability major を `7` として扱う |
| prompt attention | `1`, `attn` | 対象 GPU の compute capability を `75` として扱う |

この判定結果は各関数内の `static` な per-device 配列に保存されます。各 GPU について最初に capability を調べるときに環境変数を読み、その後の呼び出しではキャッシュ値を使うため、最初の判定後にプロセス環境を変えても反映されません。値の読み取り時点はそれぞれの経路で最初の `qsa_block_scores_tc()` / `qsa_prompt_attn_batch()` 呼び出し時です。

## 有効になる条件

- CUDA の block-score 経路では、`qsa_block_scores_tc()` が有効な形状を受け取り、GPU 情報の取得に成功した場合に capability override が適用されます。override 後の major は `7` となるため、sm_80 以上向けの TF32 tensor-core scorer 分岐を避けます。sm_80 未満向けの FP32 tiled scorer は `STRATA_SELECT_SIMT` の値が先頭文字 `'1'` の場合だけ起動します。そうでなければ関数は `false` を返し、呼び出し元が従来の warp scorer を使います（`src/prefill/prefill.cpp`）。
- CUDA の prompt-attention 経路では、`qsa_prompt_attn_batch()` の初回 capability 判定で override が適用されると `turing` が真になります。INT8 K/V pool の場合は、通常の sm_80 以上向け `launch_i8()` ではなく、v1 の `launch<1>()` が選ばれます。Q4_0 K/V pool は `turing` 条件によりこの関数が `false` を返すので、呼び出し元は `qsa_decode_attn_batch()` に fallback します。ほかの pool 形式の処理がすべてこの値で切り替わるわけではありません。
- prompt-attention 経路では通常の capability 分岐が sm_70 未満で `false` を返します。override は capability を 75 として扱うため、この guard も通過させます。従って、特に古い GPU での指定が常に安全またはサポートされるとはソースから確認できません。A/B 用コメントが説明する pre-sm_80 経路はありますが、sm_70 未満での実行保証は記載されていません。
- `STRATA_SELECT_SIMT=1` は選択側の別設定です。`STRATA_QSA_WARP=1|select` だけでは FP32 tiled arm は起動せず、既存 warp scorer に fallback します。

## 実行時の詳細

block-score 側では、`qsa_block_scores_tc()` の CUDA 実装がデバイス major を取得し、環境変数が `1` または `select` ならキャッシュに `7` を記録します。major が 8 未満として扱われるため、`STRATA_SELECT_SIMT` が先頭文字 `'1'` なら `block_scores_simt_kernel` と tail kernel を起動し、成功を返します。それ以外では `false` を返します。prefill 呼び出し元は `false` の場合 `qsa_block_scores()` を呼び、従来の warp kernel でスコアを計算します。値が有効な CUDA build でも、`STRATA_SELECT_SIMT` の値によって実際に使われる scorer が異なります。

prompt-attention 側では、`1` または `attn` のとき device cache に `75` を記録し、以降の分岐を Turing 相当として行います。INT8 K/V pool では v1 kernel を選びます。Q4_0 の場合、この経路は `false` を返し、prefill 側の呼び出し元が decode kernel の batch 処理へ移ります。これらは選択 scorer の分岐とは独立しています。Strata はこの変数について専用のログを出しません。

## backend と資料との照合

- HIP の selection scorer 実装は `__HIPCC__` 分岐内で `STRATA_QSA_WARP` を読みません。HIP prompt-attention 実装は共通の capability 判定部で値を読みますが、その後 `volta` / `turing` を明示的に未使用とし、HIP WMMA 可否の別判定へ進みます。override 値は capability が 70 未満のときの早期 `false` 判定を通過させますが、HIP WMMA の対応 GPU 判定を変えません。したがって CUDA の INT8 K/V 分岐を HIP の挙動として説明できません。gfx906 の prompt-attention は capability 判定より前に `false` を返します。
- SYCL 移植コードにも読み取りがあります。selection scorer は tensor-core kernel 未移植としてその場で `false` を返し、呼び出し元の旧 scorer に fallback します。prompt-attention は capability 値を `(void)` で未使用にした後 XMX kernel の可否を独自に調べます。このため両 SYCL 読み取り箇所では、環境変数値が実際の kernel 選択を変えていません。
- `docs/DETAILS.md` にこの変数の説明や性能測定値は見つかりませんでした。`CMakeLists.txt` は `STRATA_QSA_WARP=1` と `STRATA_SELECT_SIMT=1` を設定した選択 scorer の GPU benchmark test を定義していますが、これはテスト設定であり、利用者向け設定や一般性能の根拠ではありません。`docs/NVIDIA_V100.md` は V100 で QSA block scores に warp kernel を使うこと、および tensor-core scorer が sm_80 を必要とすることを記載しています。

## 根拠

- CUDA selection scorer の capability override、`STRATA_SELECT_SIMT` 判定、SIMT kernel 起動: `src/kernels/cuda/qsa_select.cu:1118-1172`。
- CUDA prompt-attention の capability override と `turing`/`volta` 判定: `src/kernels/cuda/qsa_prompt_attn.cu:1453-1482`。
- prompt-attention の pool 別分岐、INT8 K/V の v1 選択と fallback 条件: `src/kernels/cuda/qsa_prompt_attn.cu:1493-1522`。
- prefill の選択 scorer fallback と attention decode fallback: `src/prefill/prefill.cpp:2763-2774,2862-2876`。
- SYCL selection scorer の読み取り後の fallback: `sycl/src/kernels/cuda/qsa_select.dp.cpp:1646-1698`。
- SYCL prompt-attention の読み取り後の XMX 判定: `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1968-2010`。
- HIP 分岐と gfx906 の早期 fallback: `src/kernels/cuda/qsa_prompt_attn.cu:1461-1482,1483-1491`。
- benchmark におけるテスト専用の組み合わせ: `CMakeLists.txt:401-418`。
- V100 の scorer 対応記述: `docs/NVIDIA_V100.md:36`。
