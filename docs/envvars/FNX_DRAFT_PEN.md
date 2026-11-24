# `FNX_DRAFT_PEN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

MTP draft 層の logits を作る際、生成リクエストの repetition / frequency / presence penalty を draft にも適用するかを制御する。未設定時は適用する。`0` では draft 層の候補生成に penalty row を渡さず、非ゼロでは penalty row を渡す。対象は draft 側の予測であり、検証時に本体モデルから次 token を選ぶ分布の penalty を無効化する設定ではない。`Session::generate` は通常の MTP draft 呼び出しに、`BatchDecoder` は複数 lane の draft 呼び出しにこの判定を使う（`engine/src/split/src/session.cpp:406-411,440-445`、`engine/src/split/src/batch.cpp:65-77,105-117`）。

Strata の `docs/DETAILS.md` は sampler penalty が speculative check 対象に適用される一般動作を説明するが、この変数や draft 層への切替は記載していない（`docs/DETAILS.md:609-617`）。現行動作の根拠は以下の split engine 実装。

## 値と判定

共通 helper `env_int` が `getenv` で取得し、10 進整数として文字列全体を `strtoll` で解析する。未設定だけが既定値 `1` となる。設定値は `long long` の範囲内で、先頭の `+` / `-` と数字のみを受け付ける。空文字、前後の空白、`true` / `false`、`1.0`、`0anything`、数字の後の文字、範囲外整数は parse error。整数値は `!= 0` で判定されるため、`1` や `-1` は ON、`0` は OFF である（`engine/src/split/src/env.hpp:15-21,33-39`）。

| 実行経路 | unset | 設定時に draft penalty が有効 | 無効 |
|---|---:|---|---|
| `Session::generate`（単一 session） | 1 | `1`、`-1` など parse できる非ゼロ整数 | `0` |
| `BatchDecoder`（batch decoder） | 1 | `1`、`-1` など parse できる非ゼロ整数 | `0` |

ここでの有効・無効は環境変数による許可判定。どちらの経路でも、実際に penalty row を作るには当該 lane / request が `penalizes(s)` を満たす必要がある。parse できない値に fallback はなく、helper が `FNX_DRAFT_PEN: '<値>' is not a whole number` を含む例外を投げる（`engine/src/split/src/session.cpp:406-411`、`engine/src/split/src/batch.cpp:70-77`、`engine/src/split/src/session.cpp:109-111`、`engine/src/split/src/env.hpp:34-39`）。

## 有効になる条件

- Strata split engine の `sfnx`、または split engine の `fnx_run` 経路で使われる設定で、ソース上の読み取りは `engine/src/split` 内に限られる。`sfnx` は通常 `--mtp` を使うと MTP drafter を attach し、`--draft dflash2` では代わりに DFlash2 bridge を attach する（`engine/src/split/tools/sfnx.cpp:66-67,111-114,1120-1133`）。CUDA / HIP の `FNX_HIP` 条件によるこの変数の値判定差はない。
- Penalty がないリクエストでは、MTP draft の値が非ゼロでも penalty は適用されない。`penalizes(s)` は `temperature > 0`、`pen_last_n > 0`、かつ repeat / freq / present のいずれかが中立値から変わっている場合に限り true（`engine/src/split/src/session.cpp:100-110`）。greedy (`temperature == 0`) は penalty 自体が無効である（同 `:113-123`）。
- DFlash2 経路の draft は `Session::generate` 内の別分岐で作られ、`pen_drafts` は渡されない（`engine/src/split/src/session.cpp:453-456,565-593`）。したがって設定は DFlash2 の draft logits を変更しない。ただし penalty が有効な request では `Session::generate` が先に変数を parse するので、無効な文字列は DFlash2 使用中も例外になる（同 `:405-411,453-456`）。
- `--batch` の値が 1 より大きく、`FNX_BATCH_DRAFTS` が off でない場合に限り、`sfnx` が `BatchDecoder` を構築して batch 用の値を読む（`engine/src/split/tools/sfnx.cpp:448-458`）。Batch decoder はその後 MTP draft に penalty row を付ける。DFlash2 の batch 分岐は `draft_df2` へ進み、MTP 用 penalty row を使わない（`engine/src/split/src/batch.cpp:330-336,382-416`）。
- CLI 引数や request sampling 値が `FNX_DRAFT_PEN` を上書きする処理はない。request の sampling penalty 設定は「実際に penalty があるか」を決め、環境変数はその penalty を MTP draft にも渡すかを決める（`engine/src/split/src/session.cpp:403-411`、`engine/src/split/src/batch.cpp:105-110`）。

