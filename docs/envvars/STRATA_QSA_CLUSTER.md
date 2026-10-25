# `STRATA_QSA_CLUSTER`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA（Query Selection Attention）の block top-k 選択を、CUDA の thread-block cluster カーネルへ振り分けるかを制御します。対象は `qsa_block_topk()` で、スコア計算 (`qsa_block_scores`) や後続の KV 解決・attention 計算そのものを有効化する変数ではありません。

cluster カーネルは1 query あたり8 CTAを使います。対象になるのは一度の top-k 呼び出しが16 query 以下の場合です。適用できれば、通常の1 query 1 CTA の top-k カーネルを置き換えます。選択する cell ID は通常経路と同じになる設計です。

## 値と判定

CUDA 実装は `getenv()` の結果を `std::atoi()` に渡し、変換結果が0でなければ cluster を要求します。文字列全体の検証はありません。

| 値 | cluster 要求 |
|---|---|
| 未設定 | 有効 |
| `0`、`0abc`、空文字、数値に変換できない文字列 | 無効（`atoi` が0を返す） |
| `1`、`2`、`-1`、先頭の整数が0以外の文字列 | 有効 |

`atoi` の規則により、先頭の空白と符号は許され、整数の後ろにある文字は判定に使われません（例: ` 1tail` は有効、`0tail` は無効）。`static const bool` で初回評価結果を保持するため、top-k の最初の呼び出し後にプロセス環境を変更しても判定は更新されません。根拠: `src/kernels/cuda/qsa_select.cu:1295-1309`。

## 有効になる条件

値が有効でも、以下を満たさなければ cluster カーネルは使われず、通常の top-k 経路へ進みます。

- HIP ビルドではないこと。CUDA ソースでは HIP 用のコンパイル分岐が cluster の環境変数判定と呼び出しを除外し、cluster 関数も `false` を返します。
- `STRATA_TOPK_OLD` が設定されていないこと。この変数は値の内容でなく設定の有無を見ており、設定時は cluster を飛ばします。
- `nq <= 16`。これを超える呼び出しは通常経路です。
- CUDA デバイスが compute capability 9.0 以上であり、cluster kernel の組み込みコードも PTX/binary version 90 以上であること。古い GPU 用コードしか含まれないビルドでは使いません。
- QSA の `idx_block` が4、`cap` が最大選択幅以上、`nq <= 65535`、`max_blocks > 0` であること。
- 必要な dynamic shared memory を設定でき、その容量で少なくとも1 cluster が常駐できること。容量は `ceil(max_blocks / 8) * sizeof(uint32_t)` です。

デバイス・コード・geometry・共有メモリ条件による不適合は `false` で返り、呼び出し元が1 CTA単位の通常 top-k に fallback します。CUDA cluster kernel の起動自体が失敗した場合は stderr に `qsa_block_topk cluster: <CUDA error>` を出してプロセスを終了します。根拠: `src/kernels/cuda/qsa_select.cu:1229-1292,1301-1309,1338-1362`。

SYCL port の `qsa_block_topk()` も同じ環境値の判定を含みますが、同ファイルの `qsa_block_topk_cluster()` は「SYCL port: no thread-block clusters」として常に `false` を返します。そのため SYCL では値を有効にしても cluster は起動せず、通常経路に進みます。HIP はコンパイル条件で判定部自体を通りません。根拠: `sycl/src/kernels/cuda/qsa_select.dp.cpp:1848-1855,1953-1967`。

## 実行時の詳細

通常の一回分の生成では `src/core/layer.cpp` の QSA layer が `qsa_block_topk()` を1 query で呼びます。Verifier も layer ごとの QSA 選択で1 query または複数 query の batch を渡します。prompt 側の batch 化された選択も同じ dispatcher を通ります。そのため CUDA sm_90+ では、要求が既定で有効でも、query 数が16以下であり、他の実行条件も合う呼び出しだけ cluster になります。より大きい prefill batch はこの変数に関係なく通常経路です。

cluster 経路が成功すると8 CTAからなる cluster を query ごとに launch し、関数は通常 kernel の dispatch を省略します。cluster 関数が適用不可と判断したときは特別な警告を出さず fallback します。通常経路側で geometry/capacity が不正なら `qsa_block_topk: unsupported geometry or cap` を stderr に出して終了します。

根拠: `src/core/layer.cpp:1126-1134`; `src/core/verify.cpp:1370-1383`; `src/prefill/prefill.cpp:2772-2775,2819-2822`; cluster の launch 条件・構成は `src/kernels/cuda/qsa_select.cu:893-895,1229-1290`。

## 文書との照合

`docs/DETAILS.md:25-28` は decode の block selection と greedy argmax が sm_90+ の thread-block clusters で実行され、`STRATA_QSA_CLUSTER=0` が decode kernel を無効にすると説明しています。コードではこの変数が制御するのは QSA top-k cluster のみで、argmax は別の変数 `STRATA_ARGMAX_MULTI` が制御します。また、この資料の decode 全体の測定値は QSA cluster 単独の寄与を分離した値ではないため、本書では個別の性能向上値として扱いません。
