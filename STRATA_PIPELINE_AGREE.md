# `STRATA_PIPELINE_AGREE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows` の speculative decode で、前の window を丸ごと受理した後に動く forced MTP chain の確率評価を選びます。既定では chain の出力確率を使い、chain の token が先行 window の draft と食い違った場合に次の window の推定受理確率を 0 にします。無効にすると先行 window の draft 確率を使い、食い違いによる 0 化をしません。

これは B window を投機実行するかどうかの `p_on` 推定に関わります。verifier が token を受理・拒否する規則や sampler の token 選択を直接変更するコードではありません。実装コメントは pipeline の誤予測を rollback する設計を説明しています（`src/program/generate.cpp:10415-10422`）。

## 値と判定

対象値は `pipe_dbg_env("STRATA_PIPELINE_AGREE")` から取得し、`std::atoi(v) != 0` で判定します。変数を取得できない場合は `true`（有効）が既定です。

| 条件 | 判定 |
|---|---|
| `STRATA_PIPELINE_DEBUG` が無効で helper が `nullptr` を返す、または `STRATA_PIPELINE_AGREE` が未設定 | 有効（既定） |
| `STRATA_PIPELINE_DEBUG` 有効、値が `atoi` で 0 になる | 無効。例: `0`, `00`, `true`, 空文字 |
| `STRATA_PIPELINE_DEBUG` 有効、値が `atoi` で 0 以外になる | 有効。例: `1`, `-1`, ` 1tail` |

`atoi` は文字列全体の妥当性を検査しません。先頭の空白と符号を許し、数字列の後ろは無視します。数字で始まらない文字列（`true` など）や空文字は 0 です。`STRATA_PIPELINE_DEBUG` 自体は unset・空文字・先頭文字 `0` なら無効、それ以外の設定値なら有効です。したがって `STRATA_PIPELINE_DEBUG=0` のときは `STRATA_PIPELINE_AGREE=0` を含む個別値は読まれず、AGREE は既定有効になります。

## 有効になる条件

- `--pipeline-windows` のパイプライン実行分岐が実際に動く必要があります。CUDA/HIP の `src/program/generate.cpp` では `pipe && pl_pw >= 2 && pl_snap2[0] != nullptr` などを満たす経路です（`src/program/generate.cpp:10415-10439`）。起動時のオプション検査では `--serve`、layer split、MTP drafter、`--spec >= 2` などが要求され、非対応条件では pipeline が無効化されます（`src/program/generate.cpp:3370-3385`）。
- この変数の計算差が使われるのは `chain_kind == 1`、つまり先行 window の on-path verdict 後、A の drafts を teacher-force した chain の B window を組み立てる場合だけです。fresh chain (`chain_kind == 2`) は `A.prob` を使う別経路です（`src/program/generate.cpp:11711-11719,11557-11571`）。
- `STRATA_PIPELINE_DEBUG` が無効なら個別変数はすべて helper に隠されます。debug gate は初回呼び出し時に `static` 値として決まり、その後の環境変更は反映されません。

## 実行時の詳細

両方の backend 実装で `pl_agree` は function-local `static const bool` です。`STRATA_PIPELINE_DEBUG` の gate が有効な状態で pipeline loop が初期化されると、AGREE の値を一度 `atoi` で判定し、そのプロセスの後続 window では同じ結果を使います。

`chain_kind == 1` では、A の draft と forced chain の各 token を比較しながら確率積 `pa` を作ります。有効時は chain 確率 `op[i]` を掛け、いずれかの token が不一致なら `pa=0` として `pl_disagree` を加算します。無効時は A の draft 確率 `A.prob[i]` を掛け、不一致によるゼロ化は行いません。その後 `make_b()` が `B.p_on = pa * op[base]` を設定します。この値は stage 0 での B の投機 launch / pre-stage 判定と、pipeline calibration に使われます。後続 stage は `st > 0` の条件で theta 閾値なしに launch できるため、`p_on` が全 stage の起動可否を一律に決めるわけではありません（`src/program/generate.cpp:11298-11314,11557-11585,11608-11610,11685-11685`）。

`dec_timing` が有効な場合、終了時の stderr 統計に `forced-chain disagreements` として `pl_disagree` が出ます。有効設定でも不一致がなければ加算されず、AGREE 無効時は常にこのカウンターを増やしません（`src/program/generate.cpp:11791-11800`）。

## 根拠

- `src/program/generate.cpp:251-257`: debug gate の有無と `pipe_dbg_env()` の動作。
- `src/program/generate.cpp:11444-11451`: AGREE の取得、既定値、`atoi` 判定。
- `src/program/generate.cpp:11557-11585`: forced chain の確率積、token 不一致処理、B の組み立て。
- `src/program/generate.cpp:11608-11610`: `B.p_on` による投機 launch 条件。
- `sycl/src/program/generate.cpp:293-298,10763-10770,10871-10899`: SYCL 実装にも同じ gate、値判定、確率処理がある。
- `docs/DETAILS.md:173-177` は `--pipeline-windows 2` と適応処理の相互作用を説明しますが、`STRATA_PIPELINE_AGREE` 固有の説明や測定値は見つかりませんでした。
