# `STRATA_SELECT_TWO_PASS_CHECK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の prompt QSA 選択で、`STRATA_SELECT_TWO_PASS=1` により二段階 scorer が実際に使われたバッチについて、通常の 3xTF32 scorer と選択結果・score を照合する診断スイッチである。診断用の参照 score と ID を別途計算し、結果を集計する。選択処理そのものをこの変数が切り替えるわけではないが、追加計算・メモリを使い、比較バッファ確保などに失敗すると prompt を失敗させることがある。実装は `engine/src/kernels/cuda/qsa_select.cu` の `qsa_two_pass_check_on()` と `qsa_two_pass_check()`、呼び出し側は `engine/src/prefill/prefill.cpp` の QSA selection 部分にある（`qsa_select.cu:3904-3909, 3975-3994`; `prefill.cpp:5354-5369, 5394-5437`）。

## 値と判定

CUDA 実装は `std::getenv` の戻り値について、値が null でなく、かつ文字列全体がちょうど ASCII の `1` である場合だけ有効にする。数値変換、空白除去、大文字小文字変換はしない。未設定、空文字、`0`、`true`、`01`、`1anything`、` 1` は無効である。`qsa_two_pass_check_on()` の関数内 `static const bool` に初回呼び出し結果を保存する（`qsa_select.cu:3904-3909`）。

この変数を CLI 引数や設定ファイルから上書きする経路は見つからない。実装はプロセス環境を直接読む。

| 条件（build / backend） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA (`__HIPCC__` ではない) | 無効 | `1` | 空文字、`0`、`true`、`01`、`1x` |
| HIP / gfx906 HIP compatibility | `qsa_two_pass_check_on()` は常に `false`。この関数では環境変数を読まない | なし | すべて無効 |
| Metal | prompt selection の check 呼び出しが `#if !defined(STRATA_GPU_METAL)` で除外される | なし | すべて無効 |
| SYCL | 対象変数を読む実装・呼び出しは見つからない | なし | Strata 側の動作なし |

CUDA でも `prefill.cpp` の `static const bool tp_check = tp_on && qsa_two_pass_check_on();` は短絡評価される。`STRATA_SELECT_TWO_PASS` が有効でない場合は check 変数をこの箇所から読まず、`tp_check` は false のまま固定される。初回評価後にプロセス環境を変更しても値は反映されない（`prefill.cpp:5361-5363`; `qsa_select.cu:3904-3909`）。

## 有効になる条件

- CUDA build であること。HIP 実装の `qsa_two_pass_check_on()` は常に false であり、Metal は比較呼び出しをコンパイル対象から外す。SYCL にこの変数の読み取りはない（`qsa_select.cu:4008-4021`; `prefill.cpp:5355-5356, 5394-5399`）。
- `STRATA_SELECT_TWO_PASS=1` が必要（同スイッチも完全一致の `1` だけを要求する）。二段階 scorer 自体は CUDA prompt の tensor-core selection 用で、sm_80 以上かつ `STRATA_QSA_WARP` が `1` / `select` でなく、対応する CUDA device・scratch・selection geometry が必要である。非対応 card などでは二段階 scorer は使われず、比較も実行されない（`qsa_select.cu:3873-3892, 3896-3902, 3934-3942`; `qsa_two_pass_status.hpp:12-13, 21-34`）。
- prompt の chunked QSA selection で、`STRATA_SELECT_TWO_PASS_MIN` のブロック閾値を満たす必要がある。既定は 4096 blocks。コードは chunk の最終 query の block 数で key 準備を判定し、各 selection batch では `active >= tp_min` を判定する。`STRATA_SELECT_OLD` が設定されていると二段階 scorer を呼ばない（`prefill.cpp:5361-5369, 5371-5391`; `qsa_two_pass.hpp:60-62`）。
- `qsa_block_scores_two_pass()` が成功し、`tp_call` が true になったバッチだけ比較する。通常 scorer に fallback したバッチは比較対象外（`prefill.cpp:5381-5393, 5399`）。
- 再比較 kernel の shared-memory mark 配列が 48 KiB 以下である必要がある。`max_blocks` から求める mark 領域が 48 KiB を超えると比較を飛ばし、プロセス内で一度だけ `qsa two-pass check: %lld blocks are too many to check` を stderr に出す（`qsa_select.cu:3978-3984`）。

