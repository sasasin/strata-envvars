# `STRATA_SIMT2_TILE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の QSA block-score 計算で、SIMT2 カーネルのタイル形状を選ぶ補助スイッチ。`STRATA_SELECT_SIMT=2` が選ばれた場合にのみ参照され、既定の `32 x 128` の代わりに `64 x 64` のテンプレート構成を選ぶ。スコア計算とその後の tail-block 計算を変えるが、QSA の top-k や attention の選択条件を直接変える変数ではない（`engine/src/kernels/cuda/qsa_select.cu:2391-2419`）。

## 値と判定

読み取りは CUDA 側 `qsa_block_scores_tc` 内の関数ローカル `static const int` 初期化で、`std::getenv` の結果を `std::atoi` に渡す。環境変数が未設定なら `1`、設定されていれば `atoi` の結果となる。値が **ちょうど整数 2** のときだけ 64 x 64 タイルを使い、それ以外は 32 x 128 タイルを使う。文字列全体の検証はしないため、`atoi` が先頭から変換できる数値部分を使う（例: `2abc` や `2.0` は 2）。空文字、`true`、`0anything`、`1`、`3`、`-2` は 2 にならない。先頭空白や符号付きの `+2`、`02` は `atoi` で 2 になる。数値範囲の事前検査や clamp はない（同: `2401-2414`）。

| 条件 | unset | タイルが選ばれる値 | 既定のタイルになる値 |
|---|---|---|---|
| CUDA の対象経路で `STRATA_SELECT_SIMT=2` | 1（32 x 128） | `atoi` 結果が 2（例: `2`, `02`, `2abc`） | 空文字、`0`, `1`, `3`, `true`, `-2` など |
| その他の経路 | 読み取られない | 該当なし | 該当なし |

## 有効になる条件

- CUDA ビルドの `qsa_block_scores_tc` を実行すること。HIP 分岐にはこの変数の読み取りがなく、SYCL / Metal の別実装にも完全一致の参照はない（`engine/src/kernels/cuda/qsa_select.cu:2309-2313`, `2376-2423`）。
- 対象 GPU の compute capability が通常 `sm_80` 未満であること。`sm_80` 以上では SIMT 分岐に入らず、別の tensor-core scorer を使うため、この変数は参照されない（`engine/src/kernels/cuda/qsa_select.cu:2377-2423`）。`STRATA_QSA_WARP=1` または `select` が compute capability を 7 として扱わせる場合は、その SIMT 分岐に入る場合がある（同: `2377-2399`）。
- 同じ経路で `STRATA_SELECT_SIMT` の先頭文字が `'2'` であること。未設定または先頭が `'1'` / `'2'` 以外なら SIMT2 は選ばれず、`STRATA_SIMT2_TILE` も読まれない（同: `2391-2404`）。
- prompt の block-score 呼び出しが `qsa_block_scores_tc` に到達すること。`STRATA_SELECT_OLD` が設定されると caller がこの scorer を飛ばし、通常の `qsa_block_scores` に進む。二段階 scorer が選択されるケースでもこの読み取り箇所を通らない（`engine/src/prefill/prefill.cpp:5377-5392`, `9450-9456`）。
- decode の `qsa_block_scores` 経路は別関数で、`STRATA_SIMT2_TILE` を参照しない。QSA の fast-select 経路からその関数を直接呼んでいる（`engine/src/core/layer.cpp:1277-1283`）。

## 実行時の詳細

通常の prompt scorer は、`qsa_block_scores_tc` が利用可能ならそれを使い、利用できないときは caller が `qsa_block_scores` にフォールバックする。CUDA の compute capability が 8 未満で `STRATA_SELECT_SIMT` が `2` の場合、この変数の `static` 初期化が初めて通った時点で値を読み、以後そのプロセスでは同じタイル選択を使う。起動後に環境を変更しても、初回初期化後は反映されない。`tile == 2` なら grid を `(ceil(reach/64), ceil(nq/64))` として `block_scores_simt2_kernel<64, 64>` を起動し、それ以外なら `(ceil(reach/128), ceil(nq/32))` として `<32, 128>` を起動する。どちらも後続で tail kernel を実行する（`engine/src/kernels/cuda/qsa_select.cu:2401-2419`）。

この選択は prompt の block scores の計算タイルを変える。上位候補の抽出は caller が続けて `qsa_block_topk` を呼び、選ばれた ID を後続の処理へ渡す（`engine/src/prefill/prefill.cpp:5387-5393`, `9451-9457`）。`grid.y > 65535` のとき scorer は `false` を返し、caller が通常 scorer にフォールバックする（`engine/src/kernels/cuda/qsa_select.cu:2404-2414`; `engine/src/prefill/prefill.cpp:5387-5392`）。

## ログと測定値

この変数の値や選ばれたタイルを知らせる専用ログはない。kernel 起動後の `cudaGetLastError` が失敗した場合は `qsa_block_scores (simt): %s` を stderr に出して `exit(1)` する（`engine/src/kernels/cuda/qsa_select.cu:2415-2419`）。ソースコメントには `STRATA_SIMT2_TILE=2` が「measured slower: 400K 3.00 vs 2.82 ms」とあるが、GPU、OS、backend の詳細や測定条件が記されていないため、再現可能な測定値としては扱わない（同: `2402-2403`）。`docs/DETAILS.md` にこの補助変数の説明は見当たらず、関連する `STRATA_SELECT_SIMT` の資料記述とは分けて扱った。

## 根拠

- `engine/src/kernels/cuda/qsa_select.cu:2391-2419` — CUDA の `sm_<80` SIMT2 選択、環境値の読み取り、2 種類の tile launch、grid fallback と起動失敗処理。
- `engine/src/prefill/prefill.cpp:5377-5393`, `9450-9457` — prompt scorer の呼び出し、`STRATA_SELECT_OLD` による迂回と通常 scorer への fallback。
- `engine/src/core/layer.cpp:1277-1283` — decode の QSA block-score 経路。
