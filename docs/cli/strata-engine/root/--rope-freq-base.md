# `--rope-freq-base`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン通常 parser。通常生成は `strata generate` として案内） |
| オプション | `--rope-freq-base` |
| 別名 | なし |
| 値 | 数値 `N`。有限値で、`0` または `1` より大きい値 |

## 役割

RoPE（rotary position embedding）の周波数基準値を指定します。`N` は回転角を計算する基準で、通常の RoPE scaling の有無とは別に作用します。値を明示すると、モデルの GGUF metadata やエンジンの既定値より優先されます（`src/program/generate.cpp:3698-3699`）。

## 使い方

```sh
strata generate --pack MODEL --tokens '1,2,3' --rope-freq-base 10000000
```

この例は `generate` エンジンの引数形式を示します。`--pack` と `--tokens` は別途必要なモデル・入力指定です（usage: `src/program/generate.cpp:865-875`）。

## 値と既定値

- 値は `std::atof` で `double` に変換されます。省略時の parser 内の値は `0` です（`src/program/generate.cpp:457`, `src/program/generate.cpp:2448`）。
- `0` は明示的な周波数基準値ではなく、GGUF の `<arch>.rope.freq_base` があればその値を使う指定です。GGUF 値がない、または `1` 以下の場合は `RopeScaling` の既定値 `1e7` が残ります（`src/program/generate.cpp:3698-3699`, `include/strata/kernels/rope_scaling.hpp:66-71`）。
- `1` 以下の非ゼロ値、NaN、無限大は拒否されます。受理される明示値は有限の `N > 1` です（`src/program/generate.cpp:3328-3343`）。
- 同じオプションを複数回指定した場合、parser は各指定を順に代入し、後の値が前の値を置き換えます。重複指定専用のエラー処理はありません（`src/program/generate.cpp:2416-2421`, `src/program/generate.cpp:2448`）。
- 値を付けずに終わると `--rope-freq-base needs a value` を標準エラーに出して終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。

## 実行時の動作

parser が値を受け取ると、RoPE の設定を組み立てる段階で明示値が正なら `rope_cfg.freq_base` に設定されます。明示値が `0` の場合は、`--native` で読み込む GGUF の architecture prefix 付き `rope.freq_base` が `1` より大きければ採用され、それ以外は既定値 `1e7` です。GGUF の当該キーは `--native` のモデル shard から読まれます（`src/program/generate.cpp:3651-3674`, `src/program/generate.cpp:3698-3699`）。

確定した設定は `rope_scaling_set` でプロセス設定に一度登録され、`session_init` がテーブルを構築する前に使われます（`src/program/generate.cpp:3642-3647`, `src/program/generate.cpp:3731`, `include/strata/kernels/rope_scaling.hpp:186-190`）。通常の RoPE では各回転周波数に `freq_base^(-2i/n_rot)` を使って角度を作るため、基準値を変えると回転角が変わります（`src/kernels/cuda/rope.cu:48-58`, `src/kernels/cuda/rope.cu:61-85`）。

この設定はプロセス全体で起動時に固定され、リクエストごとの切り替えには対応しません。同一 KV cache に異なる RoPE 設定を混在させないためです（`src/program/generate.cpp:450-454`）。`--rope-scaling none` の場合も、解決済みの `freq_base` は保持され、他の scaling knob だけがリセットされます（`src/program/generate.cpp:3708-3719`）。したがって `--rope-freq-base` は `none` でも有効です。

## 適用条件と副作用

値はエンジン起動時に解決され、RoPE の角度計算に反映されます。モデル metadata 由来の値も含めて、解決後の設定全体が有限かつ有効な周波数基準値 `> 1` であることを再検証します（`include/strata/kernels/rope_scaling.hpp:164-183`）。RoPE scaling のタイプが `none` でも基準値は検証と回転に使われます。

Qwen3.6 用の family parser は `--rope-freq-base` を定義していません。`--native` または `--model` の GGUF が同 family と判定されるとそちらへ振り分けられ、通常実行では未知引数として usage を表示して終了コード `2`、serve 実行では未知引数を警告して無視します（`src/program/generate.cpp:2393-2407`, `src/qwen35/q36_engine.cu:3782-3795`）。

確認した範囲では、このオプション自体によるファイル書き込みやネットワーク通信はありません。副作用は同じ実行内の位置エンコーディングと、それを使う推論結果への影響です。ソース上、推奨値や特定モデルでの品質・性能は定められていません。

## 出力とエラー

- 非ゼロ値が `1` 以下の場合、`strata generate: --rope-freq-base must be a base above 1 (0 = the model's)` を標準エラーに出して終了コード `2` になります（`src/program/generate.cpp:3341-3343`）。
- RoPE knob のいずれかが有限値でない場合は診断を標準エラーに出して終了コード `2` になります。`--rope-freq-base nan` などが該当します（`src/program/generate.cpp:3328-3334`）。
- GGUF 値などを含めた設定全体の検証に失敗した場合は `invalid rope scaling configuration` と理由・解決値を標準エラーに出し、終了コード `2` になります（`src/program/generate.cpp:3721-3729`）。
- 数値でない文字列の厳密な構文検証は parser にありません。`std::atof` の変換結果を後段の検証が扱うため、変換できない文字列は `0` としてモデル値または既定値にフォールバックします（`src/program/generate.cpp:2448`, `src/program/generate.cpp:3698-3699`, `src/program/generate.cpp:3328-3343`）。

## 根拠

- option の既定 parser 値と使用法表示: `src/program/generate.cpp:457`, `src/program/generate.cpp:873-874`。
- 値の parser と不足値の失敗経路: `src/program/generate.cpp:2418-2421`, `src/program/generate.cpp:2448`。
- 有限値・範囲 validation: `src/program/generate.cpp:3328-3343`。
- GGUF metadata の読み込みと優先順位: `src/program/generate.cpp:3642-3674`, `src/program/generate.cpp:3698-3699`。
- Qwen3.6 専用 parser への family 分岐と未知 option の扱い: `src/program/generate.cpp:2393-2407`, `src/qwen35/q36_engine.cu:3782-3795`。
- 確定値の設定、`none` での扱い、全体 validation: `src/program/generate.cpp:3708-3731`, `include/strata/kernels/rope_scaling.hpp:164-190`。
- RoPE 周波数基準値を使うテーブル計算: `src/kernels/cuda/rope.cu:48-85`。
- SYCL 実装にも同じ parser・validation・値解決処理があります: `sycl/src/program/generate.cpp:440`, `sycl/src/program/generate.cpp:1789`, `sycl/src/program/generate.cpp:2494-2510`, `sycl/src/program/generate.cpp:2782-2817`。