## 実行時の詳細

二段階 scorer の score row を `qsa_block_topk()` に渡した後、`tp_call && tp_check` のときだけ、同じ query の score を `qsa_block_scores_tc()` で 3xTF32 再計算し、その row から参照 ID も作って `qsa_two_pass_check()` に渡す（`prefill.cpp:5392-5437`）。参照 score / ID の領域はまず `m.attn` 内の二段階 scratch 後方を使う。容量が足りない場合は CUDA device memory を追加確保し、確保できないと `err` を `STRATA_SELECT_TWO_PASS_CHECK: no room for its buffers` にして prompt 処理を失敗させる。参照 tensor-core scorer が実行できない場合も `STRATA_SELECT_TWO_PASS_CHECK: the tensor-core scorer did not run` で失敗する（`prefill.cpp:5400-5433`）。追加確保した領域は `m.owned` に保持される（`prefill.cpp:5409-5427`; 構造体のバッファ欄 `prefill.cpp:1574-1578`）。

比較 kernel は、各 query の選択 ID の不一致数、再 score した block が参照 3xTF32 score と bitwise で異なる数、再 score せず single-pass score を使った block のうち誤差 bound を外れた数、および最大誤差/bound 比を device counter に加算する（`qsa_select.cu:3811-3869`）。prompt 終了時、二段階 scorer の統計を読み出して reset し、二段階 scorer の呼び出しがあれば check query 数が 1 以上のときだけ比較集計も stderr に出す。CUDA stream の同期を伴う。集計取得に失敗した場合はこのログを出さない（`prefill.cpp:7925-7927, 7943-7966`; `qsa_select.cu:3996-4006`）。

この check は token 選択結果を置き換えない。再計算した参照 row / IDs は診断専用であり、通常の `m.sel_scores` / `m.sel_ids` を上書きしない（`prefill.cpp:5392-5436`）。ただし、check kernel 起動エラーでは `qsa two-pass check: <CUDA error>` を stderr に出して `std::exit(1)` する（`qsa_select.cu:3985-3994`）。

## ログと測定値

比較結果が集計されたときの stderr 行は次の形式である。`ids not the 3xTF32 scorer's` は ID が異なった query 数と ID entry 数、`scored again` は再 score した block のうち bitwise 不一致だった数/比較数、`kept` は bound 外だった数/対象数を示す（`prefill.cpp:7955-7963`）。

```text
strata prefill: two-pass check: %llu queries, %llu with ids not the 3xTF32 scorer's (%llu ids); scored again: %llu of %llu blocks not the 3xTF32 score bit for bit; kept: %llu of %llu single-pass scores outside the bound, the largest |S1 - S3| / bound %.4g
```

Strata の `docs/DETAILS.md:1317-1320` は slow diagnostic と説明し prompt 後に ID 差を出すとしている。現行実装では上記の追加統計も出す一方、二段階 scorer の呼び出しがない prompt では比較行を出さない。速度・精度の測定値はこの変数について同資料にない。

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:3904-3909` — CUDA での環境値判定と関数内 cache。
- `engine/src/kernels/cuda/qsa_select.cu:3975-4006` — 比較 kernel の起動、上限・失敗時のログ、統計の読出し。
- `engine/src/prefill/prefill.cpp:5354-5393` — 二段階 scorer の条件と通常 scorer への fallback。
- `engine/src/prefill/prefill.cpp:5394-5437` — check 呼び出し、参照 buffer 選択・確保、失敗経路。
- `engine/src/prefill/prefill.cpp:7943-7966` — prompt 終了時の統計集計と stderr 出力。
- `engine/include/strata/kernels/qsa_two_pass_status.hpp:21-34` — 二段階 scorer が非対応のときの条件と警告。
- `engine/include/strata/kernels/qsa_two_pass.hpp:60-62, 130-137` — 閾値の既定値と check 統計項目。
- `docs/DETAILS.md:1310-1320` — 現行ソースとの照合に使った設計資料の記述。
