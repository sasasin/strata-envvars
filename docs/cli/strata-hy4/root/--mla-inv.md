# `strata-hy4 --mla-inv`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（トップレベル） |
| オプション | `--mla-inv` |
| 別名 | なし |
| 値 | 整数。0 は無効、0 以外は有効として扱われる |

## 役割

MLA attention の split-K 分割を batch-invariant にするかを切り替えます。有効にすると、`M <= 16` の因果 attention では、複数トークンを処理する場合も `M=1` のときと同じ split 数を選び、キーの分割と各行の加算順序を揃えるための設定です。既定値は無効です（`engine/src/hy4flash/run/mla_attn.hip.cpp:19`、`engine/src/hy4flash/run/mla_attn.hip.h:127`）。

## 使い方

```sh
strata-hy4 --model SQ64.strata --engram Engram-Q8.strata --tokens ids.txt --gen 32 --mla-inv 1
```

`--mla-inv 1` で有効、`--mla-inv 0` で無効にします。`--model` などの位置づけを含む実行形式は `strata-hy4` の root parser が処理します（`engine/src/hy4flash/run/hy4_main.hip.cpp:334-384,440-441`）。

## 値と既定値

- 値は必須です。値が後続引数にない場合は `ERR --mla-inv needs a value` を標準出力に出し、終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-382,441`）。
- 受け取った文字列は `atoi` で整数に変換され、その整数がグローバル設定に代入されます。0/1 以外を拒否する検証や範囲チェックはありません。実装側では値を真偽値に変換せず、0 かどうかで判定します（`engine/src/hy4flash/run/hy4_main.hip.cpp:441`、`engine/src/hy4flash/run/mla_attn.hip.cpp:1411`）。
- 省略時は `g_mla_batch_invariant` の初期値 0 により無効です。同じオプションを複数回指定した場合は parser が順に代入するため、最後の指定が残ります（`engine/src/hy4flash/run/mla_attn.hip.cpp:19`、`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,441`）。

## 実行時の動作

parser は指定値を `g_mla_batch_invariant` に設定します。MLA の split 数を選ぶ際、値が有効かつ `M <= 16` なら split 数計算上の基準を `M * (NH / 16)` から `NH / 16` に切り替えます。続けて `--mla-blocks` 由来の目標 block 数、キー tile 数、分割上限 128 で最終 split 数を制限します（`engine/src/hy4flash/run/mla_attn.hip.cpp:1409-1423`）。因果 attention で `M <= 16` の場合は、batch-invariant が有効なら最大キー数の見積もりも調整されます。`p0 + M <= 2064` なら 2048、それを超える場合は `max(p0 + M, cache_slots)` です（`engine/src/hy4flash/run/mla_attn.hip.cpp:2048-2057`）。

このオプションは初期設定です。`--draft dfly2` による speculative generation の通常実行では、`Spec::run` が `--spec-inv`（既定有効）の設定を `g_mla_batch_invariant` に再代入するため、このモードで `--mla-inv` の値は後から上書きされます（`engine/src/hy4flash/run/hy4_main.hip.cpp:426,701,992-1000`、`engine/src/hy4flash/run/hy4_spec.hip.h:18-25,91-96`）。A/B 比較モードも `scfg.inv` を再代入します（`engine/src/hy4flash/run/hy4_main.hip.cpp:914-928`）。

## 適用条件と副作用

- split 数基準の変更は `M <= 16` のときだけです。`M > 16` ではこのフラグによる基準値の差はありません（`engine/src/hy4flash/run/mla_attn.hip.cpp:1411`）。
- `max_keys_of` の追加分岐も因果 attention かつ `M <= 16` のときだけです。window attention では `window + 16`、その他の mode では `kmax` を使います（`engine/src/hy4flash/run/mla_attn.hip.cpp:2048-2057`）。
- `--mla-inv` 自体によるファイルやネットワークへの副作用は確認できません。分割数やキー範囲の計算を変える設定です。
- 調査した parser は CUDA/HIP 用 `strata-hy4` の `engine/src/hy4flash/run/hy4_main.hip.cpp` です。Metal と SYCL は別の実行ファイル・parser であり、このオプションが同じように受理されるとは確認できません（索引 `docs/cli/000_cli_tools.md:11`、Metal parser `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1491`、SYCL parser `engine/src/hy4flash/sycl/sy_main.cpp:79`）。

## 出力とエラー

値を省略した場合のエラーは前述の通りです。指定値の数値形式が不正な場合の変換結果は `atoi` に委ねられており、Strata 側には形式検証・専用エラー経路がありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-382,441`）。未知引数は標準エラーに `unknown arg ...` を出して終了コード 2 になりますが、`--mla-inv` は対象 parser に登録されています（`engine/src/hy4flash/run/hy4_main.hip.cpp:441,498-505`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:334-384,441` — root parser、必須値の取得、`atoi` による設定。
- `engine/src/hy4flash/run/mla_attn.hip.cpp:17-19,1409-1423,2048-2057` — 既定値、split 数決定、因果 attention の最大キー数決定。
- `engine/src/hy4flash/run/mla_attn.hip.h:124-127` — 設定変数と batch-invariant の説明。
- `engine/src/hy4flash/run/hy4_spec.hip.h:18-25,91-96`、`engine/src/hy4flash/run/hy4_main.hip.cpp:426,914-928,992-1000` — speculative mode における別設定による上書き。
- `docs/cli/README.md:1319` と `docs/cli/000_cli_tools.md:11` — 索引上の文書位置とツール・parser scope。
