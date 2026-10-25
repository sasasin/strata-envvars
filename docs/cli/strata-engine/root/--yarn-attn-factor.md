# `--yarn-attn-factor`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の engine 引数（CLI 表記は `strata generate`） |
| オプション | `--yarn-attn-factor` |
| 別名 | なし |
| 値 | 正の有限な浮動小数点数 `F` |

## 役割

RoPE scaling 使用時の cos/sin 振幅補正係数を指定します。既定値は `1` です。実装では、この係数を YaRN の対数補正（YaRN correction が有効な場合）と組み合わせた値を RoPE の cos/sin に乗じます。品質や性能に対する推奨値は、このソース調査だけでは判断できません。

## 使い方

モデルと入力 token を指定する `strata generate` の engine 引数として使います。例えば:

```sh
strata generate --pack pack/full --tokens "1,2,3" --rope-scaling yarn --rope-scale 4 --yarn-attn-factor 1.2
```

この例の `1.2` は書式例であり、推奨値ではありません。engine の usage は `--pack` と `--tokens` を含む `strata generate` 構文を示しています（`src/program/generate.cpp:806-810`）。

## 値と既定値

- 値は `std::atof` で `double` に変換され、オプションを複数回指定すると最後の値が残ります（`src/program/generate.cpp:2447-2454`）。
- 省略時は `1.0` です（`src/program/generate.cpp:461`）。値の引数がない場合は `--yarn-attn-factor needs a value` を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。
- 変換後の値は有限かつ `> 0` でなければなりません。`nan` / 無限大は有限性検査で拒否され、0、負数、数値に変換できず `atof` が 0 を返す入力も範囲検査で拒否されます（`src/program/generate.cpp:3328-3334,3345-3349`）。
- 範囲外の値は `strata generate: invalid rope scaling knob ...` を stderr に出し、終了コード `2` になります。

## 実行時の動作

値は `RopeScaling::attn_factor` に設定されます（`src/program/generate.cpp:3702-3707`、`include/strata/kernels/rope_scaling.hpp:68-75`）。有効な scaling 設定では、最終的な振幅係数は次のとおりです:

- `ext_factor == 0` のとき `mscale = attn_factor`。
- `ext_factor != 0` のとき `mscale = attn_factor * (1 + 0.1 * ln(1 / freq_scale))`。

この計算は `RopeScaling::mscale()` に定義されています（`include/strata/kernels/rope_scaling.hpp:84-90`）。YaRN の既定 `ext_factor` は 1（`--yarn-ext-factor` を省略した場合）ですが、`--yarn-ext-factor 0` なら対数補正は入りません（`src/program/generate.cpp:3703-3705`）。`freq_scale` は明示した正の `--rope-freq-scale`、またはそれが 0 の場合は `1 / factor` です（`include/strata/kernels/rope_scaling.hpp:77-82`）。従って YaRN では `--rope-scale`、`--rope-freq-scale`、`--yarn-ext-factor` が実効値に影響します。

テーブル生成経路では `mscale` を各位置・回転ペアの cos/sin に乗じます（`src/kernels/cuda/rope.cu:61-84`）。analytic 経路も同じ振幅補正を cos/sin に適用します（`include/strata/kernels/rope_scaling.hpp:145-166`）。設定はプロセス起動時に一度固定され、session の RoPE table と kernel graph が構築されます。リクエスト単位で変更するオプションではありません（`src/program/generate.cpp:450-454,3642-3647,3731`、`include/strata/kernels/rope_scaling.hpp:187-192`）。

`--rope-scaling` が未指定なら model GGUF の rope scaling type が参照され、明示した `none` / `linear` / `yarn` は model file より優先します（`src/program/generate.cpp:3645-3647,3681-3694`）。`none` が解決された場合、このオプションを含む scaling knobs は無効化・初期化され、値は RoPE に反映されません。係数が既定値 `1` 以外なら、stderr に「no rope scaling is active ... have no effect」という note が出ます（`src/program/generate.cpp:3708-3719`）。

## 適用条件と副作用

- 値の検査は scaling type が `none` でも先に行われるため、不正値は拒否されます。ただし type が `none` なら有効な値も結果に使われません（`src/program/generate.cpp:3328-3350,3708-3719`）。
- scaling が有効な場合、係数は全ての位置の cos/sin 振幅に反映されます。`--max-context` が学習済み context 以下でも scaling は各 angle に適用される旨を engine が stderr に表示します（`src/program/generate.cpp:3732-3750`）。
- RoPE config は session 初期化と kernel capture より前に設定されます（`src/program/generate.cpp:3642-3647,3731`）。調査した範囲では、このオプション自体によるファイル書き込みやネットワーク通信は確認できません。
- `strata` が Qwen3.6 family と判定したモデルは別 parser に委譲されます（`src/program/generate.cpp:2393-2407`）。本書は索引で `strata-engine/root` に分類された通常 engine parser の調査です。Qwen3.6 専用 parser の同名オプションの有無や挙動は本調査では確認していません。

## 出力とエラー

- 有効な scaling type なら stderr に解決後の scaling type、factor、frequency scale、base、`mscale`、`--max-context` と学習済み context が出力されます。`mscale != 1` の場合、さらに cos/sin をその倍率で補正する note が出ます（`src/program/generate.cpp:3732-3750`）。
- `none` の場合、値が既定値以外なら scaling が無効である note を stderr に出力します（`src/program/generate.cpp:3712-3719`）。
- 解決後の config も検証され、`mscale` が有限でない、または `<= 0` なら `invalid rope scaling configuration` を stderr に出して終了コード `2` になります（`include/strata/kernels/rope_scaling.hpp:170-183`、`src/program/generate.cpp:3721-3729`）。

## 根拠

- parser の値変換と既定値: `src/program/generate.cpp:461,2447-2454`
- 引数不足・数値範囲検証: `src/program/generate.cpp:2418-2420,3328-3350`
- model metadata と CLI の優先順位、none 時の扱い、config 固定: `src/program/generate.cpp:3642-3719,3731`
- 振幅計算・検証: `include/strata/kernels/rope_scaling.hpp:68-90,170-183`
- cos/sin への実適用: `src/kernels/cuda/rope.cu:61-84`。この箇所は CUDA 経路の実装。
- CLI 索引の配置と scope: `docs/cli/README.md:1128-1142,1312`
