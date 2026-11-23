# `STRATA_Q36_MTP_SAMPLED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Qwen3.6-35B-A3B エンジンのサーバー生成で、通常は MTP（multi-token prediction）の候補検証対象にならないサンプリング中の要求も MTP speculative drafting の対象にします。単独要求では `spec` 条件に入り、バッチ要求では sampled slot も MTP 候補 slot として数えられます。greedy 要求の MTP 動作を切り替える変数ではありません（`engine/src/qwen35/q36_engine.cu:4777-4780,4902-4909,5177-5181`）。

この変数は `strata-q36` の Qwen3.6 エンジン実装にあります。CUDA または gfx906 以外の HIP 用 GPU エンジンビルドでは `strata_qwen35` と `strata-q36` が追加され、`strata` にもリンクされます。gfx906 ビルドではこのエンジンを追加しません（`engine/cmake/strata_gpu_engine.cmake:565-584`）。

## 値と判定

3 か所とも `std::getenv(...) != nullptr && std::string(std::getenv(...)) != "0"` を使います。未設定なら false、設定されて値がちょうど `0` なら false、それ以外は true です。文字列全体を `"0"` と比較し、数値変換や trim、大文字小文字変換はしません。したがって空文字、`00`、`false`、` 0` は有効、`0` は無効です。値域・数値境界はありません（`engine/src/qwen35/q36_engine.cu:4777,4903,5180`）。

| 利用経路 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| 単独のサーバー要求 (`GEN` / `GENI`) とバッチ窓の sampled slot | false | 空文字、`1`、`true`、`00`、` 0` など `"0"` 以外 | `0` |

## 有効になる条件

- Qwen3.6 エンジンを含むビルド・実行経路であること。gfx906 ビルドにはこのエンジンが含まれません（`engine/cmake/strata_gpu_engine.cmake:565-584`）。
- モデルに MTP ブロックがあり、`--mtp N` で `N` が 1〜7 に設定されること。引数値はこの範囲でなければ起動時に `strata-q36: --mtp takes 0 .. 7 drafts` と stderr に出して終了コード 2 になり、ロード後はモデルに MTP がない場合 `E.mtp_d` が 0 になります（`engine/src/qwen35/q36_engine.cu:5373-5378,5456-5461,5555-5557`）。
- 要求がサンプリング要求として判定されること。`Sampling::needs_logits()` は `temperature > 0` または repeat/frequency/presence penalty が既定値と異なると true です。`top_p`、`top_k`、`min_p` 単独の変更はこの判定を true にしません（`engine/include/strata/qwen35/sampling.hpp:13-17`）。greedy 要求はこの変数が unset でも MTP 対象です（`engine/src/qwen35/q36_engine.cu:5180-5181`）。
- 単独要求では `GEN` / `GENI` 経路であること。`BGEN` / `BGENI` は `adm` 経路となり、単独要求用の `spec_step` 条件から除外されます（`engine/src/qwen35/q36_engine.cu:5004-5008,5180-5181,5236-5240`）。
- バッチ窓で使う場合はさらに `--batch-mtp` または `STRATA_BATCH_MTP` が有効であり、`--batch N`（`N > 1`）と MTP (`E.mtp_d > 0`) が必要です。`STRATA_BATCH_MTP` は未設定なら無効、設定時に `"0"` 以外なら有効です。バッチ窓は空き検証行 `Engine::kVerify - act > 0` も必要とし、候補数は空き行数までです（`engine/src/qwen35/q36_engine.cu:4899-4909,5558-5560`）。
- `--tokens` の非サーバー経路はこの環境変数を読まず、MTP がある場合は greedy speculative step を行う別経路です（`engine/src/qwen35/q36_engine.cu:5614-5628`）。

## 実行時の詳細

この環境変数の判定は、単独要求を扱う `request()`、バッチ窓を選ぶ `window()`、実際にバッチ MTP 候補を選ぶ `window_mtp()` の各関数内に別々の関数ローカル `static const bool` としてあります。各値はその関数の初回到達時に一度だけ評価され、その関数では以後キャッシュされます。したがってプロセス起動後に環境を書き換えても、すでに初期化された判定には反映されません。3 つの static は独立しており、各関数が未初期化の間に環境を書き換えた場合は評価時点が異なり得ます（`engine/src/qwen35/q36_engine.cu:4764-4778,4900-4907,5004,5180-5181`）。

単独サーバー要求では、この値が true かつ要求が sampled なら `spec` が true になります。生成ループは MTP ブロックから最大 `E.mtp_d` 個の draft を作り、メインモデルの greedy pick と照合して一致した draft を採用し、`T` として出力します。通常の sampling 経路では `sample()` が logits から token を選ぶため、この切替時には受理された draft および検証後の pick が出力系列に入ります。したがって「sampling 分布を保ったまま計算だけを省く」とはコードから断定できず、生成 token が変わり得ます（`engine/src/qwen35/q36_engine.cu:3960-4019,5219-5263`）。

バッチ要求では、sampled slot が MTP 候補になれます。候補 slot は `mtp_turn` に基づいて順に選ばれ、提案がその slot の当該 token と一致した場合には2行目も保持します。sampled slot の当該 token は `sample()` で選択されますが、保持された2行目の出力は `E.rows_pick` から取られます。よってここでも MTP が sampled 出力 token に関与し、通常の逐次 sampling と同じ token 列になる保証はソースから確認できません（`engine/src/qwen35/q36_engine.cu:4777-4800,4802-4811,4818-4858`）。

CLI 引数・別環境変数がこの値自体を上書きする処理はありません。`--mtp` と（バッチ窓用の）`--batch-mtp` / `STRATA_BATCH_MTP` は MTP 実行条件を別途決めます。環境変数を子プロセスへ転送する処理は、この名前の参照箇所にはありません。

## ログと測定値

この変数の値を理由に出す専用ログや無効値エラーはありません。単独サーバー要求の終了時には stderr の `strata serve: ... drafts accepted ...` 集計と stdout の `DONE` 行に accepted / offered 数が含まれます。バッチ slot では slot 終了時、提案があった場合に stderr へ `strata batch: slot %d: %lld of %lld MTP proposals accepted` が出ます（`engine/src/qwen35/q36_engine.cu:5266-5273,4840-4847`）。起動時のモデル MTP 欠如や batch 条件不足は変数の警告ではなく、`--batch-mtp` を明示した場合のみ `strata-q36: --batch-mtp needs --batch N (2 or more) and --mtp N: ignored` が stderr に出ます（`engine/src/qwen35/q36_engine.cu:5558-5560`）。測定値は記載しません。

## 根拠

- `engine/src/qwen35/q36_engine.cu:4764-4782` — バッチ窓での値判定、sampled slot の候補化。
- `engine/src/qwen35/q36_engine.cu:4899-4909` — バッチ MTP 経路へ入る条件。
- `engine/src/qwen35/q36_engine.cu:5004-5008,5177-5181,5236-5263` — 要求種別、単独 sampled 要求の MTP 判定と生成。
- `engine/src/qwen35/q36_engine.cu:4818-4858` — バッチ slot の sample、proposal 採否、出力。
- `engine/src/qwen35/q36_engine.cu:5373-5378,5456-5461,5555-5562,5614-5628` — `--mtp`、モデル状態、バッチ有効条件、非サーバー経路。
- `engine/include/strata/qwen35/sampling.hpp:13-17` — sampled 判定。
- `engine/cmake/strata_gpu_engine.cmake:565-584` — エンジンを含むビルド条件。

