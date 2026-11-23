# `FNX_PF_PEER`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

AMD/HIP 版 split engine の prompt chunk sums（prompt 処理中のカード間の和）で、受信側カードの fine-grained device memory を使う経路を選びます。有効時は prompt sums のリング用受信バッファと flags を peer device memory に割り当てます。また、小さい chunk では別の all-to-all push とカードごとの加算経路を使います。無効時は prompt sums の交換バッファを host memory に置きます。設定は decode sums や attention merge を直接選ぶものではありません（`engine/src/split/src/engine.cu:144-146`, `engine/src/split/src/prefill.cu:981-1009`, `engine/src/split/src/prefill.cu:744-755`）。

この設定が評価されるのは `FNX_HIP` ビルドで、peer push が使え、かつ prompt sums に RCCL が使われない場合だけです。NVIDIA/CUDA build には読み取り箇所がなく、値は無視されます（`engine/src/split/src/engine.cu:125-147`; build 定義: `engine/src/split/CMakeLists.txt:121-140`）。

## 値と判定

`env_int("FNX_PF_PEER", 1) != 0` で読みます。`env_int` は未設定なら既定値を返し、設定されていれば符号付き base-10 整数を `long long` の範囲内で文字列全体から parse します。先頭・末尾の空白、空文字、数字以外の接尾辞、整数範囲外は受け付けず、例外になります。0 以外は有効で、負数も有効です（`engine/src/split/src/engine.cu:145`, `engine/src/split/src/env.hpp:15-21`, `engine/src/split/src/env.hpp:33-40`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| HIP build、peer push on、RCCL off | `1`（有効） | 整数の 0 以外。例: `1`, `-1`, `+2` | 整数 `0`。例: `0`, `00` |
| 同条件で parse が行われる場合 | — | — | 空文字、`0anything`、`true`、` 1`、`1 `、`9223372036854775808` などは不正値。`<名前>: '<値>' is not a whole number` の例外 |
| 非 HIP build、peer push off、または RCCL on | 値を参照しない | 値を参照しない | 値を参照しない |

有効値は CLI 引数や設定ファイルで上書きされません。peer push の可否は別の `FNX_PEER` と起動時 probe で決まり、RCCL が使われる場合は `FNX_PF_PEER` の値より RCCL 経路が優先されます（`engine/src/split/src/engine.cu:125-146`, `engine/src/split/src/hip/peer_policy.hpp:26-40`, `engine/src/split/src/hip/rccl_dl.hpp:76-90`）。

## 有効になる条件

- HIP build の `strata-split-N`（CMake 上の N は 2、3、4）であること。CUDA build では対象コードが `#if FNX_HIP` 内にないため読み取られません（`engine/src/split/CMakeLists.txt:116-140`, `engine/src/split/src/engine.cu:125-147`）。
- `FNX_PEER` が `0` でなく、起動時の peer probe が成功して `peer_on` になること。peer push が off または probe に失敗した場合は host exchange となり、`FNX_PF_PEER` は短絡評価で読み取られません。probe 失敗時は `The cards cannot push into each other's memory here (...): using the host exchange for this run.` を stderr に出します（`engine/src/split/src/hip/peer_policy.hpp:26-40`, `engine/src/split/src/engine.cu:129-146`）。
- RCCL が prompt sums に使われていないこと。現 commit の `RCCL_DEFAULT_ON` は `true` で、peer push が有効ならまず RCCL を試します。RCCL が開けた場合 `rccl_on_` が true になり、この変数は評価されず prompt sums は RCCL 経路になります。`FNX_PF_RCCL=0` で RCCL を明示的に止めるか、RCCL の初期化が失敗して `rccl_on_` が false になった場合に `FNX_PF_PEER` が評価されます（`engine/src/split/src/hip/rccl_dl.hpp:21-22`, `engine/src/split/src/hip/rccl_dl.hpp:76-90`, `engine/src/split/src/engine.cu:134-146`）。
- 値が有効なら、prompt 用の `ring_ce` 受信領域と flags を fine-grained device memory に割り当てます。小 chunk の all-to-all 領域は別変数 `FNX_PF_A2A_ROWS` で上限を決め、既定は 256 行、`0` 以下ならその領域を作りません（`engine/src/split/src/prefill.cu:981-1009`）。

