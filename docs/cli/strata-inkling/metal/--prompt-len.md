# `strata-inkling-metal --prompt-len`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal`（Metal） |
| オプション | `--prompt-len` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換される値 |

## 役割

`--bench` と `--par-sweep` が使う合成プロンプトの長さ（トークン数）を指定する。生成用の通常プロンプトや `--ids` の長さは変更しない。

## 使い方

```sh
strata-inkling-metal --model model.strata --bench --prompt-len 256
```

`--bench` の単一スロット計測で、長さ 256 の決定的な合成トークン列を prefill する。並列 sweep でも同じ長さを使う場合は `--par-sweep` を指定する。

## 値と既定値

- 省略時は `128`。
- 値の文字列は `atoi` で整数に変換される。専用の範囲検証や正の値の検証はない。空・数値として解釈できない文字列は `atoi` の変換結果 `0` となる。オプションの値が欠けると stderr に `missing value for --prompt-len` を出して終了コード `2` で終了する。
- 同じオプションを複数回指定した場合は、引数を順に走査して都度代入するため最後の指定が残る。
- 負数を含め、不正・極端な値に対するアプリケーション独自の拒否や補正は確認できない。負数は後段の `std::vector` サイズに渡されるため、正常に処理できる値としては扱えない。範囲外整数の `atoi` の結果はこのコードから保証できない。

## 実行時の動作

parser は `bench_prompt` に値を代入するだけで、`--bench` または `--par-sweep` がなければこの値を使う処理に入りません（`engine/src/inkling2/metal/ink_metal_main.cpp:424-429,452,589-614`）。

`--bench` では `bench_prompt` 要素の vector を作り、各要素を `100 + (i * 17) % 50000` で埋めて `run_greedy_decode` に渡す。結果の `[BENCH]` 行には prompt 長と prefill 計測値が出る。生成長は別変数 `--gen`（既定 32）が決める（同 `:423-424,589-603`）。prompt が空の場合、prefill ループは実行されず、`run_greedy_decode` 内の初期値 `next_tok = 0` が後続の生成に使われる。これは通常の正の長さの計測とは異なる経路である（同 `:138-163`）。

`--par-sweep` では同じ `bench_prompt` が 1、4、8、32、64 slot の各計測に渡される。各 slot の合成 token ID は slot と位置から生成され、prompt 長は prefill の位置範囲と decode 開始位置にも使われる。`--parallel` / `--slots` が sweep 対象数を制限するため、64 未満を指定すると parser が最低 64 に引き上げる（同 `:363-414,449,457,606-613`）。

## 適用条件と副作用

- Metal 実装でのみ扱うオプションである。対象 parser は `engine/src/inkling2/metal/ink_metal_main.cpp` にある。
- `--bench` と `--par-sweep` の計測処理を実行するとモデルのロード、Metal runner の初期化、および推論計算を伴う（同 `:470-493,589-613`）。オプション自体によるファイル出力は確認できない。
- 既定の最大 context は 4096（`--max-context` / `--ctx` で変更可能）。`run_greedy_decode` は生成ループを最大 context によって制限するが、このオプションの prompt 長を事前検証する処理は見当たらない。context 超過時に prefill がどう失敗するかは、この parser 側のコードだけでは確定できない（同 `:420,448,174-185`）。

## 出力とエラー

成功時、`--bench` は stdout に `[BENCH]` 行を出し、`--par-sweep` は各実施 slot 数について `[PAR ...]` 行を出す（`engine/src/inkling2/metal/ink_metal_main.cpp:409-413,600-603`）。forward 処理が失敗した場合は stderr に `[ERROR] bench: ...` または `[ERROR] par c=...: ...` を出し、終了コード `1` となる（同 `:596-599,609-611`）。prompt 長に対する範囲エラー専用の診断は確認できない。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:417-468` — Metal CLI の parser、既定値、`atoi` 変換、値欠落・未知引数の処理。
- `engine/src/inkling2/metal/ink_metal_main.cpp:120-163,174-185` — 単一 slot の合成 prompt prefill、生成開始と最大 context による生成制限。
- `engine/src/inkling2/metal/ink_metal_main.cpp:362-414,589-613` — 並列 benchmark と単一 benchmark における prompt 長の利用、結果出力、失敗経路。
- `docs/cli/README.md:1549-1569` — `strata-inkling-metal` の索引上のスコープと `--prompt-len` の掲載。
