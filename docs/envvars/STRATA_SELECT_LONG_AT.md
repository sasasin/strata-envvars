# `STRATA_SELECT_LONG_AT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_SELECT_LONG_AT` は、長文脈用 QSA select を使い始める decode 窓の位置を cells 数で指定する閾値です。`Verifier` は窓の開始位置 `pos0` と窓幅 `T` の合計が閾値以上なら、長文脈用の block-score / top-k 呼び出しを記録した graph variant を選びます。比較は `>=` なので閾値ちょうどの窓から対象です。閾値を設定しただけでは機能は有効にならず、`STRATA_SELECT_LONG=1` が必要です。`engine/src/core/verify.cpp:195-219, 2266-2276, 3710-3715, 3837-3845`

長文脈用関数は通常関数と同じ selection IDs / score bits を意図する実装コメントがあります。閾値はどのセルを選択対象にするかを変え、token の選択規則そのものを別のものにする設定ではありません。`engine/src/core/verify.cpp:195-199, 2266-2276`; `docs/OLDER_GPUS.md:184-191`

## 値と判定

`select_long_at()` が `std::getenv` で読み、値が null または空文字なら `65536`、それ以外は `std::atoll` で変換します。文字列全体の妥当性検査、errno 検査、範囲 clamp はありません。したがって `64K` は先頭の `64` が変換され、`0anything` や数値として読めない文字列は `0` になります。空白や符号を含む接頭部の扱いは `atoll` の変換に従います。`engine/src/core/verify.cpp:213-219`

| 条件 | unset | 有効になる値の例 | 判定例・境界 |
|---|---:|---|---|
| `STRATA_SELECT_LONG=1` かつ長文脈用経路が利用可能 | `65536` cells | `100000` → `100000` cells | 空文字 → `65536`; `0`, `0anything`, `abc` → `0`; `-1` → `-1`。`pos0 + T >= 閾値` で切り替わり、0 以下なら通常の非負 window 位置では常に閾値以上 |
| `STRATA_SELECT_LONG` が有効でない | 閾値が評価されても variant 選択に使われない | なし | 閾値だけ設定しても長文脈用 variant は選ばれない |

値の読み取り結果は関数内 `static const int64_t` に保存されます。最初に有効な経路から閾値が必要になった時点の値をプロセス中に使い続け、実行中に環境を変更しても再読込しません。CLI 引数や設定ファイルによる上書きはこの関数にはありません。`engine/src/core/verify.cpp:214-219`

## 有効になる条件

- `STRATA_SELECT_LONG` の値が未設定でなく、先頭文字が `'1'` のときだけ gate が開きます。`1`, `10`, `1anything` は gate を開きます。`1` 以外の先頭文字（例 `0`, `t`, 空文字）は開きません。文字列全体の比較ではありません。`engine/src/core/verify.cpp:200-212`
- 長文脈用 multi-CTA kernel が含まれる CUDA build（`STRATA_EXPERIMENTAL_SM60`）が必要です。build が対応しない場合、`STRATA_SELECT_LONG=1` に対して warning を出して feature を無効にします。HIP / Metal や通常の非実験 build では scratch が 0 のため、この経路は有効になりません。`engine/src/core/verify.cpp:200-209`; `engine/src/kernels/cuda/qsa_select.cu:3221-3227`
- 設定が使われるのは `Verifier` の decode window にある QSA select です。該当する verifier / QSA 経路を実行しない処理には影響しません。window の graph を位置に応じて選び、`record_window` 内の select 呼び出しが長文脈用 variant を記録します。`engine/src/core/verify.cpp:3710-3715, 3837-3845, 5899-5917, 2266-2276`
- 長文脈用 graph を選んでも、内部の scorer / top-k は別条件で通常実装に fallback することがあります。`STRATA_SCORES_DX=0` は長文脈 scorer を止めます。`STRATA_TOPK_MULTI=0` は multi-CTA top-k を止め、`STRATA_TOPK_OLD` が設定されている場合も multi-CTA top-k を使いません。unset 時の scorer は compute capability 6.x（または実装上の SM70 default）、top-k は compute capability 6.x / SM70 default の対象で有効です。`STRATA_TOPK_MULTI` の非空値は `atoi` で変換され、0 なら off、0 以外なら any-card mode です。`engine/src/kernels/cuda/qsa_select.cu:3108-3132, 3174-3195, 3230-3256`
- top-k に multi-CTA 版を使うには、ほかにも `nq > 0`, `multi_scratch != nullptr`, `active_blocks <= 0`, 対応する index block / capacity などの条件が必要です。満たさなければ通常 top-k に戻ります。scorer も query 数、QSA shape、active-block 条件が合わなければ通常 scorer を使います。`engine/src/kernels/cuda/qsa_select.cu:3230-3256`

## 実行時の詳細

閾値は各窓の位置判定で参照されます。通常の run 経路では capture 前に `sel_long_` を決め、window graph を選択します。pipelined window 経路では `capture_all()` が必要な window 幅について通常 variant と長文脈 variant の graph をあらかじめ capture し、`pl_launch()` が同じ位置条件でどちらかを launch します。`pos0 + T` は session の context 上限を超えないことも別途検査されます。`engine/src/core/verify.cpp:3710-3718, 3837-3845, 5899-5917, 5964-5998`

閾値を超えて長文脈 variant を選んだ後も、実際に scorer / top-k のどちらかが専用 kernel を使うかは上記の build、環境変数、shape 条件で決まります。長文脈 scorer の起動エラーは `qsa_block_scores (dx): ...` を stderr に出して `exit(1)`、multi-CTA top-k の起動エラーは `qsa_block_topk multi: ...` を stderr に出して `exit(1)` します。通常経路へ fallback する条件ではこれらの専用 kernel は呼ばれません。`engine/src/kernels/cuda/qsa_select.cu:3167-3170, 3213-3215, 3230-3256`

## ログと測定値

`STRATA_SELECT_LONG_AT` 自身は、未設定・不正文字列・閾値到達のいずれでもログを出しません。build 非対応時の warning は gate 変数 `STRATA_SELECT_LONG=1` に対するもので、文言は `strata verify: STRATA_SELECT_LONG=1 needs the CUDA build with STRATA_EXPERIMENTAL_SM60; ignored` です。`engine/src/core/verify.cpp:200-209`

`docs/OLDER_GPUS.md` は長文脈用経路について、4 基の GP100 での測定値と測定条件を記載していますが、閾値単独の効果を測った値ではありません。本調査では閾値の独立した測定値は確認できません。`docs/OLDER_GPUS.md:184-191`

## 根拠

- `engine/src/core/verify.cpp:195-219` — gate と閾値の読み取り・既定値・cache。
- `engine/src/core/verify.cpp:1206-1208, 3710-3718, 3837-3845, 5899-5917, 5964-5998` — scratch、window variant 選択、graph capture / launch。
- `engine/src/core/verify.cpp:2266-2276` — 長文脈用 QSA select の呼び出し。
- `engine/src/kernels/cuda/qsa_select.cu:3108-3132, 3174-3195, 3221-3256` — build guard、関連環境変数、fallback 条件。
- `docs/OLDER_GPUS.md:184-191` — Strata の説明と測定条件。