## 実行時の詳細

`Engine` の構築中、`FNX_PEER` の判定と RCCL の選択の後に一度評価して `pf_peer_` に保存します。環境変数をリクエストごとに読む処理や、この値の static cache はありません。構築後の環境変更は既存 Engine の経路に反映されません（`engine/src/split/src/engine.cu:34`, `engine/src/split/src/engine.cu:125-147`; 使用先: `engine/src/split/src/prefill.cu:981-1009`）。

`pf_peer_` が true の場合、prompt ring の受信 half buffers、aggregate buffers と flags を peer memory に割り当てます。さらに `FNX_PF_A2A_ROWS` が正なら mailbox と flags を作り、chunk の行数 `C` が上限以下で `own_out` でないとき `k_pfa_push` / `k_pfa_sum` により他カードの mailbox へ送って各カード側で加算します。それ以外の chunk は ring 経路に進みます。小 chunk の加算はコードコメント上 ring と bit-identical とされています（`engine/src/split/src/prefill.cu:744-755`, `engine/src/split/src/prefill.cu:981-1009`, `engine/src/split/src/pf_common.cuh:151-165`）。

有効値の parse に失敗した場合、または fine-grained device memory の割り当てに失敗した場合は例外になります。sfnx は engine 構築の例外を `ERR ...` と stderr の `sfnx: failed: ...` に出して終了コード 1 で終了します（割り当てエラー: `engine/src/split/src/prefill.cu:77-85`; engine 側の割り当て: `engine/src/split/src/engine.cu:148-153`; 例外処理: `engine/src/split/tools/sfnx.cpp:1097-1103`, `engine/src/split/tools/sfnx.cpp:1123-1135`）。

## ログと測定値

有効時は stderr に `fnx: peer push: the prompt chunk sums are pushed into the peers' device memory` を出します（`engine/src/split/src/engine.cu:145-146`）。既定値のままでもこのログは出ますが、peer push が off の場合や RCCL が使われる場合はこの変数の有効ログは出ません。対象変数固有の測定値は、調査対象ソース・設計資料では確認できません。

`docs/SPLIT_ENGINE.md:77-81` は `FNX_PF_RCCL=1` を「off by default」と記しています。一方、調査対象 commit の `engine/src/split/src/hip/rccl_dl.hpp:21-22` では `RCCL_DEFAULT_ON = true` で、`FNX_PF_RCCL` が unset の場合 `rccl_decide` はこれを既定値として使います（同 `:76-90`）。従って資料の RCCL 既定値の記述はこの commit のコードと一致しません。ここでは実際の経路条件をコードに基づいて記載しています。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:282`。
- 対象変数の唯一の実読み取り、適用条件、設定ログ: `engine/src/split/src/engine.cu:125-146`。
- 整数 parse の規則: `engine/src/split/src/env.hpp:15-21`, `engine/src/split/src/env.hpp:33-40`。
- peer push 判定: `engine/src/split/src/hip/peer_policy.hpp:26-40`。
- RCCL の優先と既定: `engine/src/split/src/hip/rccl_dl.hpp:21-22`, `engine/src/split/src/hip/rccl_dl.hpp:76-90`。
- peer memory と小 chunk 経路: `engine/src/split/src/prefill.cu:744-755`, `engine/src/split/src/prefill.cu:981-1009`, `engine/src/split/src/pf_common.cuh:151-165`。
- 設計資料との照合: `docs/SPLIT_ENGINE.md:77-81`。
