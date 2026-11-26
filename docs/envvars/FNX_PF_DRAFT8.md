# `FNX_PF_DRAFT8`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Strata split engine の prompt prefill で MTP draft layer の状態を作るタイミングとまとめ方を切り替える。off（既定）では main model の各 prompt chunk を処理する途中で `prefill_draft` を呼ぶ。on ではこの呼び出しを省き、main prefill の stream 完了後に各 chunk の最終 residual を使って MTP draft rows をまとめて処理する。対象は `Engine::prefill_pass` の経路であり、MTP が attach されていない場合は値にかかわらず分岐結果に影響しない。`prefill_draft` と `draft_rows` は draft layer の prompt K/V・QSA state を作る処理で、通常の prompt token の結果をこの分岐で選び直す処理ではない（`engine/src/split/src/prefill.cu:1262-1297,1773-1817`）。

## 値と判定

`env_flag` は `env_int(name, 0) != 0` で判定する。`env_int` は unset のときだけ既定値を返し、設定値は符号任意の base-10 整数全体として `strtoll` で解析する。空文字、空白、末尾の文字、範囲外の整数は受け付けず、`<name>: '<value>' is not a whole number` の `std::runtime_error` を投げる。整数として解析できた値は 0 のみ off、非ゼロは on（負数も on）であり、真偽値文字列としての解析や clamp はない（`engine/src/split/src/env.hpp:15-21,33-39,51-52`）。

| ビルド・経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| split engine の prefill | `0`（off） | `1`、`-1`、`2` など、整数として解析できる非ゼロ値 | `0`、`-0`（off）。空文字、`true`、`1x`、前後に空白のある値、整数範囲外は無効値として扱われ、例外になる |

## 有効になる条件

- split engine の `Engine::prefill_pass` が実行されること。対象コードは `engine/src/split/src/prefill.cu` にある（`engine/src/split/src/prefill.cu:1391-1397,1773`）。
- `Engine::mtp_attach` によって MTP draft layer が engine に attach されていること。未 attach なら `mtp_` が null で、両方の draft 分岐を通らない（`engine/src/split/src/engine.cu:1251-1254`; 条件分岐は `engine/src/split/src/prefill.cu:1774,1782,1805`）。
- DFlash2 だけを attach した経路では `mtp_` を設定しないため、このフラグの draft-layer 分岐は動かない（`engine/src/split/src/engine.cu:1251-1254`; `engine/src/split/tools/sfnx.cpp:1124-1133`）。CLI の `--mtp` 等は MTP attach の有無を決めるが、この環境変数自体を上書きする処理は確認できない。

## 実行時の詳細

値は `Engine::prefill_pass` 内の関数ローカル `static const bool` として最初にこの関数が通った時に読み取られ、その後の呼び出しでは同じプロセス内で再読込されない。したがって、その後に環境を変更しても反映されない。明示的な子プロセスへの転送・上書きはこの変数について確認できない（`engine/src/split/src/prefill.cu:1773`; `engine/src/split/src/env.hpp:33-39,51-52`）。

off かつ MTP attach 済みの場合、各 chunk で main layers の処理に続いて `prefill_draft(C, set)` を実行する。on の場合はこの per-chunk 呼び出しを飛ばす。Hyper-connection split が有効なら draft rows の前に各 card の stream event を待ち、全 card の prefill stream を同期して ring error を確認した後、各 chunk の main residual `p.R` を source に `draft_rows` を実行する。chunk 内を `MAXT` 行以下に区切り、各行に対応する次 token（chunk 内の次 token、または chunk の終端 token）を渡す。`MAXT` は 16。`draft_rows` は MTP が必要なこと、行数が `1..MAXT` で各行に token が一つあること、context 範囲内であることを検査し、draft layer を実行する。prompt prefill 側はその返り値を使わない（`engine/src/split/src/prefill.cu:1774-1817`; `engine/src/split/src/model.hpp:43`; `engine/src/split/src/engine_common.cu:1405-1414`）。

## ログと測定値

この変数専用の有効・無効ログはない。整数として不正な値は `env_int` の例外になり、`sfnx` の実行中エラー経路では `ERR <例外文>` を stdout、`sfnx: failed: <例外文>` を stderr に出して status 1 で終了する。`fnx_run` では stderr に `fnx_run: <例外文>` を出して status 1 で終了する（`engine/src/split/src/env.hpp:33-39`; `engine/src/split/tools/sfnx.cpp:1097-1102,1137-1140`; `engine/src/split/tools/fnx_run.cpp:1364-1373`）。Strata の `docs/DETAILS.md` の Draft layer 節にはこのフラグの説明や比較測定値は見当たらず、性能差は記載しない。

## 根拠

- `engine/src/split/src/prefill.cu:1262-1297,1773-1817` — MTP prompt state 処理、フラグ読取、分岐、同期、まとめた draft rows。
- `engine/src/split/src/env.hpp:15-21,33-39,51-52` — 整数全体の parse、unset の既定、非ゼロ判定、無効値の例外。
- `engine/src/split/src/model.hpp:43` — `MAXT = 16`。
- `engine/src/split/src/engine.cu:1251-1254`、`engine/src/split/src/engine_common.cu:1405-1414` — MTP attach と `draft_rows` の前提・処理。
- `engine/src/split/tools/sfnx.cpp:1097-1102,1137-1140`、`engine/src/split/tools/fnx_run.cpp:1364-1373` — 実行時例外の観測経路。
- `docs/DETAILS.md:376-383` — draft layer の資料との照合（このフラグの記載・測定値なし）。
