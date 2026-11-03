# `STRATA_SELECT_GEMM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL の indexed QSA prompt prefill で、pooled indexer key と複数 query の block score を計算する方法を選びます。GEMM 経路は oneMKL FP32 GEMM と `qsa_block_scores_reduce` を使い、通常経路は tensor-core score kernel が使えればそれを使い、使えない場合は warp kernel に進みます。対象名を読む実装は `sycl/src/prefill/prefill.cpp` のみです（3367 行）。

## 値と判定

値は `std::atoi` で整数に変換され、結果で分岐します。文字列全体の妥当性検査はありません。

| 環境値 | `atoi` の結果 | 選択モード |
|---|---:|---|
| unset | −1（既定値） | 自動選択。active block 数がしきい値以上で、GPU 世代が Battlemage のとき GEMM を選ぶ |
| `0`、空文字、整数に変換できない文字列 | 0 | 自動選択をせず、GEMM を選ばない |
| 正の整数（例: `1`, `2`） | 正数 | 自動選択条件によらず GEMM を要求する |
| 負の整数（例: `-1`, `-2`） | 負数 | unset と同じ自動選択 |

`atoi` のため、先頭の空白や符号を含む整数表記は変換され、整数の後ろに続く文字列は判定されません（例: `1xyz` は 1、`0xyz` は 0）。`true` など数値変換できない文字列は 0 です。範囲外の整数表記に対する結果はこの実装で検査・制限されません。自動選択のしきい値は別変数 `STRATA_SELECT_GEMM_MIN` で、unset 時は 2,048 blocks です。

根拠: `sycl/src/prefill/prefill.cpp:3367-3370`。

## 有効になる条件

- この読み取り箇所は SYCL の prefill 実装にあります。トップレベルでは `STRATA_ENABLE_SYCL` が有効なとき SYCL を別 backend として構成し、CUDA/HIP と同時には有効にできません。CUDA/HIP・Metal の実装がこの名前を読む箇所は見つかりません（`CMakeLists.txt:12-21`; 全参照検索結果は `sycl/src/prefill/prefill.cpp:3363-3369`）。
- 自動選択（unset または負数）には、対象バッチの `active` が `STRATA_SELECT_GEMM_MIN` 以上であることと、デバイス世代が `Battlemage` であることの両方が必要です。`active` は当該バッチ最後の query の `n_bid + 1` です（`sycl/src/prefill/prefill.cpp:3350-3355,3368-3370`）。
- 正数はこの自動選択条件を迂回しますが、実際の GEMM 実行には `STRATA_SELECT_OLD` が未設定、attention scratch が存在、index dimension が 128、index head 数が 4、計算された `sel_tile` が 256 以上であることも必要です。これらを満たさない場合は GEMM を実行せず通常の score 経路へ進みます（`sycl/src/prefill/prefill.cpp:3356-3357,3371-3375`）。
- `STRATA_SELECT_OLD` は値の内容ではなく設定の有無で判定され、空文字でも旧選択を有効にします。この場合 GEMM と tensor-core score の両方を通らず、warp kernel に進みます（`sycl/src/prefill/prefill.cpp:3356-3357,3395-3399`）。

## 実行時の詳細

`STRATA_SELECT_GEMM` と `STRATA_SELECT_GEMM_MIN` はどちらも関数内の `static const` で初回評価結果を保存します。実行中に環境を変えても同じプロセスでは再評価されません。読み取りはこの indexed QSA selection loop に初めて到達したときに行われます（`sycl/src/prefill/prefill.cpp:3350-3369`）。

GEMM 条件が成立すると、`active` blocks を `sel_tile` ごとに処理し、oneMKL GEMM の出力を `qsa_block_scores_reduce` に渡します。成功すればその結果で top-k selection を行います（`sycl/src/prefill/prefill.cpp:3371-3388,3400-3401`）。GEMM から例外が出た場合、stderr に `prefill: the GEMM block scores failed (%s); the warp kernel instead` を一度だけ出し、warp kernel に fallback します。GEMM を使わない場合も、旧選択が有効でなければ先に tensor-core score kernel を試し、それが使えない場合に warp kernel を呼びます（`sycl/src/prefill/prefill.cpp:3389-3399`）。この変数による独立した終了・エラー経路は確認できません。

## 根拠

- 候補名の唯一の参照と `atoi` による読み取り: `sycl/src/prefill/prefill.cpp:3367`。
- unset の既定値、関連しきい値、Battlemage 判定: `sycl/src/prefill/prefill.cpp:3368-3370`。
- GEMM 実行条件、処理、例外時ログと fallback: `sycl/src/prefill/prefill.cpp:3371-3399`。
- GEMM 後の top-k と通常経路: `sycl/src/prefill/prefill.cpp:3395-3401`。
- SYCL backend のビルド入口: `CMakeLists.txt:12-21`。
