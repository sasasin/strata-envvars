# `STRATA_QI_EXACT_ATTN`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。調査対象は Strata 所有ソース。外部ライブラリ・GPU driver の環境変数の動作は含めない。

## 役割

ネイティブ Qwen Image 2.1 runner が画像トークンを処理するときの attention 実装を、独自 WMMA attention または ggml flash attention から Strata 同梱の逐次 FP32 attention kernel に切り替える診断・比較用フックです。K/V はこの runner の各 attention 経路と同じ FP16 のままで、クエリ・dot product・softmax・出力の計算は FP32 です。名前中の「EXACT」はソースのコメント上の呼称であり、全演算や K/V が FP32 になる意味ではありません。

この環境変数はネイティブ runner の選択自体を有効化しません。ネイティブ runner は CUDA/HIP ビルドで、Qwen Image 2.1 に `--model-args qwen_image_2_1_native=1` が渡された場合に選択されます（serve は native 設定時にその model arg を追加します）。

## 値と判定

コンストラクターで `getenv("STRATA_QI_EXACT_ATTN") != nullptr` を評価します。文字列の parse や内容比較はありません。

| 環境変数の状態 | `exact_attn` | 結果 |
|---|---:|---|
| unset | false | 通常の backend 判定に従う attention 経路 |
| 空文字を含む、何らかの値で設定 | true | 画像トークンで `qi21_attn_causal(..., causal=0)` を使用 |

したがって `0`、`false`、空文字も設定されていれば有効です。runner のコンストラクターで一度だけ読み、後からプロセス環境を変更しても、その runner の判定は変わりません。

根拠: `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:80-90`。

## 有効になる条件

- ネイティブ runner が選択されていること。`tools/image/sdcpp_native/apply.py` の組み込みコードは model args に `qwen_image_2_1_native=1` が含まれ、DiT model path が空でないときにネイティブ runner を作成します。ビルド側も `SD_CUDA` または `SD_HIPBLAS` のときだけ `SD_QI_NATIVE` を定義します。
- `compute()` がネイティブ処理を続ける入力であること。入力 shape、参照画像、fused MLP、CUDA/HIP backend の条件を満たさない場合は stock runner に移ります。また prompt 内に画像がある場合も stock runner に移ります。
- 対象は `blocks_pass()` の画像トークン経路（`mrow == 0`）です。テキスト prefix（`mrow == 1`）はこの変数に関係なく、既に同じ FP32 causal kernel を使います。

条件を満たさない場合、変数が設定済みでも stock runner を実行することがあり、この変数による切り替えは起きません。

根拠: `tools/image/sdcpp_native/apply.py:1-4,27-45,48-51`; `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:317-334,445-466,468-475,490-494,529-558,571-574`。

## 実行時の詳細

画像トークン経路では、変数が設定されていると `use_wmma` も false になり、attention 分岐が `qi21_attn_causal()` に進みます。引数 `causal=0` により、各画像 query は、その layer のテキスト prefix K/V と画像トークン K/V 全体を参照します。kernel は FP32 query と FP16 K/V の dot product を FP32 で計算し、scale `1/sqrt(128)` を掛けた後、FP32 softmax と FP32 の重み付き V 和を出力します。通常経路は、対応 backend なら独自 WMMA kernel、そうでなければ ggml flash attention です。

この設定の有無を示す専用ログは見つかりませんでした。コメントはこの参照経路を「slow」と記していますが、調査対象 commit の資料に再現条件付きの性能測定値は見つからなかったため、速度差は数値で断定しません。独自 kernel は `Lk * sizeof(float)` の動的 shared memory を必要とし、48 KiB を超えると kernel 呼び出しが `1` を返します。そのエラーで画像 block 処理が失敗すると native runner は無効化され、警告を出して以降 stock runner を使います。

根拠: `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:332-335,381-416,571-574`; `tools/image/sdcpp_native/qi21-native.cu:199-237,633-641`; runner fallback と警告は `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:108-112,441-442`。

## 根拠

- 環境変数の唯一の直接読み取り箇所: `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:86`。
- attention 分岐と prefix の別経路: `tools/image/sdcpp_native/qwen_image_2_1_native.hpp:332-335,381-416`。
- FP32 attention kernel、mask、K/V 型と shared-memory 上限: `tools/image/sdcpp_native/qi21-native.cu:199-237,633-641`。
- native runner の選択条件: `tools/image/sdcpp_native/apply.py:27-51`。
- `docs/DETAILS.md` と関連資料内に `STRATA_QI_EXACT_ATTN` の説明・測定値は確認できませんでした。
