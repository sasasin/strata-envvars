# `STRATA_SPEC_PROB_GATE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

`STRATA_SPEC_PROB=1` による確率的ドラフト生成で、`--spec-min-p` が見るドラフト確率を選ぶ。既定では実際に抽選された候補の確率を使い、値を `top` にするとドラフト分布の最大確率を使う。これはドラフトを追加するかどうかのしきい値判定を変える設定で、検証側の受理・棄却計算そのものは変えない。

## 値と判定

| 環境変数の状態 | 判定 | `--spec-min-p` に渡す値 |
|---|---|---|
| 未設定 | 既定 | 抽選された候補の `q` 確率 |
| 空文字 | 既定と同じ | 抽選された候補の `q` 確率 |
| 文字列が厳密に `top` | top モード | `q` 分布内の最大確率 |
| その他の文字列（`TOP`、`1`、`0` を含む） | 既定と同じ | 抽選された候補の `q` 確率 |

文字列全体を `strcmp` で比較するため、大文字小文字を区別し、前後の空白なども許容しない。数値変換は行わない。

## 有効になる条件

- `STRATA_SPEC_PROB` が設定され、空文字でも `0` でもないこと。確率的受理モードはこの別の環境変数で有効になる。この変数だけではモードを有効にしない。
- MTP ドラフトを使い、サンプリング要求であること（greedy ではなく、temperature が 0 より大きいこと）。さらに `temperature >= STRATA_SPEC_MIN_TEMP` が必要。
- `--spec-min-p` が 0 より大きいこと。このしきい値が 0 の場合、出力されるドラフト確率の差はドラフト長判定に使われない。
- 確率的ドラフトに分布リスト `q` がある MTP ドラフトが対象。prompt lookup や suffix draft など分布を持たない候補にはこの確率の選択は適用されない。
- 確認したドラフトサンプラーの実装は `src/kernels/cuda/sampler.cu` にある。`src/kernels` 内に同名関数の別 backend 実装は見つからなかった。

`--spec-min-p` は各ドラフト候補の確率が指定値以上の間だけ次の候補を検証窓に追加する。したがって `top` は抽選結果に左右されず、ドラフト分布の自信度で窓を伸ばす判定になる。

## 実行時の詳細

`spec_gate_pick()` は関数内の `static const bool` を初回評価時に設定する。プロセス中に環境変数を変更しても再読込しない。呼び出しは MTP の確率的ドラフトサンプラーを組み立てる箇所にあり、その値が GPU サンプラーへ渡される。

GPU 側は draft head の分布 `q` から候補を抽選する。通常モードでは抽選された要素 `q[pi]` を出力確率にし、`top` モードでは先頭要素 `q[0]`（分布の最大確率）を出力確率にする。その確率は `--spec-min-p` と比較され、しきい値未満でドラフト列を止めるために使われる。検証器の確率的受理は別に `p(d)` と `q(d)` から判定する。

初期化・設定に失敗した場合、MTP はエラーを返す（例: ドラフト分布バッファ不足時は `mtp: the draft distributions' buffer does not fit`）。確率的ドラフト設定の有効化時には stderr に `strata mtp: probabilistic draft acceptance on (STRATA_SPEC_PROB): ...` を出す。`STRATA_SPEC_PROB_GATE` 自身についてのログ出力はない。

## 根拠

- `include/strata/core/spec_prob.hpp:42-51` — `top` との完全一致判定、既定値、および関数内 static による初回評価。
- `include/strata/core/coupled_draft.hpp:65-79` — `STRATA_SPEC_PROB` の設定有無・空文字・`0` の判定と、共通セットアップ条件。
- `src/core/mtp.cpp:525-545,566-579` — 確率的ドラフト用バッファ確保、stderr の有効化ログ、sampling / temperature 条件。
- `src/core/mtp.cpp:999-1008` — `spec_gate_pick()` をドラフトサンプラーへ渡す箇所。
- `src/kernels/cuda/sampler.cu:937-982` — `gate_pick` が候補自身の確率か分布先頭の確率かを選ぶ処理。
- `src/program/generate.cpp:11959-11963,12120-12121` — `--spec-min-p` とドラフト確率を比較し、後続ドラフト数を決める経路。
- `src/core/verify.cpp:2309-2336` — sampled request で `q` リストがある場合の検証器呼び出し。確率的受理がこの env のゲート選択とは別であることの確認。
- `docs/DETAILS.md:1260` — `STRATA_SPEC_PROB` と通常の確率的受理モードの説明。`STRATA_SPEC_PROB_GATE` 自体の説明は見当たらない。
