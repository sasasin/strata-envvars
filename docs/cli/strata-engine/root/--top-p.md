# `--top-p`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの引数。`strata generate`） |
| オプション | `--top-p` |
| 別名 | なし |
| 値 | 浮動小数点数 `F`。有限値で `0 < F <= 1` |

## 役割

サンプリング時に、確率の高い候補から累積確率が指定値以上になるまでを残す nucleus（top-p）フィルターの閾値を指定する。`1` ではこのフィルターを無効にする。既定では greedy 実行なので、値を指定しただけではサンプリングに切り替わらない。

## 使い方

```sh
# seed を指定してサンプリングし、top-p 閾値を 0.9 にする
strata --tokens "1,2,3" --seed 123 --top-p 0.9
```

この CLI は事前 tokenize 済みの token ID を受け取る。通常の greedy 実行では top-p は候補選択に使われない。

## 値と既定値

- 既定値は `0.95`。値は `float` として `std::atof` で読み取られる。
- 検証を通る範囲は有限値の `(0, 1]`。`0`、負数、`1` より大きい値、NaN、無限大は拒否される。
- 同じ引数を複数回指定したときは、parser が順に代入するため最後の値が残る。
- 引数値がない場合は `--top-p needs a value` を stderr に出して終了コード `2`。数値として解釈できない文字列は `atof` により `0` となり、範囲検証で拒否される。

## 実行時の動作

値は `SamplerParams.top_p` に渡され、token sampling kernel が候補を切り詰める。処理順は penalties → top-k → top-p → min-p → temperature → token 選択。top-p は top-k 後の候補 logits から softmax 確率を求め、降順候補の累積確率が `F` 以上となる最初の候補までを残す。top-k と組み合わせた場合、top-p の累積確率は top-k で選ばれた候補集合上で正規化される。`F=1` のとき top-p の切り詰め処理を行わない。

既定の `--greedy` は有効で、`--seed` は greedy を解除して sampled path を有効にする。したがって通常の単発生成で top-p を効かせるには、greedy を解除し、temperature を正にする必要がある。`--greedy` と `--seed` を両方指定した場合は引数の並び順が有効で、parser は `--greedy` を true、`--seed` を false に設定する。temperature が 0 以下の場合も sampler は greedy 経路を選ぶ。

`--serve` ではリクエストごとの sampling 設定が使われる。リクエストに `top_p` がなければ `1.0`、temperature がなければ `0`（greedy）が初期値となるため、起動時の `--top-p` は serve リクエストの閾値を設定しない。

## 適用条件と副作用

top-p は sampled path で候補 token の選択に作用し、生成内容に影響する。CLI の起動引数を読み込む以外に、このオプション固有のファイル書き込みやネットワーク動作はない。serve モードでは各リクエスト内の `top_p` が使われる。

## 出力とエラー

無効な範囲の値は `strata generate: invalid sampling or resource parameter` を stderr に出し、終了コード `2` で終了する。このエラーは他の sampling/resource パラメータの検証とも共用される。引数値の欠落も stderr と終了コード `2` で失敗する。

## 根拠

- `engine/src/program/generate.cpp:756-765` — `Options.top_p` の型と既定値。
- `engine/src/program/generate.cpp:1280-1283` — help における `--top-p F` の記載。
- `engine/src/program/generate.cpp:3844-3846,3881-3885` — 値欠落時のエラー処理、`--seed` / `--greedy` との設定順、top-p 代入。
- `engine/src/program/generate.cpp:5267-5274` — 有限値と `(0,1]` の検証、および拒否時の stderr・終了コード。
- `engine/src/program/generate.cpp:10635-10649` — `SamplerParams` への転送、greedy/sample の診断出力、serve はリクエスト単位で sampling する旨。
- `engine/src/program/generate.cpp:18824-18830,18901-18904,18951-18967` — serve リクエストの `top_p` 既定値と個別の sampler 設定。
- `engine/src/program/generate.cpp:24401-24405` — 通常生成ループから sampler を呼び出し、選択 token を読み戻す箇所。
- `engine/src/kernels/cuda/sampler.cu:384-402` — top-k 後の候補上で top-p の累積確率を計算して残す範囲を決める処理。
- `engine/src/kernels/cuda/sampler.cu:1280-1290` — greedy と sampled の kernel 経路の分岐。
- `engine/include/strata/kernels/sampler.hpp:15-20` — sampler パラメータ既定値と filter chain の説明。
