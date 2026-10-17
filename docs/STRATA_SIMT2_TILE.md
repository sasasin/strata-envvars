# `STRATA_SIMT2_TILE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の QSA block scorer で、`STRATA_SELECT_SIMT=2` が選ぶ FP32 SIMT カーネルのタイル形状を切り替えます。未設定または変換結果が `2` 以外なら 32 query × 128 block、値の変換結果が `2` なら 64 query × 64 block です。この変数だけでは SIMT scorer を有効にしません。

## 値と判定

| 値の状態 | 判定 | 選ばれる形状 |
|---|---|---|
| 未設定 | 既定値 `1` | 32 × 128 |
| 設定あり、`atoi` の結果が `2` | `tile == 2` | 64 × 64 |
| 設定あり、`atoi` の結果が `2` 以外 | `tile != 2` | 32 × 128 |

`std::atoi` で文字列全体の妥当性を検査せず整数変換します。したがって空文字や数値に変換できない文字列は通常 `0` となり、32 × 128 側です。`2x` のように先頭の整数部分が `2` なら 64 × 64 側になり、符号や先頭空白を含む入力も `atoi` の規則で変換されます。大文字小文字の比較はありません。整数範囲外の入力に対する `atoi` の結果はこの実装から保証できません。

## 有効になる条件

- CUDA コンパイルの経路であること（`__HIPCC__` でない側の分岐）。HIP 側にはこの変数の読み取りがありません。
- 対象 GPU の compute capability major が 8 未満であること。sm_80 以上では通常の tensor-core scorer に進み、この変数は参照されません。デバイス属性を取得できない場合もこの SIMT 分岐には進みません。
- `STRATA_SELECT_SIMT` の値が `2` として認識されていること。この親設定が無効・未設定なら通常 scorer に fallback し、この変数は読み取られません。親設定は先頭文字が `2` かどうかで判定されるため、たとえば `2anything` も SIMT=2 経路に入ります。
- fast QSA selection が使われ、`qsa_block_scores_tc` が呼ばれること。通常の prompt selection と `qsa_select_bench` が該当します。prompt 呼び出し側が古い scorer を強制する場合や、`qsa_block_scores_tc` が `false` を返して fallback する場合、このタイル設定は使われません。

## 実行時の詳細

`qsa_block_scores_tc` は sm_80 未満で `STRATA_SELECT_SIMT` を最初に評価し、その結果を `static` に保存します。親設定が `2` なら同じ呼び出しで本変数も `static const int` として一度だけ読みます。以後、プロセス内で環境を変更しても、親設定とタイル値のキャッシュは再評価されません。値はカーネル起動時の grid 寸法とテンプレート引数に使われ、32 × 128 または 64 × 64 の `block_scores_simt2_kernel` を起動します。後者は query 方向の grid を `(nq + 63) / 64`、前者は `(nq + 31) / 32` で計算します。grid の y が 65535 を超える場合は `false` を返し、呼び出し側の通常 scorer に fallback します。

どちらの形状でも続けて tail score カーネルを起動し、起動エラーがあれば stderr に `qsa_block_scores (simt): <CUDA error>` を出してプロセスを終了します。カーネル自身は両形状で同じ `block_scores_simt2_kernel` の実装を使います。ソースコメントは 64 × 64 を「measured slower」と記し、400K の測定を 3.00 対 2.82 ms としていますが、測定条件の記載がこの箇所にないため、一般的な性能値とは扱えません。

`docs/DETAILS.md` は親変数 `STRATA_SELECT_SIMT=1|2` を、通常 scorer と異なる合計順序を持つ明示選択肢として説明しています。この環境変数は親設定で SIMT=2 を使う際のタイル形状だけを切り替えます。文書には `STRATA_SIMT2_TILE` 固有の値や測定条件はありません。

## 根拠

- `src/kernels/cuda/qsa_select.cu:1824-1831,1861-1907`: CUDA/HIP 分岐、対象 GPU 判定、親変数の判定、タイル値の読み取りとカーネル dispatch。
- `src/kernels/cuda/qsa_select.cu:606-694`: 32 × 128 / 64 × 64 カーネルの template geometry と score 計算。
- `src/prefill/prefill.cpp:3146-3162`: prompt selection から `qsa_block_scores_tc` を呼び、失敗時に通常 scorer へ fallback する経路。
- `src/kernels/qsa_select_bench.cpp:98-100`: benchmark executable から scorer を呼ぶ経路。
- `src/core/layer.cpp:1176-1182`: decode QSA は `qsa_block_scores` と top-k を使い、この `_tc` dispatch を直接呼ばない。
- `docs/DETAILS.md:2253-2259`: 親変数 `STRATA_SELECT_SIMT` の説明。
