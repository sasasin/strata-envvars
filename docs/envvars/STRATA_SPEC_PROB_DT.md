# `STRATA_SPEC_PROB_DT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA 実装で `STRATA_SPEC_PROB` による確率的 MTP ドラフトを使うとき、ドラフト分布 `q` を作る温度をリクエスト温度の倍率で調整します。ターゲット側の分布 `p` やリクエスト設定そのものは変更しません。倍率が変わると `q` と、ドラフトが検証で受け入れられる確率が変わります。

## 値と判定

`std::atof` で値を変換し、結果 `v` が `v > 0.0f` の場合だけ採用します。それ以外は倍率 `1.0f` です。文字列全体の妥当性は確認しないため、数値の後ろに文字があっても `atof` が読み取った数値が使われます。

| 環境変数の値 | 結果 |
|---|---|
| 未設定 | `1.0` |
| 空文字、数値に変換できない文字列 | `atof` は `0` となり、`1.0` |
| `0`、`-2`、`nan` など、変換結果が正でない値 | `1.0` |
| `0.5`、`2` | それぞれ `0.5`、`2.0` |
| `2abc` | `atof` が先頭の数値を変換するため `2.0` |

設定値の有無ではなく変換後の正値かどうかで判定します。CLI 引数や設定ファイルによるこの倍率の上書きは見つかりません。

## 有効になる条件

- `STRATA_SPEC_PROB` が設定され、空文字でなく、文字列全体が `0` と異なること。これは確率的ドラフト用のバッファと処理を有効にします。`STRATA_SPEC_PROB_DT` 単独では確率的ドラフトを有効化しません。
- MTP ドラフトが使われ、当該リクエストが greedy でなく、温度が正で、`STRATA_SPEC_MIN_TEMP` の閾値以上であること。閾値の既定値は `0` です。この条件を満たさないリクエストでは該当する確率的ドラフト kernel が呼ばれず、この倍率も使われません。
- 調査した確率的ドラフト kernel は CUDA 実装です。`sycl/` の移植版には `STRATA_SPEC_PROB` / `STRATA_SPEC_PROB_DT` や確率的 `q` リスト処理がなく、移植版の MTP ドラフトはこの設定を使いません。

`STRATA_SPEC_PROB` は空白を除去したり前方一致で判定したりせず、`strcmp(e, "0") != 0` で判定されます。したがって `0anything` も確率的ドラフトを有効にします。

## 実行時の詳細

`spec_draft_temp_scale()` は倍率を `static const` に保存します。最初にこの関数が呼ばれた時点で環境変数を読み、その後プロセス内で環境を変更しても再評価しません。関数は MTP のドラフト最終段で `spec_draft_sample()` を呼ぶときにだけ評価されます。

CUDA kernel はドラフト sampler パラメータの `temperature` に倍率を掛け、ドラフト側の確率分布 `q` を作ります。確率的検証はその `q` とターゲット側 `p` を使い、ドラフトを確率 `min(1, p(d)/q(d))` で受け入れ、拒否時には残余分布から置換 token を選びます。したがって倍率はドラフト分布と受け入れやすさを変えますが、検証側の `p` は変更しません。

`docs/DETAILS.md` は `STRATA_SPEC_PROB` の確率的ドラフトと検証の概要・測定を説明していますが、`STRATA_SPEC_PROB_DT` の説明や倍率別の測定値は記載していません。本調査ではこの変数の性能効果を測定していません。

## 根拠

- `include/strata/core/spec_prob.hpp:53-61` — `std::atof`、正値条件、既定倍率、static cache。
- `include/strata/core/coupled_draft.hpp:67-79` — `STRATA_SPEC_PROB` の判定と、確率的ドラフトが coupled-draft 用セットアップを使う関係。
- `src/core/mtp.cpp:541-545,565-573,576-580,682-683` — `STRATA_SPEC_PROB` 時の `q` バッファ確保、起動ログ、リクエストごとの sampled 温度条件、セットアップ。
- `src/core/mtp.cpp:999-1009` — 確率的ドラフト時に `spec_draft_temp_scale()` を CUDA kernel に渡す箇所。
- `src/kernels/cuda/sampler.cu:937-950,963-980,1372-1390` — ドラフト kernel が温度倍率を適用し、分布と token を作る箇所。
- `src/program/generate.cpp:12046-12049` — MTP 由来の `q` リストを verifier に渡す条件。suffix / lookup ドラフトは別扱い。
- `src/core/verify.cpp:2309-2336` — `q` リストがある sampled window で確率的検証を起動し、起動できない場合は通常 sampler に戻る箇所。
- `sycl/include/strata/core/coupled_draft.hpp:1-4,55-65`、`sycl/src/core/mtp.cpp:1-7,603-604,782,1132`、`sycl/src/kernels/cuda/sampler.dp.cpp:1173-1176,1699-1705` — SYCL 移植版は `STRATA_SPEC_COUPLED` のみを使うこと。
- `docs/DETAILS.md:1260` — 確率的ドラフトの全体説明。`STRATA_SPEC_PROB_DT` 固有の記述はない。
