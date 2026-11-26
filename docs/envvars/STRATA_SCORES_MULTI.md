# `STRATA_SCORES_MULTI`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA の block score 計算で、複数 query をまとめて処理する multi kernel を選ぶか制御する。未設定または `atoi` の結果が非 0 なら multi 経路が候補となり、`atoi` の結果が 0 なら通常の block scorer を使う。QSA の選択結果を変える設定ではなく、multi kernel は通常 kernel と同じ演算順で score を計算する設計である（CUDA 実装コメント: `engine/src/kernels/cuda/qsa_select.cu:973-978`）。

主な実装は `qsa_block_scores` の CUDA/HIP 共通ソースと SYCL 実装にある。単一 query の decode では通常 `qsa_block_scores` が呼ばれ、QSA fast-select を使うレイヤーではその後 top-k 選択と attention に進む（`engine/src/core/layer.cpp:1277-1289`）。verify の複数 slot 経路にも同じ設定が使われる（`engine/src/core/verify.cpp:2200-2215,2232-2249`）。

## 値と判定

CUDA/HIP と SYCL の各 `qsa_block_scores` は `std::getenv` の結果を `std::atoi` に渡し、関数内 `static const bool` に保存する。未設定なら `true`、設定されていれば `atoi(value) != 0` が有効条件である（CUDA/HIP: `engine/src/kernels/cuda/qsa_select.cu:1607-1609`、SYCL: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1632-1634`）。

| 条件（backend） | unset | multi が有効になる値（例） | multi が無効になる値（例） |
| --- | --- | --- | --- |
| CUDA / HIP | 有効 | `1`, `2`, `-1`, `1abc`（`atoi` の結果が非 0） | 空文字, `0`, `0anything`, `true`, `abc`（`atoi` の結果が 0） |
| SYCL | 有効 | `1`, `2`, `-1`, `1abc`（`atoi` の結果が非 0） | 空文字, `0`, `0anything`, `true`, `abc`（`atoi` の結果が 0） |

文字列全体の妥当性、大文字小文字、範囲の検査や clamp はない。`atoi` が先頭の整数部分を変換し、変換できない文字列は 0 となるため、たとえば `1abc` は有効、`0anything` は無効になる。環境変数から読むだけで、CLI 引数・設定ファイル・他の環境変数との優先順位は実装されていない。

## 有効になる条件

- `qsa_block_scores` の入力が正の query 数で、indexer geometry が対応する場合に score kernel の選択に進む。非対応 geometry または `nq > 65535` は `qsa_block_scores: unsupported indexer geometry` を stderr に出して終了する（CUDA/HIP: `engine/src/kernels/cuda/qsa_select.cu:2194-2200`、SYCL: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1625-1631`）。
- multi 経路は `nq <= 8` かつ `active_blocks <= 0` のときだけ使う。`MQ` は 8 と定義されている（CUDA/HIP: `engine/src/kernels/cuda/qsa_select.cu:973-978,2201-2205`、SYCL: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1632-1636`）。
- prefill から実 active block 数が渡される経路（`active_blocks > 0`）では、この変数が有効でも multi kernel は使わず、通常 scorer 系へ進む（`engine/src/prefill/prefill.cpp:9448-9455`、CUDA/HIP: `engine/src/kernels/cuda/qsa_select.cu:2201-2205`）。
- CUDA/HIP の verify slot batching が slot 一括 launcher を使うとき、multi 無効なら launcher は `false` を返し、呼び出し側が per-row の `qsa_block_scores` に fallback する。slot-group launcher も `!scores_multi_on()` で `false` を返す（`engine/src/kernels/cuda/qsa_select.cu:1997-2006,2018-2029`、`engine/src/core/verify.cpp:2200-2212,2232-2249`）。
- QSA fast-select を通らず別の index/select 実装を使う場合、この環境変数の判定箇所には到達しない。`qsa_layer` は `g_fast_select` が真のときに `qsa_block_scores` と `qsa_block_topk` を呼ぶ（`engine/src/core/layer.cpp:1277-1283`）。

## 実行時の詳細

初めて `qsa_block_scores` が呼ばれた時に環境値を読み、関数内 `static` に保持する。以降の呼び出しでは再読込しないため、プロセス稼働中に環境値を変更しても反映されない（CUDA/HIP: `engine/src/kernels/cuda/qsa_select.cu:1607-1609`、SYCL: `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1632-1634`）。起動時に明示的に読む処理や子プロセスへの転送は確認できない。

有効な場合、decode の multi kernel は最大 8 query を固定 grid で処理し、各 query の score を出力する。実際の通常 scorer との算術順序は同じとソースコメントに記されている（CUDA/HIP: `engine/src/kernels/cuda/qsa_select.cu:973-978,1004-1029`）。SYCL も `nq <= 8` の no-active-count 経路で multi kernel を submit し、それ以外は `block_scores_kernel` を submit する（`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1632-1690`）。

無効または条件外なら CUDA/HIP は通常の `block_scores_kernel` 系へ進む。verify の slot batching は一括 launcher が何も起動せず `false` を返した後、各 row を個別に計算する（`engine/src/kernels/cuda/qsa_select.cu:2005-2015,2025-2052,2273-2278`、`engine/src/core/verify.cpp:2204-2212,2242-2249`）。この設定による待ち時間・timeout・子プロセス管理はない。

## ログと測定値

この環境変数自体の値や on/off を報告するログはない。通常経路では、CUDA/HIP は kernel 起動エラー時に `qsa_block_scores multi: %s` または `qsa_block_scores: %s` を stderr に出して `exit(1)` する。slot launcher の geometry 不正時は `qsa_block_scores_slots: unsupported indexer geometry` または `qsa_block_scores_slot_groups: unsupported indexer geometry` を出して `exit(1)` する（`engine/src/kernels/cuda/qsa_select.cu:2001-2014,2021-2023,2225-2229,2273-2278`）。SYCL の multi 経路は submission 時に明示的な環境変数ログを出さず、同ファイルには CUDA 風の last-error 終了処理もありません（`engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1641-1672`）。

Strata の `docs/DETAILS.md` に本変数固有の性能測定値は見つからなかった。`docs/QSAROWS.md` と `docs/DETAILS.md` の QSA_ROWS 記述は別の環境変数の実装・測定であり、ここでの性能値として転用していない（`docs/DETAILS.md:1293-1301`）。

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:973-978,1004-1029,1607-1609,1997-2052,2194-2229,2273-2278`
- `engine/sycl/src/kernels/cuda/qsa_select.dp.cpp:1625-1690`
- `engine/include/strata/kernels/qsa_select.hpp:33-47`
- `engine/src/core/layer.cpp:1277-1289`
- `engine/src/prefill/prefill.cpp:9448-9457`
- `engine/src/core/verify.cpp:2191-2215,2232-2249,2515-2521`
- `docs/DETAILS.md:1293-1301`