## 実行時の詳細

単一 session では `Session::generate` の呼び出しごとに判定する。`penalizes(s)` が false の場合は `&&` の短絡評価により `env_int` 自体を呼ばず、設定値の parse も行わない。true の場合、MTP draft の前に penalty window から `Penalty::Row` を作り、`Engine::draft` に渡す。MTP chain の後続 draft でも、先に採用された draft token を window に追加して penalty row を更新する（`engine/src/split/src/session.cpp:398-411,439-445,561-618`）。

`Engine::draft` は penalty row を `draft_rows` に渡す。row がある場合、そこに含まれる repeat / freq / present 値と token index / count を draft vocab の各 card 範囲へ写し、GPU 側 draft logits に `penalize_row` を適用してから argmax を取る。row がない場合は penalty token 数を 0 にする（`engine/src/split/src/engine_common.cu:1395-1407,1417-1435`、`engine/src/split/src/engine.cu:1346-1354`）。Sampler candidate も同じ penalized logits から取得される（`engine/src/split/src/engine_common.cu:1463-1468`）。

Batch decoder は `BatchDecoder` constructor で一度だけ `env_int` を読み `pen_drafts_` に保存し、各 batch draft window と lane の penalty state にそれを使う。構築後に環境値を再読込する箇所はない（`engine/src/split/src/batch.cpp:65-87,105-117,338-375,382-416`）。単一 session 経路は次の `generate` 呼び出しで再評価する。ソース内にこの変数を書き換える処理は見つからなかった。

`FNX_DRAFT_PEN=0` でも、本体モデルの `top_tokens` 用 penalty row は別途作られており、検証側の候補計算は続く（`engine/src/split/src/session.cpp:487-502`、batch は `engine/src/split/src/batch.cpp:143-164`）。従ってこの設定で変わるのは draft の logits / draft token であり、検証分布そのものではない。コードコメントは speculative correction が draft と target 分布を補正する設計として説明している（`engine/src/split/src/session.cpp:407-410,490-524`）。

## ログと測定値

正常値を設定したことや penalty の有効化を知らせる専用ログはない。値が parse できない場合は helper の例外文言 `FNX_DRAFT_PEN: '<値>' is not a whole number` が発生する。`sfnx` の `fail` は標準出力に `ERR <例外文言>`、標準エラーに `sfnx: failed: <例外文言>` を出して終了コード 1 で終了する（`engine/src/split/src/env.hpp:34-39`、`engine/src/split/tools/sfnx.cpp:1094-1103`）。Batch decoder 経路では構築時に parse するため、該当構成なら最初の request より前に失敗する（同 `:448-458`）。単一 session では penalty を持つ request の `generate` 時に失敗し、penalty のない request では読み取り自体が短絡される（`engine/src/split/src/session.cpp:405-411`）。`fnx_run` からの例外は標準エラーに `fnx_run: <例外文言>` と出力され、終了コード 1（`engine/src/split/tools/fnx_run.cpp:1364-1373`）。

この変数の効果に関する測定値は、現行ソースと `docs/DETAILS.md` に条件付きで示されていない。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-39` — 整数の構文、境界、未設定値、無効値例外。
- `engine/src/split/src/session.cpp:100-123,398-445,487-524,561-618` — penalty 条件、単一 session の読み取り・draft / verify 処理。
- `engine/src/split/src/batch.cpp:65-87,105-117,143-164,330-416` — batch decoder の読み取り時期と draft 適用条件。
- `engine/src/split/src/engine_common.cu:1395-1435,1463-1468`、`engine/src/split/src/engine.cu:1346-1354,1417-1426` — MTP draft の penalty row 設定と logits への適用。
- `engine/src/split/tools/sfnx.cpp:448-458,1094-1103,1120-1133`、`engine/src/split/tools/fnx_run.cpp:1364-1373` — batch decoder 構築、DFlash2 / MTP の選択、失敗出力。
- `docs/DETAILS.md:609-617` — sampler penalty の一般説明との照合（`FNX_DRAFT_PEN` 自体の説明はなし）。
