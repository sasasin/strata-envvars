# `STRATA_METAL_ROUTE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。調査対象リポジトリの作業ツリーは clean。外部ライブラリの環境変数の動作は対象外。

## 役割

Metal の decode window において、MoE router の行列ベクトル積（router GEMV）と、その logits から expert 選択・実行計画を作る `moe_route` を、単一の `router_route` GPU dispatch にまとめる opt-in スイッチです。既定では別々の GEMV と `moe_route` dispatch を使います。

この環境変数を読む実装は `metal/src/engine/window.cpp` の `Window::routef_` 初期化だけです。Metal エンジンの window 経路に対する変数で、CUDA/HIP/SYCL の経路を制御する参照はありません。

## 値と判定

| 値 | `routef_` |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 文字列全体が `1` | 有効 |
| `0`、`01`、`1x`、`true`、空白を含む値など | 無効 |

`getenv()` の戻り値が存在することに加え、`std::string(value) == "1"` を比較します。数値変換や先頭文字だけの判定ではなく、大文字小文字も含めて文字列全体が一致する必要があります。`Window` のメンバー初期化時に値を読み、そのインスタンスの間は再読込しません。実行中に環境を書き換えても既存の window には反映されません。window を破棄して新しいインスタンスを作成した場合は、その作成時の値が読み取られます。

## 有効になる条件

`STRATA_METAL_ROUTE=1` でも、各 layer の `ffn_gate_inp.weight` の tensor 型が `BF16` または `F32` の場合だけ fused dispatch を選択します。それ以外の型では、通常の router GEMV と `moe_route` の2 dispatchに戻ります。Metal window は `Window::init()` で Qwen3.8-Flash-Next の geometry（48 layers など）を要求する実装です。

## 実行時の詳細

各 layer の MoE 部分で `routef_` と router tensor 型を確認します。条件を満たすと、`router_route_30`（BF16）または `router_route_0`（F32）を選び、router weights、入力、logits、expert ids/weights、plan、counter を渡します。条件を満たさない場合は別途 `gemv()` で logits を作り、その後 `moe_route` を呼び出します。fused 側は router GEMV と route の選択・plan 作成を一つの dispatch で実行し、その結果を後続の expert dispatch が使います。

`metal/kernels/router.metal` の実装コメントは、logits、ids、weights、plan が従来経路と bitwise 一致すると説明しています。同カーネルは、router 行列積の後に device counter を使って最後に完了した threadgroup が route 本体を実行し、counter をリセットします。counter は初期化時に16 bytes確保され、Metal runtime の `Context::alloc()` が確保領域をゼロ初期化します。コード上、この変数による専用ログ出力やエラー分岐はありません。

## ログ・測定値

`docs/MAC.md` は `STRATA_METAL_ROUTE=1` を、同じ token を生成し、この環境では速くならなかった decode variant と説明しています。実装コメントには T2 GPU で decode window 13.035 ms 対 13.027 ms、router_route 単独 0.615 ms 対分離した2 dispatchの0.566 ms、M5 Max で end-to-end 0.3–0.5%遅かったとの記録があります。これらはソースコメントと文書に記載された測定値で、条件の詳細や別のMacでの再現性まではこの調査では確認していません。

## 根拠

- `metal/src/engine/window.cpp:243-248` — スイッチの役割、厳密な文字列比較、window member としての初期化、コメント記載の測定値。
- `metal/src/engine/window.cpp:409-440` — Metal window の初期化と kernel 群への `router.metal` の組み込み、counter の確保。
- `metal/src/engine/window.cpp:657-658,760-830` — layer ごとの型条件、fused/分離 dispatch の選択と引数。
- `metal/src/engine/window.cpp:950-1017,1067-1093,2455-2471` — window 実行とキャッシュ済み dispatch の使用、window インスタンスの生成・破棄。
- `metal/kernels/router.metal:1-6,56-104` — fused kernel の処理、対応型、counter とbitwise一致についての実装コメント。
- `metal/src/mtl_rt.h:90, metal/src/mtl_rt.mm:171-177` — `Context::alloc()` が shared buffer をゼロ初期化すること。
- `docs/MAC.md:183-194` — Mac向け試験スイッチ一覧での説明。
