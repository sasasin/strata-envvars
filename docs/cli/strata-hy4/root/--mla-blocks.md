# `strata-hy4 --mla-blocks`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（トップレベル、CUDA/HIP） |
| オプション | `--mla-blocks` |
| 別名 | なし |
| 値 | 整数。MLA attention の split-K 分割数を決める際の目標ブロック数 |

## 役割

MLA attention の split-K 分割数を算出するときに使う目標値を設定する。値が大きくても実際の分割数は、query/head 数、参照する key のタイル数、分割上限で制限されるため、指定値と GPU の実ブロック数が一致する保証はない。既定値は `192`（`engine/src/hy4flash/run/mla_attn.hip.cpp:17-19`、宣言コメントは `engine/src/hy4flash/run/mla_attn.hip.h:124-127`）。

## 使い方

モデルファイルを指定して起動する例:

```sh
strata-hy4 --model /path/to/model.gguf --mla-blocks 256
```

`--mla-blocks` は値を一つ取る。トップレベル引数解析で整数変換して `g_mla_target_blocks` に代入する（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,440`）。

## 値と既定値

- 値は `atoi` で整数に変換される。CLI parser に数値形式・正数・範囲の検証はなく、変換に失敗した値を拒否する専用経路もない（`engine/src/hy4flash/run/hy4_main.hip.cpp:440`）。
- 省略時は `192`。同じオプションを複数回指定すると、引数走査中に同じ変数へ順に代入されるため、最後の指定値が残る（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,440`）。
- `--mla-blocks` の直後に値がない場合、parser は `ERR --mla-blocks needs a value` を stdout に出し、flush 後に終了コード `2` で終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-382`）。
- `0` または負数も parser では拒否されない。split 算出時の `base >= g_mla_target_blocks` が成立して分割数 `1` になるため、split-K 分割は行われない（`engine/src/hy4flash/run/mla_attn.hip.cpp:1409-1414`）。

## 実行時の動作

`g_mla_target_blocks` は初期値 `192` を持ち、オプション指定があれば parser がその値で置き換える（`engine/src/hy4flash/run/mla_attn.hip.cpp:17-19`、`engine/src/hy4flash/run/hy4_main.hip.cpp:440`）。MLA の split 数 `S` は `choose_splits()` が次のように決める（`engine/src/hy4flash/run/mla_attn.hip.cpp:1409-1423`）。

1. `base` を query 数 `M` と head 数 `NH` から求める。通常は `M * (NH / 16)`。`--mla-inv` が非ゼロで、かつ `M <= 16` の場合は `M` の代わりに `1` を使う（`--mla-inv` の設定は `engine/src/hy4flash/run/hy4_main.hip.cpp:440-441`、式は `engine/src/hy4flash/run/mla_attn.hip.cpp:1410-1412`）。
2. `base >= --mla-blocks` なら `S=1`。そうでなければ目標値を `base` で割り上げた値を初期値とし、key タイル数と `128` の小さい方以下に制限し、最後に最低 `1` とする（同 `:1412-1423`）。
3. key タイル数による上限は `HY4_MLA_SPLIT_DIV` にも依存する。この環境変数が設定されていれば `atoi` 結果の最低値 `1` を使い、未設定なら CUDA は `1`、HIP は `2` を使う。これは `static const` として初回の算出時に決まる（同 `:1415-1421`）。したがって同環境変数は `--mla-blocks` の目標値を置き換えず、算出された分割数を key タイル数から制限する。

`--mla-inv` 有効時は、分割数の `base` に加え、因果 attention の `max_keys` も `M <= 16` の範囲で batch invariant 用に算出される（`engine/src/hy4flash/run/mla_attn.hip.cpp:2048-2057`）。そのため `--mla-blocks` の結果は同オプションとの組み合わせで変わる。

この分割数は `mla_workspace_bytes()` の計算にも使われ、`S > 1` の場合に必要な一時 workspace は `M * (NH / 16) * S * (16 * MLA_KV_LORA + 32) * sizeof(float)` バイトとなる（`engine/src/hy4flash/run/mla_attn.hip.cpp:2038-2042`）。エンジンは不足時に workspace を拡張し、既存領域を解放して `hipMalloc` で確保する。グラフ実行時には関連グラフをクリアする（`engine/src/hy4flash/run/hy4_graph.hip.h:188-198`）。通常の MLA 呼び出しでは、attention 引数に応じたサイズを事前に確保してから `mla_attend()` を呼ぶ（同 `:2166-2169`）。

## 適用条件と副作用

- `strata-hy4` の CUDA/HIP parser が値を設定するが、効果が現れるのは MLA attention の split 数を算出する経路である。`mla_attend()` は `fast_ok` 条件を満たさない場合、または split 数が `1` の場合には分割経路を使わない。`fast_ok` は簡易経路が強制されていないこと、head 数が 16 の倍数であること、cache slot 数が正で 16 の倍数であること、窓 attention では ring も正で 16 の倍数であることを要求する（`engine/src/hy4flash/run/mla_attn.hip.cpp:2193-2203`）。
- 分割数の増加に伴い MLA 一時 workspace が増える。workspace が不足する状態で `mla_attend()` に入った場合は、q8 / 通常 KV に応じた simple attention kernel に fallback し、split 経路を使わない（同 `:2204-2208`）。
- ソース上、このオプション専用のログ、ファイル出力、環境変数書き換えは確認できない。workspace 確保で同期・解放・確保が起こり得る点は上記のとおり。

## 出力とエラー

有効な値を指定したときに `--mla-blocks` 専用の確認出力はない。値なしは stdout にエラーを出して終了コード `2` となる（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-382`）。未知の引数は stderr に `unknown arg <引数>` を出し、終了コード `2` となる（`engine/src/hy4flash/run/hy4_main.hip.cpp:498-505`）。

## 根拠

- parser、値の取り込み、値なし・未知引数の経路: `engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,438-442,498-505`
- 既定値と split 数の算出、`HY4_MLA_SPLIT_DIV` の制限: `engine/src/hy4flash/run/mla_attn.hip.cpp:17-19,1409-1423`
- workspace のサイズ・確保と MLA 呼び出し: `engine/src/hy4flash/run/mla_attn.hip.cpp:2038-2042,2193-2208`; `engine/src/hy4flash/run/hy4_graph.hip.h:188-198,2166-2169`
- `--mla-inv` による算出条件: `engine/src/hy4flash/run/hy4_main.hip.cpp:440-441`; `engine/src/hy4flash/run/mla_attn.hip.cpp:1410-1412,2048-2057`
