# `STRATA_ROUTE_RESIDENT_MTP`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

`strata serve` で MTP drafter を使う場合に、draft 層の top-10 expert routing に residency bias を適用します。検証側の最終層にある expert residency row を表として使い、top-10 の指定順位にある非 resident expert を、logit が一定 margin 以内の resident expert に置き換えます。これは実験的な設定で、draft token を変えることがあります。生成 token は引き続き verifier が決めます。

## 値と判定

| 環境変数の状態 | 有効判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（`atoi("")` は 0） |
| `0`、`00`、`-0`、数字以外で始まる文字列 | 無効（`atoi` の結果が 0） |
| `1`、`2`、`-1`、`1tail`、` 1` など `atoi` の結果が非 0 になる文字列 | 有効候補 |

値全体を文字列比較せず、`std::atoi` の結果が非 0 かどうかで判定します。そのため数値の後ろに文字があっても先頭の数値部分で判定されます。値が非 0 でも、後述の条件を満たさない場合は効果がありません。

有効化には別途 `STRATA_ROUTE_RESIDENT` が設定されている必要があります。この変数の値は `std::atof` で margin として読み、結果が `0.0` 以下なら bias を設定しません。順位範囲は `STRATA_ROUTE_RESIDENT_RANKS` があれば `sscanf("%d-%d")` で読み、なければ 6–9 です。変換結果や順位の範囲は検証されません。kernel は `lo` から `hi` までの順位を調べ、`hi` は最大 9 に制限しますが、負の `lo` を下限補正しません。指定する場合は 0–9 の範囲にしてください。

根拠: `src/program/generate.cpp:7443-7454`。

## 有効になる条件

次の条件が揃う必要があります。

- `strata serve` の経路である。
- `--mtp` が指定され、`use_mtp` が true である。
- layer-split stage がなく (`stages.empty()`)、`thits.d_res` が存在する。
- `STRATA_ROUTE_RESIDENT` が設定されており、その `atof` 結果が正である。
- `STRATA_ROUTE_RESIDENT_MTP` の `atoi` 結果が非 0 である。
- draft 層の expert 数が 512、top-k が 10 である。

`STRATA_ROUTE_RESIDENT_MTP` の読み取り・設定箇所は serve 初期化部だけです。通常の `strata generate` の MTP 初期化経路にはこの設定処理がありません。CUDA の MTP 実装であり、HIP/SYCL の同等実装はこの調査対象ソースでは確認できませんでした。

## 実行時の詳細

serve 初期化時に `STRATA_ROUTE_RESIDENT_MTP` と `STRATA_ROUTE_RESIDENT` を読みます。`STRATA_ROUTE_RESIDENT_RANKS` は任意で、未設定なら `lo=6, hi=9` のままです。正の margin の場合、`thits.d_res` の最終モデル層の row（`(g.n_layers - 1) * g.n_expert` の位置）を MTP drafter に渡し、有効化ログを stderr に出します。ログ文は `strata generate: STRATA_ROUTE_RESIDENT_MTP: the MTP draft's router is biased toward layer ...` です。

MTP の MoE routing 後、512 experts / top-10 のときだけ `native_route_resident()` が呼ばれます。top-10 中の非 resident expert を `lo` から `hi` まで順位順に調べ、未選択の resident expert のうち最大 logit のものへ置換します。置換候補との logit 差が `margin` 以下のときだけ置換し、置換があった token の routing weights は選ばれた expert の logits から softmax で再計算します。置換しなかった token の weights は変更しません。CUDA kernel 起動時に例外が起きた場合は `mtp route-resident: ...` をエラー文字列に設定し、draft 処理は失敗します。

MTP の `draft()` / `draft_first()` が作る予測 token は変わり得ます。一方、serve の各 verify window では verifier が採用 token を決める構造です。したがってこの設定は verifier の router を変更するものではありません。

## 根拠

- `src/program/generate.cpp:6928-6940` — serve 経路と `--mtp` 判定。
- `src/program/generate.cpp:7440-7455` — 環境変数、適用条件、margin/rank の設定、ログ。
- `include/strata/core/mtp.hpp:50-55,262-264` — MTP drafter への residency row と設定値の保持。
- `src/core/mtp.cpp:915-930` — MTP router 後の適用条件と呼び出し。
- `src/kernels/cuda/native_router.cu:180-184,192-245,248-255` — expert 置換、margin 判定、weights 再計算、kernel 呼び出し。
- `docs/DETAILS.md:1661-1663` — `STRATA_ROUTE_RESIDENT_MTP` は opt-in で、`STRATA_ROUTE_RESIDENT` より速くないと記載されている。これは資料中の主張であり、この調査で性能測定はしていない。
