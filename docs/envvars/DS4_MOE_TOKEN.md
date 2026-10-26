# `DS4_MOE_TOKEN`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DS4 の非同期 host-routed 経路で、window 内の token 数が1のときに使う MoE 計算経路を選びます。有効なら `moe_gate_up` と `moe_down` を順に呼び、無効なら window 用の `win_experts` を呼びます。`ds4_model.cu` のコメントは、無効時には CPU lane の応答を待つ前に down rows を実行し、結果のビットは同じで速度向上はないと説明しています。

## 値と判定

値は `std::atoi` で整数に変換し、変換結果が0かどうかで判定します。文字列全体の検証はありません。

| 設定 | 判定 |
|---|---|
| 未設定 | 有効 |
| 空文字 | `atoi` の結果が0のため無効 |
| 数値変換結果が0 | 無効。例: `0`, `0tail`, `true`, 数字で始まらない文字列 |
| 数値変換結果が0以外 | 有効。例: `1`, `-1`, `2tail`, 前後に空白のある非ゼロ整数 |

`atoi` は先頭の空白と符号を許し、先頭から読める整数部分を変換します。後続文字列は判定されません。数値範囲の検証や clamp はありません。

## 有効になる条件

この設定が分岐に影響するのは `layer()` 内の `wp.async` 経路だけで、さらに `T == 1` の場合に限られます。`plan_window()` は `wp.async` を `par || (!sync_decode && T <= async_max_t)` で決めます。したがって、値が有効でも `wp.async` が偽、または `T` が1以外なら `DS4_MOE_TOKEN` による選択は起きません。

この変数は `wp.async` でない host-routed 経路や、複数 token の window の処理を切り替えません。

## 実行時の詳細

設定値は `Model::Impl` のメンバー初期化時に読みます。値はそのインスタンスの `moe_token_path` に保持され、layer ごとには再読込しません。インスタンス生成後に環境を変更しても、そのインスタンスの判定は変わりません。

`wp.async` 経路では、まずルーティングを公開し、shared expert を計算します。その後 `T == 1 && moe_token_path` なら `MoeArgs` を組み立て、モデル形式に応じた `moe_gate_up` を実行します。lead device は CPU lane の応答を `wait_seq` で待ってから、同じ形式選択で `moe_down` を実行します。

条件が偽なら、window 用の group 情報と CPU lane の応答先を `WinArgs` に設定し、MXFP4 形式では `gg::win_experts`、それ以外では `x3::win_experts` を呼びます。この呼び出しが失敗すると `layer()` は `err` に `exl3 win_experts failed` を設定して失敗を返します。切替自体に専用ログはありません。

`docs/DETAILS.md` にはこの変数の説明や測定値は見つかりませんでした。そのため、上記はコードで確認できる経路の説明で、性能差の主張はしていません。

## 根拠

- `src/dsv41/ds4_model.cu:983-987` — `DS4_MOE_TOKEN` の読み取り、既定値、整数変換と `moe_token_path` の保存。
- `src/dsv41/ds4_model.cu:8458-8462` — `wp.async` の決定式。
- `src/dsv41/ds4_model.cu:9051-9053,9077-9098` — 非同期経路、単一 token 判定、token 用 MoE 計算と CPU lane の応答待ち。
- `src/dsv41/ds4_model.cu:9099-9137` — window 用経路、形式別 `win_experts` 呼び出しと失敗時のエラー。

