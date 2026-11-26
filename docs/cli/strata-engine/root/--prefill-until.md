# `strata --prefill-until`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの引数） |
| オプション | `--prefill-until` |
| 別名 | なし |
| 値 | 整数。parser は `std::atoll` で `int64_t` に変換する。明示的な範囲検証はない |

## 役割

prompt の先頭何 token までを chunked / batched prefill で処理するかを指定する。残りの prompt token は通常の token path で順に処理されるため、複数位置の logits を検証する診断用途などで、prefill 後の状態を token path と比較できる。通常の生成ではこの分割を指定せず、既定の全 prompt prefill を使う。

## 使い方

```sh
# prompt の先頭 512 token を batched prefill に渡し、残りを token path で処理する
strata --pack ./model.strata --tokens-file ./prompt.tokens --prefill 2048 --prefill-until 512
```

`--prefill` で chunked prefill を有効にした例。`--tokens-file` は token ID の入力ファイルを指定する。

## 値と既定値

- 省略時の内部値は `0`。prompt の `n_prompt - 1` token を batched prefill に渡す。
- 値 `N` が `0 < N < n_prompt - 1` のときだけ `N` が batched prefill の token 数になる。それ以外（0、負数、`n_prompt - 1` 以上）は `n_prompt - 1` に戻り、全 prompt prefill と同じ扱いになる。
- 数値の文法、上限・下限は独自に検証しない。値は `std::atoll` で読み取られる。数値でない文字列も parser 上は明示的なエラーにならず、変換結果に基づいて上記の条件分岐が適用される。
- オプションの値を省略すると stderr に `--prefill-until needs a value` を出し、終了コード 2 で終了する。

## 実行時の動作

実行時に `n_batched` を決め、`prefill.run` にその token 数を渡す。処理後は `pos_start = n_batched` とし、prompt の残りを token path で処理する。最後の prompt token は生成の最初の予測に使われるため、batched prefill の対象は最大でも `n_prompt - 1` token である（CUDA/HIP/Metal 系: `engine/src/program/generate.cpp:23989,24164-24166,24215-24219`; SYCL: `engine/sycl/src/program/generate.cpp:13311,13385-13387,13426-13427`）。

## 適用条件と副作用

- `o.prefill_chunk > 0` かつ prompt が2 token以上のときに限り、batched prefill の `n_batched` と開始位置に反映される。chunk size 自体は別オプション `--prefill` 等で設定される。内部の初期値 `prefill_chunk` は0で、0は token path を表す（`engine/src/program/generate.cpp:971-972`; `engine/sycl/src/program/generate.cpp:637-638,13311-13312`）。
- `n_batched` が短くなる場合、実行時に prefill される token 数も減り、残りの prompt は token path に回る。デバイス処理、モデル形式、後続生成への影響の詳細は、ここで確認した範囲では `n_batched` の経路に限られる。
- 通常のエンジン parser にある。Qwen3.6 family は parser 処理前に `engine/src/qwen35` 側へ振り分けられるため、この文書の parser 経路には含まれない（`engine/src/program/generate.cpp:3804-3818`）。索引の `strata-engine/root` は通常のエンジン引数スコープ。
- prefill 実行が失敗すると stderr に `strata generate: <理由>` を出し、終了コード 1 で終了する（CUDA/HIP/Metal 系: `engine/src/program/generate.cpp:24164-24166`; SYCL: `engine/sycl/src/program/generate.cpp:13385-13387`）。

## 出力とエラー

- `--prefill-until` 自体の値については範囲外エラーや補正の警告を出さず、条件に合わなければ全 prompt prefill にフォールバックする（`engine/src/program/generate.cpp:23989`; `engine/sycl/src/program/generate.cpp:13311`）。
- prefill 後の通常ログは stderr に処理した token 数・chunk 数・時間等を表示する。この値は batched prefill 分を示す（CUDA/HIP/Metal 系: `engine/src/program/generate.cpp:24220-24226`; SYCL: `engine/sycl/src/program/generate.cpp:13431-13436`）。
- 値の省略時は parser の共通 `next` 処理が stderr に不足を出して終了コード 2 にする（`engine/src/program/generate.cpp:3842-3847`; `engine/sycl/src/program/generate.cpp:1882-1887`）。
- オプション文字列が認識されない parser では `unknown argument: ...` と usage を stderr に出し、終了コード 2 で終了する（`engine/src/program/generate.cpp:4268-4274`; `engine/sycl/src/program/generate.cpp:2214-2220`）。

## 根拠

- `engine/src/program/generate.cpp:1003-1006` — CUDA/HIP/Metal 系 `Options` の初期値とコメント上の意図。
- `engine/src/program/generate.cpp:4036-4039` — CUDA/HIP/Metal 系 parser 定義。値を `std::atoll` で読み込む。
- `engine/src/program/generate.cpp:23989-23990,24164-24166,24215-24219` — prefill 数の選択、実行、token path の開始位置。
- `engine/sycl/src/program/generate.cpp:651-654` — SYCL 側 `Options` の初期値と意図。
- `engine/sycl/src/program/generate.cpp:2032-2035` — SYCL parser 定義。
- `engine/sycl/src/program/generate.cpp:13311-13312,13385-13387,13426-13427` — SYCL 側の prefill 数の選択、実行、token path の開始位置。
- `engine/src/program/generate.cpp:3804-3818` — Qwen3.6 family を専用 parser に振り分ける処理。
