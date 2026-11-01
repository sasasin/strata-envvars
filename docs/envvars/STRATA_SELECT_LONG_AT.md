# `STRATA_SELECT_LONG_AT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA verifier の QSA 選択処理で、通常版と long-context 版の window graph を切り替える context cell 数の閾値です。この変数だけでは long 版を有効にしません。`STRATA_SELECT_LONG=1` が有効で、long 版用 scratch を提供するビルドのときに使われます。閾値以上の window は long 版を選び、それ未満は通常版を選びます。

## 値と判定

| 環境値 | 判定結果 |
|---|---|
| 未設定 | 65,536 cells |
| 空文字 | 65,536 cells |
| `atoll` が数値として変換できる prefix を含む文字列 | `std::atoll` が読み取る符号付き整数。たとえば `32768tail` は 32,768、`-1` は -1 |
| 数字で始まらない非空文字列 | `atoll` の変換結果 0 |
| `0` または `-0` | 0。通常の有効 window では `pos0 + T >= 0` なので常に long 版の候補 |

全体文字列の検証、errno / 範囲エラー確認、clamp はありません。先頭空白や符号は `atoll` の変換規則に従い、数値の後ろにある文字列は判定されません。表現可能範囲を超えた値についても Strata 側の明示的な検証はありません。閾値が到達可能な context より大きければ long 版の条件を満たしません。

CLI 引数や設定ファイルによる上書きは、この変数の読み取り経路にはありません。別の環境変数 `STRATA_SELECT_LONG` が long 版を有効にする前提条件です。

根拠: `src/core/verify.cpp:194-200,3013-3018,3076-3078`。

## 有効になる条件

- `STRATA_SELECT_LONG` の値の先頭文字が `1` であること。`STRATA_SELECT_LONG` が未設定、空文字、または先頭文字が `1` 以外なら long 版を選びません（`src/core/verify.cpp:181-193`）。
- `strata::kernels::qsa_topk_multi_scratch_ints(1) > 0` であること。同関数が正の scratch サイズを返すのは HIP でなく `STRATA_EXPERIMENTAL_SM60` が定義された CUDA build です。条件を満たさず `STRATA_SELECT_LONG=1` が指定された場合、stderr に `strata verify: STRATA_SELECT_LONG=1 needs the CUDA build with STRATA_EXPERIMENTAL_SM60; ignored` と出し、long 版を無効にします（`src/core/verify.cpp:181-193`; `src/kernels/cuda/qsa_select.cu:3075-3084`）。
- 対象は通常の verifier window と pipelined window です。batch-row graph は `sel_long_ = 0` に固定され、この閾値では切り替わりません（`src/core/verify.cpp:3744-3756`）。
- 閾値判定は `pos0 + T >= select_long_at()` です。`T` は window の行数、`pos0` は開始位置です。判定を満たした場合も、各 long API が必ず専用 kernel を起動するとは限りません。CUDA long top-k は `STRATA_TOPK_MULTI`、query 数、shape、scratch などに応じて通常 top-k に fallback し、long score も `STRATA_SCORES_DX` 等の条件に応じて通常 scorer に fallback します（`src/kernels/cuda/qsa_select.cu:3086-3113`; `include/strata/kernels/qsa_select.hpp:81-95`）。

## 実行時の詳細

`select_long_at()` は関数内の `static const int64_t` に値を保持します。`STRATA_SELECT_LONG` が有効な経路で最初に閾値判定を行った時に読み取り、その後プロセス内で環境を変更しても再評価しません。`STRATA_SELECT_LONG` が無効なら `&&` の短絡評価により閾値 helper は呼ばれず、この変数も読み取られません（`src/core/verify.cpp:194-200,3016-3017,3076-3078,4877-4878`）。

通常 window では `prelaunch()` と `run()` が同じ `pos0 + T` 条件で graph variant を決めます。pipelined windows では `capture_all()` が long 機能有効時に両 variant を capture し、`pl_launch()` が window ごとに閾値を判定して graph を選びます（`src/core/verify.cpp:3013-3034,3070-3084,4815-4823,4870-4902`）。long variant の QSA 選択処理は `qsa_block_scores_long()` と `qsa_block_topk_long()` を呼び、条件を満たさない場合はそれぞれ通常 scorer / top-k に fallback します（`src/core/verify.cpp:1775-1786`）。

この閾値自体についてのログや警告はありません。unsupported build に対する警告は `STRATA_SELECT_LONG` 側が出します。window graph の capture / launch に失敗した場合は verifier のエラー経路（例: `verify: begin capture failed`, `verify: launch: ...`）になりますが、これは閾値固有の失敗ではありません（`src/core/verify.cpp:2590-2603,3032-3035`）。

## 根拠

- 読み取り、既定値、変換、cache: `src/core/verify.cpp:194-200`
- long 機能の opt-in と build 条件、警告: `src/core/verify.cpp:176-193`; `src/kernels/cuda/qsa_select.cu:3075-3084`
- 通常 window / prelaunch における閾値比較: `src/core/verify.cpp:3013-3018,3070-3084`
- pipelined window の両 graph capture と launch 時の選択: `src/core/verify.cpp:4815-4823,4870-4902`
- batch-row graph の固定動作: `src/core/verify.cpp:3744-3756`
- long API の個別 fallback: `src/kernels/cuda/qsa_select.cu:3086-3113`; `include/strata/kernels/qsa_select.hpp:81-95`
- Strata の説明資料: `docs/OLDER_GPUS.md:178-184`。同資料も `STRATA_SELECT_LONG=1` の decode window について default 65,536 cells と記載しています。
