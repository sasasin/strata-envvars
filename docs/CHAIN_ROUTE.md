# `CHAIN_ROUTE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal の `token_chain` 診断・計測プログラムで、MoE router の GEMV と `moe_route` を一つの `router_route` dispatch に融合するかを選びます。未設定時は融合経路です。これは通常の Strata エンジンやサーバーの設定ではありません。リポジトリ内の `CHAIN_ROUTE` の読み取りは `metal/tests/token_chain.cpp` のみで、実行時の Metal window engine は別の変数 `STRATA_METAL_ROUTE` を読みます。

## 値と判定

`getenv()` が返す文字列全体を `"0"` と比較します。数値変換や真偽値 parse はありません。

| `CHAIN_ROUTE` | `routef` | `token_chain` の経路 |
|---|---:|---|
| 未設定 | true | router GEMV と route を融合した `router_route_30` を1 dispatch で実行 |
| 空文字 | true | 同上。設定ありでも文字列が `"0"` ではない |
| 文字列がちょうど `0` | false | router GEMV と `moe_route` を別々の dispatch で実行 |
| その他（例: `00`, `0 `, `false`, `1`） | true | 同上の融合経路 |

空白除去、大文字小文字変換、先頭文字判定はありません。値は `main()` 内で一度読み取られ、プロセス実行中に環境を変更しても再評価されません。

## 有効になる条件

- `metal/tests/token_chain.cpp` からビルドされた `token_chain` 実行ファイルを使う場合に限ります。同ファイルの冒頭はこれを実モデル GGUF 上の Metal dispatch 列を計測するプログラムと説明しています。
- `token_chain` は少なくとも GGUF shard のパスを引数に取ります。 `--ntok` などの CLI 引数には `CHAIN_ROUTE` を上書きするものはありません。
- 通常の Strata エンジンやサーバーでは `CHAIN_ROUTE` は参照されません。`metal/src/engine/window.cpp` には別設定 `STRATA_METAL_ROUTE` があり、こちらは `"1"` と完全一致すると engine window の融合経路を opt-in します。

## 実行時の詳細

`routef` が false のとき、各 MoE layer でまず `ffn_gate_inp.weight` の GEMV を実行して router logits を作り、その後 `moe_route` dispatch が logits から expert ids、weights、plan を作ります。`routef` が true のときは `router_route_30` が router weight と入力から同じ出力群を作り、共有 expert GEMV と並行する dispatch 列に追加されます。どちらの経路でも、その後の expert 選択・計算 dispatch は共通です。

このプログラムは dispatch 数と weight/state bytes を標準出力に出し、warm-up 後の実行時間の中央値、最小値、最大値、effective GB/s、window あたりに換算した tok/s を表示します。環境変数自体についての専用ログはありません。`metal/tests/fuse_parity.cpp` は融合 router 経路と分割経路について logits、ids、weights、plan が bitwise 一致するかを検査するテストを含みますが、この調査ではテストや GPU 実行は行っていません。

## 根拠

- `metal/tests/token_chain.cpp:1-8,59-83`: `token_chain` の用途と CLI 引数。
- `metal/tests/token_chain.cpp:180-184`: `CHAIN_ROUTE` の単一読み取りと完全一致比較。
- `metal/tests/token_chain.cpp:495-500,547-565`: false 時の別 GEMV + `moe_route`、true 時の `router_route_30` dispatch。
- `metal/tests/token_chain.cpp:644-659`: 計測出力と median の表示。
- `metal/tests/fuse_parity.cpp:1-5,68-116`: 融合・分割 router の bitwise 比較テスト。
- `metal/src/engine/window.cpp:251-255,784,839-861`: 通常の Metal window engine が別変数 `STRATA_METAL_ROUTE` を使う箇所。

`docs/DETAILS.md` には `CHAIN_ROUTE` の記載は見つかりませんでした。計測結果や性能差はこの文書では主張していません。
