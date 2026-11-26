# `strata --stream-token`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン、root 引数） |
| オプション | `--stream-token` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

トークン単位の推論で、入力埋め込み・残差への入力コピー・head・sampling などの GPU 作業をセッションの compute stream に順序付けて投入する実験用フラグです。CUDA/HIP 実装では有効時に `main_cs` を token stream として渡し、無効時は既定 stream（`nullptr`）を使います。SYCL 実装でも同様に `main_cs` を選択します。help は実験的機能として掲載されています（`engine/src/program/generate.cpp:1242`、`engine/sycl/src/program/generate.cpp:830`）。

## 使い方

```sh
# 通常の推論エンジン起動例。モデル・pack・token の指定は利用環境に合わせる。
strata --stream-token --pack pack/full --tokens 1,2,3
```

## 値と既定値

値は取りません。parser は指定されると `stream_token` を `true` にし、`Options` の初期値は `false` です。繰り返し指定しても同じ boolean を true にするだけです（`engine/src/program/generate.cpp:776,3910`、SYCL: `engine/sycl/src/program/generate.cpp:460,1949`）。

通常の引数処理では、このフラグ自体に値の形式・範囲検証はありません。フラグの後ろに値らしい引数を置くと、その引数は別引数として解析され、未知引数なら usage を stderr に出して終了コード 2 で終了します。値を必要とする引数が欠けた場合は parser の `next()` が「needs a value」と stderr に出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:3842-3846,4268-4273`）。

## 実行時の動作

フラグが有効だと `token_stream` に `main_cs` を設定し、入力埋め込みと初期化／残差コピーへ渡します。無効時は `nullptr` です（`engine/src/program/generate.cpp:10616-10632`）。通常の token loop は session の layer 処理後に head を実行し、stream-token 有効時には head 後の device-wide 同期を省略します。logits の host readback も通常は省きますが、`--check-logits` を指定した場合、または logits dump の対象位置では readback します（同: `24339-24364`）。その後の sampling は選択中の token stream に投入し、サンプル token の host へのコピーと stream 同期で結果を取得します（同: `24402-24408`）。したがって、全ての同期がなくなるわけではありません。

`--native SHARD1` の処理は、このフラグを内部で有効化し、native arithmetic の複数設定もまとめて有効化します（同: `5155-5165`）。一方、`--native-head-gguf` を指定する場合は `--stream-token` が有効でなければならず、満たさないと stderr に `--native-head-gguf requires --stream-token` を出して終了コード 2 になります（同: `5309-5316,5378-5381`）。

SYCL 側でも `token_stream` に `main_cs` または `nullptr` を設定し、stream-token 時には input 後の queue 全体待機と head 後の queue 待機を省略します。logits readback の条件は CUDA/HIP と同じで、`--check-logits` または dump 対象なら読み戻します（`engine/sycl/src/program/generate.cpp:6034-6061,13559-13598`）。

## 適用条件と副作用

このフラグは GPU 上の token 推論経路に作用し、CPU-only の処理について別の挙動はソースから確認できませんでした。CUDA/HIP と SYCL には対応する実装があります。フラグは実験的と記載されていますが、特定の速度向上や数値結果の差は、ソースだけからは断定できません（`engine/src/program/generate.cpp:1242,10616-10632`、`engine/sycl/src/program/generate.cpp:830,6034-6061`）。

確認した範囲では、このフラグ自体によるファイルやネットワークへの副作用はありません。主な差は GPU queue/stream の選択と、推論中の同期・logits readback 条件です。`--check-logits` や logits dump と併用すると、stream-token 有効時も条件付き readback が発生します（`engine/src/program/generate.cpp:24348-24364`、SYCL: `engine/sycl/src/program/generate.cpp:13559-13598`）。

## 出力とエラー

`--stream-token` 単独の成功時に追加メッセージを出す処理は確認できませんでした。未知引数の場合は `unknown argument: ...` と usage を stderr に出し、終了コード 2 です。`--native-head-gguf` と併用して stream-token が無効な場合も stderr に要件を出し、終了コード 2 です（`engine/src/program/generate.cpp:4268-4273,5378-5381`）。

実行中には通常経路と同様、埋め込み・head・logits または sampled token の GPU 操作が失敗した場合、該当箇所のエラーを stderr に出して終了コード 1 となる経路があります（同: `10618-10632,24339-24364,24402-24408`）。

## 根拠

- `engine/src/program/generate.cpp:756-777,1242,3910` — option 状態の初期値、help 表示、parser 登録。
- `engine/src/program/generate.cpp:3842-3846,4268-4273` — 引数解析と未知引数の失敗経路。
- `engine/src/program/generate.cpp:5155-5165` — `--native` preset が stream-token を内部で有効化。
- `engine/src/program/generate.cpp:5309-5316,5378-5381` — native head GGUF の shard 解決と stream-token 必須検査。
- `engine/src/program/generate.cpp:10616-10632,24339-24364,24402-24408` — token stream の選択、同期/readback、sampling とエラー経路。
- `engine/sycl/src/program/generate.cpp:460,830,1949,2592,2777-2779,6034-6061,13559-13598` — SYCL parser、native preset、必須検査、stream 選択・同期/readback。

