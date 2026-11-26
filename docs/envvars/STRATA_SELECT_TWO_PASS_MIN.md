# `STRATA_SELECT_TWO_PASS_MIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の QSA prompt prefill で、二段階 block-score 経路を試す最小 block 数を指定する。既定値は 4096 blocks。`STRATA_SELECT_TWO_PASS=1` で二段階経路を要求した場合に限り、この値以上の batch を候補にする。値を 0 にすると block 数による足切りをなくすが、二段階経路自体を有効化する設定ではない。該当コードは `qsa_two_pass_min_blocks()` と prefill の選択処理にある（`engine/src/kernels/cuda/qsa_select.cu:3911-3917`, `engine/src/prefill/prefill.cpp:5354-5385`）。

## 値と判定

CUDA 実装は `std::getenv` の戻り値を `std::atoll` に渡す。未設定なら `kMinBlocksDefault`（4096）、設定済みなら先頭の整数部分を使い、負数は 0 に clamp する。空文字や整数で始まらない文字列は `atoll` により 0 になる。先頭空白と符号は整数変換で扱われ、数字の後ろの文字列は検査されない。正の値に上限 clamp はない。したがって、この設定は真偽値や数値文字列全体の厳密な検証ではない（`engine/src/kernels/cuda/qsa_select.cu:3911-3917`）。

| 実装 | unset | 例: 閾値 | 例: 0 になる値 |
|---|---:|---|---|
| CUDA | 4096 | `4096`, `+12`, `12xyz` → 4096 / 12 / 12 | 空文字、`abc`, `0anything`, `-1`（負数 clamp）→ 0 |
| HIP | 4096 | この変数を読まず、固定の既定値 | 値は判定に使われない |

`true` は整数として始まらないため 0、` 12` は 12、大文字小文字の区別は文字列判定としては行わない。CLI 引数や設定ファイルによる上書きはこの読み取り経路にはなく、CUDA では環境値が閾値の唯一の入力である。HIP 実装は `qsa_two_pass_min_blocks()` を既定値で返す（`engine/src/kernels/cuda/qsa_select.cu:3911-3917,4008-4018`）。

## 有効になる条件

- CUDA build の QSA prompt prefill がこの選択処理を通ること。Metal は呼び出し側で二段階経路のコードを除外する（`engine/src/prefill/prefill.cpp:5355-5370,5381-5386`）。
- `STRATA_SELECT_TWO_PASS` の値が文字列として厳密に `1` で、二段階経路が要求されること。未設定、空文字、`01`、`1x` などは要求にならず、閾値に達していても利用されない（`engine/include/strata/kernels/qsa_two_pass_status.hpp:12-18`, `engine/src/kernels/cuda/qsa_select.cu:3896-3902`）。
- 対象 batch の末尾 query の `n_bid + 1` が閾値以上であること。さらに各 selection batch の `active` block 数も閾値以上であること（`engine/src/prefill/prefill.cpp:5365-5369,5371-5385`）。
- 二段階 scorer が利用可能な CUDA device と query geometry、scratch 条件を満たすこと。device 判定は compute capability 8 以上と kernel shared-memory 属性設定の成功を要求し、`STRATA_QSA_WARP=1` または `select` の場合は無効になる（`engine/src/kernels/cuda/qsa_select.cu:3873-3892,3921-3943`）。
- `STRATA_SELECT_OLD` が設定されていないこと。設定されていると二段階経路を呼ばず、従来 scorer へ進む（`engine/src/prefill/prefill.cpp:5377-5389`）。
- chunked CUDA prompt path であること。layer-major prompt path では二段階 scorer は走らない（`engine/include/strata/kernels/qsa_two_pass_status.hpp:2-6`）。

条件を満たさない場合は通常の tensor-core scorer、またはそれが使えないときの block scorer に fallback し、その後の `qsa_block_topk` を実行する。閾値自体は選択結果を変更する条件ではなく、二段階 scorer を試す対象範囲を変える（`engine/src/prefill/prefill.cpp:5387-5393`）。

## 実行時の詳細

CUDA では値を `qsa_two_pass_min_blocks()` 内の function-local `static const` に保存し、prefill 側も `tp_min` を `static const` として保持する。初回評価後のプロセス環境変更は反映されない（`engine/src/kernels/cuda/qsa_select.cu:3911-3917`, `engine/src/prefill/prefill.cpp:5361-5369`）。

prefill chunk の QSA indexer append 完了後、末尾 query の block 数で key preparation を判定する。各 selection batch では末尾 query の active block 数が閾値以上で、二段階 key preparation が成功し、`STRATA_SELECT_OLD` が未設定の場合に二段階 scorer を呼ぶ。二段階 scorer が false を返した場合も既存 scorer に戻る。選択 ids はいずれの場合も `qsa_block_topk` が作る（`engine/src/prefill/prefill.cpp:5323-5342,5361-5393`）。

HIP 用実装は `STRATA_SELECT_TWO_PASS_MIN` を読み取らず 4096 を返し、二段階 scorer の stub は常に false を返す。そのためこの変数で HIP の閾値は変更されず、二段階 scorer は実行されない（`engine/src/kernels/cuda/qsa_select.cu:4008-4018`）。

## ログと測定値

二段階 score 経路が実際に呼ばれたとき、最初の呼び出しで stderr に `qsa select: two-pass scores on (STRATA_SELECT_TWO_PASS=1): ...` を一度出し、`qsa_two_pass_min_blocks()` の値を表示する（`engine/src/kernels/cuda/qsa_select.cu:3951-3956`）。閾値に達しない場合、この score-on ログはその理由だけでは出ない。機能要求が device/backend 条件で使えない場合、`STRATA_SELECT_TWO_PASS=1` が設定されていれば stderr に `strata: STRATA_SELECT_TWO_PASS=1 is not used on ...` と一度出る（`engine/include/strata/kernels/qsa_two_pass_status.hpp:21-34`, `engine/src/kernels/cuda/qsa_select.cu:3896-3902,4008-4011`）。

`docs/DETAILS.md` は既定 4096 blocks（16K cells）と RTX 3090 での prompt 測定を記載するが、その測定は同資料が示す `STRATA_SELECT_TWO_PASS` の説明であり、この閾値単独の性能測定ではない（`docs/DETAILS.md:1310-1320`）。

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:3911-3917` — CUDA での環境読み取り、既定値、変換、負値 clamp、cache。
- `engine/src/prefill/prefill.cpp:5354-5393` — prefill 内の閾値判定、他条件、fallback、top-k 呼び出し。
- `engine/src/kernels/cuda/qsa_select.cu:3873-3892,3921-3943,4008-4018` — CUDA device 条件、二段階 scorer の guard、HIP stub。
- `engine/include/strata/kernels/qsa_two_pass_status.hpp:12-34` — opt-in switch の厳密な値判定と非対応経路での警告。
- `engine/include/strata/kernels/qsa_two_pass.hpp:60-62` — 既定値 4096 の定義と単位。
- `docs/DETAILS.md:1310-1320` — 二段階選択の設計説明と資料記載の測定条件。
