# `STRATA_SPLIT_HEADROOM_TOL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

複数 GPU の `--layer-split auto` が配置候補を選ぶとき、最速とみなす候補からどれだけ遅い候補まで比較対象に含めるかを割合で指定する。許容幅内の候補から、各 GPU の層と全 expert に必要な領域を差し引いた後の最小空き VRAM が最大になる配置を選ぶ。したがって変更するのは自動分割位置であり、予測時間が許容幅を超える候補は選ばれない（`engine/sycl/src/program/generate.cpp:4025-4052, 4152-4171`、`engine/include/strata/program/split_rules.hpp:110-138, 187-199`）。

## 値と判定

`std::getenv` が null の場合だけ `0.002`（0.2%）を使い、設定されていれば `std::atof` で `double` に変換する。空文字や数値に変換できない文字列も「未設定」扱いには戻らず、`atof` の変換結果 `0` になる。全体の厳密な数値検証や範囲制限はなく、先頭の数値部分が変換され、後続の文字は判定に使われない（`engine/sycl/src/program/generate.cpp:4036-4037`）。

| 環境値 | `headroom_tol` | 選択関数での扱い |
|---|---:|---|
| 未設定 | `0.002` | 最速候補の予測時間から最大0.2%遅い候補まで含める |
| `0.01` | `0.01` | 最大1%遅い候補まで含める |
| 空文字、`abc`、`true`、`0anything`、`0`、負数 | `0` または負数 | `tol > 0` が偽となり、最速候補と予測時間が同じ候補だけが対象 |
| `0.2junk` | `0.2` | 先頭の数値部分が変換され、最大20%遅い候補まで含める |

候補時間の上限は `best.ms + best.ms * (tol > 0.0 ? tol : 0.0)` で、上限と同じ時間の候補も含む。許容幅が正でない場合も headroom 選択自体は止まらず、最速候補と同時間の候補間で余裕量を比べる（`engine/include/strata/program/split_rules.hpp:118-138`）。

## 有効になる条件

- 値が選択に使われるのは SYCL engine の自動 layer-split 探索（`multi_gpu && split_auto`）だけ。`--layer-split auto` は `--serve` を必要とし、少なくとも1枚の追加 stage GPU が必要で、複数 GPU の layer split には `--expert-profile` も必要（`engine/sycl/src/program/generate.cpp:2287-2329, 2333-2357, 3921-3923`）。
- 可視 GPU が1枚だけなら `--layer-split auto` は解除され、探索は行われない（`engine/sycl/src/program/generate.cpp:2313-2316`）。
- `--split-skip-if-fits` により CUDA0 だけで全 profiled pair を保持できると判定されると、分割状態が解除されるため、この値による選び直しも行われない（`engine/sycl/src/program/generate.cpp:3526-3569, 3921`）。
- 別環境変数 `STRATA_SPLIT_HEADROOM` が設定され、その値を `atoi` した結果が `0` の場合は候補を headroom 評価用に記録しない。これは static 初回評価の設定で、未設定なら有効、`0`・空文字・`false` などは無効になる（`engine/sycl/src/program/generate.cpp:4032-4052`）。
- 候補が複数必要。5 GPU 以上では比例配分の候補を1つだけ作り、4 stage でも列挙候補がない場合は比例配分に戻るため、別の選択肢との比較は起きない（`engine/sycl/src/program/generate.cpp:4144-4150, 4152-4155`）。明示的な `--layer-split K[,K2..]` は自動探索ではない。

## 実行時の詳細

許容幅は自動配置探索ブロックに入るたび、その場で `getenv` / `atof` から読み取る。環境値を CLI 引数、設定ファイル、別設定で上書きする処理はこのコード経路にない。探索後は選ばれた cut を `split_at` に置き、各 stage の層範囲を設定して後続の重み・session・expert cache の配置に使う（`engine/sycl/src/program/generate.cpp:4036-4037, 4173-4178, 4196-4207`）。

headroom 候補の各 stage の余裕量は `stage room - session bytes - その範囲にある全 expert の bytes` の最小値。許容時間内でこの値が最大の候補を選び、余裕量も同じなら予測時間が短い方、さらに同じなら先に並んだ候補を維持する。無効値の警告や変換エラー経路はない（`engine/include/strata/program/split_rules.hpp:128-138, 187-199`）。

## ログと測定値

headroom により最速候補から別の配置へ変更した場合、stderr に次の書式で出す（`%s` / `%f` 系は実値で置換される）。変更がなければこの行は出ず、いずれの場合も後続で自動 split の要約行を出す（`engine/sycl/src/program/generate.cpp:4152-4178`）。

```text
strata generate: layer split auto: K=%s instead of K=%s (predicted %.1f vs %.1f ms): its tightest card keeps %.2f GiB beyond all its layers' experts, against %.2f GiB (#1440: a full card can page to system memory); STRATA_SPLIT_HEADROOM=0 keeps K=%s
strata generate: layer split auto: K=%s - predicted %.1f ms per decode window; the caches hold %lld of %zu profiled pairs (~%.1f%% of the routed mass), best of %lld placements
```

## 根拠

- `engine/sycl/src/program/generate.cpp:2287-2329, 2333-2357` — `--serve`、stage GPU、profile を含む layer-split 条件。
- `engine/sycl/src/program/generate.cpp:3526-3569, 3921-3923, 4032-4052, 4152-4178` — 適用条件、値の読み取り、候補評価、配置とログ。
- `engine/include/strata/program/split_rules.hpp:118-138, 187-199` — 時間許容幅、同点時の規則、最小余裕量の定義。
