# `--yarn-orig-ctx`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ推論エンジン `strata`（root parser） |
| オプション | `--yarn-orig-ctx N` |
| 別名 | なし |
| 値 | 浮動小数点数。`0` はモデル値または既定値を使う。 |

## 役割

RoPE の YaRN 補正が基準にする「学習時コンテキスト長」を指定する。解決後の値は RoPE 補正区間（pair index の low/high）を求める計算に使われる。位置ごとの生成上限を設定するオプションではない（`--max-context` とは別）。`RopeScaling::corr_dims` は `orig_ctx` と beta 値から区間を計算し、RoPE テーブル構築がその区間を補正角度の混合に使う（`include/strata/kernels/rope_scaling.hpp:92-100`、`src/kernels/cuda/rope.cu:61-83`）。

## 使い方

```sh
strata --native /path/to/model.gguf --rope-scaling yarn --yarn-orig-ctx 131072
```

`--native` で通常エンジンに GGUF モデルを指定する実行例。`--rope-scaling yarn` を省略した場合、この値だけで YaRN が有効になるわけではなく、モデルの scaling metadata または別の `--rope-scaling` 指定に従う（`src/program/generate.cpp:3642-3647,3681-3694`）。

## 値と既定値

- オプションの値は `std::atof` で `double` に変換される。繰り返し指定した場合は parser が順に代入するため最後の値が残る（`src/program/generate.cpp:2416-2421,2450`）。値を省略すると `--yarn-orig-ctx needs a value` を stderr に出して終了コード `2` で終了する（同 `2418-2420`）。
- 値は有限かつ `0` 以上でなければならない。NaN/無限大および負数は validation で拒否され、終了コード `2`（同 `3328-3334,3345-3350`）。
- `0` は明示的なコンテキスト長としては使われず、モデル metadata に対象 arch の `rope.scaling.original_context_length` があり値が `1` 以上ならその値を採用する。モデル値がない場合の構造体既定値は `262144`（同 `3651-3653,3673-3674,3700-3701`、`include/strata/kernels/rope_scaling.hpp:66-75`）。オプション省略も parser 初期値 `0` のままなので同じ解決経路になる（`src/program/generate.cpp:459,2450,3700-3701`）。
- `0` より大きい明示値はモデル metadata より優先される。0 以外の値は parser 検査では `>= 1` まで要求されず、たとえば `0 < N < 1` は scaling が有効な構成では解決後 validation に失敗する。一方 `--rope-scaling none` のときは scaling knobs をリセットするため、この値は構成の有効性検査対象から外れ、効果もない（`src/program/generate.cpp:3345-3349,3700-3719`、`include/strata/kernels/rope_scaling.hpp:169-183`）。
- `atof` は厳密な数値構文検査ではないため、数値に変換できない文字列は `0` となり、上記の fallback と同様に扱われる。これは parser の変換方式から分かる範囲であり、入力形式として推奨される使い方ではない（`src/program/generate.cpp:2450`）。

## 実行時の動作

値は起動時に一度だけ解決される。モデルを読む場合、エンジンは arch prefix 付きの GGUF key `rope.scaling.original_context_length` を取得する。明示値 `N > 0` があればそれを優先し、そうでなければ metadata 値 `>= 1`、それもなければ `RopeScaling` の `262144` を使う（`src/program/generate.cpp:3651-3674,3700-3701`、`include/strata/kernels/rope_scaling.hpp:66-75`）。

解決値は `RopeScaling::corr_dims` が YaRN の周波数補正区間を計算する入力になる。RoPE table builder はその区間を使い、`ext_factor` が 0 でないとき補間角と学習時角の混合を行う（`include/strata/kernels/rope_scaling.hpp:92-100`、`src/kernels/cuda/rope.cu:67-83`）。そのため値は `--rope-scaling yarn` など RoPE scaling が有効な構成で意味を持つ。`none` では係数を初期状態に戻して無効化する。`linear` でも共通設定に値は格納され、区間は計算されるが、`--yarn-ext-factor` が既定の自動値から `0` になるため table builder の補正角混合は行われない（`src/program/generate.cpp:3700-3719`、`src/kernels/cuda/rope.cu:69-83`）。

RoPE 設定は session 初期化より前にプロセス全体の設定として固定される。1つの KV cache 内で異なる RoPE scaling を混ぜないため、リクエストごとの切り替えはない（`src/program/generate.cpp:450-454,3642-3647,3731`）。

## 適用条件と副作用

- 値はモデルの RoPE metadata より優先されるので、誤った学習時コンテキスト長を指定すると YaRN 補正区間が意図と異なる値になる。
- 有効な scaling 構成で解決後の `orig_ctx` が有限かつ `>= 1` でなければ、全体構成 validation が失敗する（`include/strata/kernels/rope_scaling.hpp:164-183`）。
- `--rope-scaling none` では `--yarn-orig-ctx` を含む YaRN knobs がリセットされる。警告は `--rope-scale > 1`、`--rope-freq-scale > 0`、`--yarn-ext-factor > 0`、または `--yarn-attn-factor != 1` のいずれかを検知した場合に限られるため、`--yarn-orig-ctx` 単独指定は効果がなくてもこの警告条件には含まれない（`src/program/generate.cpp:3708-3719`）。
- 有効な scaling 時は stderr に resolved type、factor、context、学習時 context を含む診断行が出る。実行の主な副作用は起動時の RoPE 設定と、それを使う RoPE table / kernel 構成への反映（`src/program/generate.cpp:3731-3743`、`src/kernels/cuda/rope.cu:48-83`）。

## 出力とエラー

- 値不足: stderr に `--yarn-orig-ctx needs a value`、終了コード `2`（`src/program/generate.cpp:2418-2420`）。
- NaN / 無限大: stderr に `strata generate: a rope scaling knob is not a finite number (...)`、終了コード `2`（`src/program/generate.cpp:3328-3334`）。
- 負数: stderr に `strata generate: invalid rope scaling knob ...`、終了コード `2`（`src/program/generate.cpp:3345-3349`）。
- scaling 有効時に metadata 由来を含む解決値が `1` 未満の場合: `invalid rope scaling configuration: the original (trained) context must be finite and > 0 ...` を stderr に出し、終了コード `2`（`include/strata/kernels/rope_scaling.hpp:177`、`src/program/generate.cpp:3724-3729`）。

## 根拠

- 索引上の tool/command scope: `docs/cli/README.md:1128-1134,1312-1316`（調査対象リポジトリ）。
- parser の既定値、help 表示、値の読取り: `src/program/generate.cpp:459,875-877,2416-2421,2450`。
- CLI 値の validation、GGUF metadata と優先順位、解決後の適用と診断: `src/program/generate.cpp:3328-3350,3642-3674,3681-3743`。
- YaRN の `orig_ctx` 既定値・補正区間・有効構成 validation: `include/strata/kernels/rope_scaling.hpp:66-75,92-100,164-183`。
- RoPE table での角度補正: `src/kernels/cuda/rope.cu:61-83`。

調査時に確認した Strata checkout は `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、作業状態は `main...origin/main`（`git status --short --branch`）だった。別 revision の help や Release artifact は参照していない。
