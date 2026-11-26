# `STRATA_DBG_ROUTE_OVERRIDE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP 系の prefill `run_impl` にある研究用フックで、MoE router が選んだ expert ID と routing weight を、指定ファイル中に対応レコードがあれば差し替える。通常の routing の後に実行され、差し替えられた `m.ids` と `m.w` は後続の expert 処理へ渡る。コメントも「opt-in, never on by default」と位置づけている。Metal の `run()` は `metal_engine::prompt_run` に分岐して戻るため、この `run_impl` の置換処理は通らない（`engine/src/prefill/prefill.cpp:5585-5587, 5588-5594, 5641-5645, 9629-9650`）。

## 値と判定

値は文字列として解釈・数値変換されず、`std::getenv` の null 判定だけに使われる。未設定ならこの変数による route override は無効。空文字を含む設定済み値は有効扱いで、そのままファイルパスとして `fopen(path, "rb")` に渡される。したがって `1`、`0`、`true`、`false`、空白を含む文字列は真偽値ではなく、各文字列どおりのパスである。空文字や開けないパスはファイルを読めず、override レコードは空になる（`engine/src/prefill/prefill.cpp:5592-5594, 5606-5610`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP の `run_impl` が MoE 層を処理 | override なし | 開けるファイルパス。数値・真偽値としての書式検査なし | ファイルを開けないパスではレコードなし。空文字もこのケース |
| layer-major prefill の適用判定 | この変数だけでは拒否しない | 空文字を含め、環境変数が存在すれば layer-major を拒否 | なし（値内容を検査しない） |

この変数に対応する CLI 引数や設定ファイル経由の値は見つからず、別の設定値による優先・fallback もない。ファイル形式の行数フィールドは `int32` から `size_t` に変換して領域を確保するが、負値・過大値を含む上限チェックはないため、コード上で安全な値域は定義されていない（`engine/src/prefill/prefill.cpp:5611-5615`）。

ファイルは繰り返しレコードとして読み込まれる。各レコードは `int32` 3 個（layer、position、行数）に続き、`行数 * K` 個の `int32` expert ID、その後 `行数 * K` 個の `float` weight からなる。`K` はビルド対象 geometry の `n_expert_used`。読み込み時にレコードの layer・position・行数や ID・weight の妥当性を検査するコードはなく、実行時には当該チャンクの `T * K` 個と一致するかだけを確認する（`engine/src/prefill/prefill.cpp:310-312, 5605-5617, 5641-5645`）。

## 有効になる条件

- CUDA/HIP 系の prefill が `run_impl` を実行し、MoE 層の router 処理まで到達すること。通常の router 投影と `route(...)` は先に実行される（`engine/src/prefill/prefill.cpp:5585-5587`）。
- 対象レコードのキーが、その呼び出しで計算された `(layer, position)` と一致し、レコードの ID 要素数が `T * K` と一致すること。一致しないレコードは置換されず、元の routing が残る（`engine/src/prefill/prefill.cpp:5611-5617, 5622-5623, 5641-5645`）。
- layer-major prefill が有効候補になっている場合、この変数が設定されていると `lm_prepare` は「routing or row debug dump」として layer-major を辞退し、通常の `run_impl` 経路へ進ませる。layer-major 自体が選ばれていない場合、この拒否判定は影響しない（`engine/src/prefill/prefill.cpp:8205-8209, 9657-9705`）。
- `STRATA_DBG_FEAT` が同時に設定されていれば同じフックブロックで feature dump も行われるが、route override との値の優先順位はない。override は読み込まれた対象レコードがあるときだけ router 結果に上書きされる（`engine/src/prefill/prefill.cpp:5592-5595, 5625-5645`）。

## 実行時の詳細

`run_impl` の各 MoE 層で router を計算した後、関数内 static の `ovr_path` が初回に環境を読みます。変数が未設定でなければ、同じく関数内 static の map 初期化で環境を再取得してファイルを一度だけ `rb` で開き、レコードを map に保持します。以降のリクエストやチャンクではファイルを再読込せず、プロセス実行中に環境変数やファイル内容を変更してもこの path/map の初期化結果は更新されません（`engine/src/prefill/prefill.cpp:5591-5594, 5606-5621`）。

各層の position キーは絶対 token position `pos0` からではなく、関数内 static の `posl[l & 63]` を読み、その値を当該チャンクの `T` だけ進めて作られる。カウンターはプロセス内で保持され、セッションやリクエストの開始時にリセットする処理はここにはない。ファイル中のキーとチャンクの行数が合致した場合、ID 配列と weight 配列を GPU 側の `m.ids` / `m.w` へコピーする（`engine/src/prefill/prefill.cpp:5604, 5622-5624, 5641-5645`）。

ファイルが開けない場合は空 map のまま進み、明示的なエラーや警告は出さない。開けたファイルでは読み込んだレコード数を stderr に `route override: %zu records` の形式で出す。途中で header または配列の読み取りが不完全になると読み込みループを抜け、完全に読めなかった当該レコードは map に加えない。対象キーまたは `T * K` 要素数が合わないときも、エラーにせず元の routing を使う（`engine/src/prefill/prefill.cpp:5609-5620, 5611-5617, 5641-5645`）。

layer-major 候補時の辞退ログは `strata prefill: layer-major off for this prompt: a routing or row debug dump`。同じ理由のログは `said` static により繰り返し抑制される。短い prompt などで layer-major 候補がそもそも有効でない場合、この変数を理由とするログは出ない（`engine/src/prefill/prefill.cpp:8205-8209, 9657-9703`）。

## ログと測定値

route override ファイルを開けた場合に `stderr` へ `route override: %zu records` を出す。ファイルを開けない場合、キー不一致、チャンク行数不一致について専用ログはない。layer-major の辞退時には上記の理由ログが出る。ソースと関連する `docs/DETAILS.md` に、この変数についての性能測定値は見当たらない。

## 根拠

- `engine/src/prefill/prefill.cpp:5585-5595` — router 実行後の研究用 hook と環境値の存在判定。
- `engine/src/prefill/prefill.cpp:5604-5624` — static cache、ファイルレコードの読み込み、position カウンター。
- `engine/src/prefill/prefill.cpp:5641-5645` — キー・サイズ一致時の GPU routing ID / weight 差し替え。
- `engine/src/prefill/prefill.cpp:8205-8209, 9657-9705` — layer-major prefill の辞退条件と通常経路への続行。
- `engine/src/prefill/prefill.cpp:310-312` — `K` のビルド geometry 上の定義。
