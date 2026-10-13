# `STRATA_S2_SWIGLU_Q8`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

grouped S2 expert カーネルの gate/up 出力に対する SwiGLU 活性化と、その結果の scaled Q8_0 量子化を1つの GPU カーネルに融合する経路を選びます。無効にすると、SwiGLU と Q8_0 量子化を別々に起動します。CUDA 実装と SYCL 実装の両方に同じ判定があります。

## 値と判定

実装は `getenv()` の結果の先頭文字だけを調べます。数値変換や文字列全体の比較はしません。

| 値 | `swiglu_q8` | 結果 |
|---|---:|---|
| 未設定 | true | 条件を満たすと融合 SwiGLU + scaled Q8_0 カーネルを使う |
| 空文字 | true | 空文字列の先頭は `'0'` ではないため、未設定と同様 |
| `0` または `0...` | false | SwiGLU と量子化を分ける |
| `1`、`true`、その他先頭が `0` でない文字列 | true | 融合候補になる |

先頭が `0` なら後続文字列にかかわらず無効です。空白を含む文字列も先頭文字だけで判定されます。

根拠: `src/kernels/cuda/s2_expert_grouped.cu:1152-1159`、`sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp:1624-1631`。

## 有効になる条件

環境変数の判定が true でも、次の両方を満たす場合だけ融合カーネルが選ばれます。

- `new_grouped(x_q8_0, scratch)` が true。`STRATA_OLD_GROUPED` により旧カーネルを選んでいないこと、入力 activation と scratch のアドレスがそれぞれ4-byte alignedであることが必要です。
- `x_scales != nullptr`。融合カーネルは fp32 activation scales を引数に受け取ります。

どちらかを満たさない場合、環境変数が未設定または有効値でも分離経路へ進みます。分離経路は SwiGLU を実行し、`x_scales` がある場合は `quantize_q8_0_scaled`、ない場合は `quantize_q8_0` を続けて呼びます。従って、この変数が変えるのは条件を満たした grouped S2 呼び出し内のカーネル起動構成です。

この関数は CUDA の `src/kernels/cuda/s2_expert_grouped.cu` と SYCL の `sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp` にあり、ビルド設定にも登録されています（CUDA: `CMakeLists.txt:346`、SYCL: `sycl/CMakeLists.txt:206`）。`moe_grouped_s2` は非 native expert layout の grouped expert 処理から呼ばれます。CUDA では remote expert 経路が fp32 scale 配列を渡し（`src/core/remote_experts.cpp:313-323`）、MTP grouped path も `hit_xs_` を渡します（`src/core/mtp.cpp:932-936`）。verify コードからも同じ関数を呼びますが、実際に融合できるかは渡される scale pointer とアラインメントに従います。

## 実行時の詳細

環境変数は `moe_grouped_s2` 内の関数ローカル `static const bool` 初期化子で読みます。プロセス内のその実装で最初にこの関数が到達した時点で一度評価され、後から環境を書き換えても値は再評価されません。

融合経路は gate/up projection の後に `swiglu_quantize_q8_0_scaled_kernel` を起動します。このカーネルは gate/up scratch を読み、SwiGLU 活性化結果を scratch に書き戻すと同時に Q8_0 データと fp32 scales を生成し、その後の down projection に渡します。分離経路は `swiglu_kernel` の後に scale の有無に応じて別の量子化関数を呼びます。カーネル起動後の `check(...)` はそれぞれ `moe_grouped_s2/swiglu_q8`、`moe_grouped_s2/swiglu` の名前でエラー確認します。環境変数そのものに関するログ出力はこの箇所にありません。

## 根拠

- 判定と fused/fallback 分岐、scratch のレイアウト: `src/kernels/cuda/s2_expert_grouped.cu:1131-1181`、`sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp:1577-1673`。
- 新 grouped 経路の条件と旧 grouped 経路選択: `src/kernels/cuda/s2_expert_grouped.cu:523-553`、`sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp:735-764`。
- CUDA remote expert caller: `src/core/remote_experts.cpp:313-323`。
- CUDA MTP caller: `src/core/mtp.cpp:932-936`。
- ビルド登録: `CMakeLists.txt:346`、`sycl/CMakeLists.txt:206`。
- `docs/DETAILS.md` と関連設計資料を確認しましたが、この環境変数固有の値判定や速度・正確性の測定条件を裏付ける記述は見つかりませんでした。性能差や出力の同一性はここでは断定しません。
