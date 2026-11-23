# `strata-hy4-metal --temp`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend） |
| オプション | `--temp` |
| 別名 | なし |
| 値 | `atof` で `float` に変換される値。parser に範囲検証や clamp はない |

## 役割

Metal 版 Hy4-Flash の offline 生成で、適用される生成経路では温度を確率サンプリング設定へ渡す。温度が正なら logits に temperature softmax を適用し、top-k / min-p / top-p で候補を絞った分布から選ぶ。既定値は `0` で greedy 判定となる。ただし、この値はすべての `--gen` 経路に反映されるわけではなく、通常の非 speculative 生成では `--temp` を指定しても argmax が使われる。

## 使い方

```sh
# DFly2 drafter を含むモデルで、offline の speculative 生成に温度を指定する
strata-hy4-metal --model ./model.strata --tokens ./prompt.ids --gen 64 --draft dfly2 --temp 0.7
```

この例で `--temp` がサンプリングに使われるには、モデルに DFly2 drafter があり、chunk が 16 以上で、`--all-logits` と画像入力を使わず、`--draft off` でないことが必要。`--draft dfly2` が実行可能でない場合は通常生成経路になり、そこではこの温度は使われない。

## 値と既定値

- `--temp` の値は `atof` の戻り値を `float` にして `SampleOpts.temperature` に代入する。省略時は `SampleOpts` の初期値 `0.f`。
- parser に数値形式・範囲の検証や補正はない。複数回指定した場合は引数を順に処理して同じフィールドへ代入するため、後の指定が残る。
- `temperature <= 0` は `greedy()` 判定となる。正の温度では確率分布の計算に温度を使う。
- 引数値が欠けている場合の専用エラー処理は parser にない。無効形式をどう数値化するかなど、`atof` 自体の詳細はこの Strata ソースだけからは定めない。

## 実行時の動作

parser は `--temp VALUE` を `cli_samp.temperature` に設定する。offline 側では `cli_prob` が「温度が greedy 判定でない」場合に真になり、確率分布計算へ進む。分布計算は logits を top-k（最大64候補）で絞り、温度 softmax、min-p、top-p の順で候補を残して再正規化する。したがって正の `--temp` は `--top-k`、`--min-p`、`--top-p` と組み合わさる。負値やゼロは greedy 判定となり、温度 softmax は通らない。

適用されるのは DFly2 speculative decode 経路である。speculative mode は `gen > 0` または計測用モードに加え、`--draft off` でないこと、モデル内に drafter があること、runner chunk が16以上であること、`--all-logits` でないこと、画像入力がないことを条件に成立する。通常の `--gen` 経路は `r.argmax()` を使って次 token を選び、`cli_samp` を参照しないため、speculative mode が成立しない場合は `--temp` が通常生成に反映されない。計測専用の `--bench-m` / `--par-m` 経路も生成前に終了する。

`--serve` では CLI の `cli_samp` を ServeOpts に渡していないため、起動時の `--temp` はリクエスト sampling に反映されない。serve の GEN リクエストは独自の `SampleOpts` を持ち、`temperature=...` をリクエストごとに指定する。値を省略したリクエストの既定値は同じく `0.f`。

## 適用条件と副作用

- 温度自体はモデルやファイルを書き換えない。生成結果の token 選択に影響する。
- `--draft dfly2` を指定しても spec 条件が不成立なら警告を stderr に出して通常経路へ進む。モデルに drafter がない場合など、speculative 初期化に失敗した場合はエラーを stderr に出して終了する。
- `--temp` 専用の stdout/stderr 出力はない。生成時の token ID は speculative 経路では stdout の `generated ids:`、通常経路でも `generated ids:` に出され、`--out` のディレクトリに `gen_ids.txt` が書かれる。これは生成モード全体の出力で、温度指定の副作用ではない。

## 出力とエラー

- `--temp` の値について parser 段階の validation error はない。
- unknown flag は stdout に `ERR unknown flag ...`、stderr に `unknown arg ...` を出して終了コード `2`。
- `--draft dfly2` が利用できない場合は stderr に理由の警告を出す。speculative 実行が `finish == "error"` になった場合は `spec: ...` を stderr に出して終了コード `1`。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1501-1504` — default の draft mode が `auto`、`SampleOpts` の生成。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1567-1571` — `--temp` の parser と、関連する `--top-p` / `--top-k` / `--min-p` / `--seed` の設定。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609` — 未知引数の出力と終了コード。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1674` — serve 起動時に `ServeOpts` を構成し、`cli_samp` は渡さないこと。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1755-1769` — DFly2 の有無と speculative mode 条件、要求時の警告および初期化エラー。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1818-1844` — offline sampling 判定、通常 decode helper での分布利用。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1898-1943` — speculative decode への `cli_samp` 受け渡しとエラー経路。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1944-1976` — 通常の `--gen` が argmax を使い、生成 ID を出力・保存する経路。
- `engine/src/hy4flash/metal/hy4_metal_spec.h:15-24, 49-94` — temperature 既定値と greedy 判定、top-k・temperature・min-p・top-p による分布計算。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:91-94, 121-143` — GEN リクエストごとの sampler と `temperature=` の解析。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:162-210, 505-536` — serve sampling の温度適用と生成時の利用。
