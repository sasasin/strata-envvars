# `--rope-freq-scale`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--rope-freq-scale F` |
| 別名 | なし |
| 値 | `std::atof` で読む浮動小数点数。有限の 0 以上。0 は自動値を表す |

## 役割

RoPE（rotary position embedding）の角度縮小率を指定します。`--rope-scaling linear` または `--rope-scaling yarn` と組み合わせたとき、指定値が補間角度に掛かります。省略値の 0 では `--rope-scale` から `1 / factor` が求められます。`--rope-scaling none` ではこの値は使われません。

## 使い方

エンジンのヘルプに示された形式に沿った例です。以下は `strata generate` の引数例で、モデルパックと prompt token を別途用意してください。

```sh
strata generate --pack /path/to/pack --tokens "1,2,3" \
  --rope-scaling linear --rope-scale 2 --rope-freq-scale 0.5
```

## 値と既定値

- 値は `std::atof` で double に変換されます。parser はこのオプションの複数指定を個別に拒否せず、引数走査中に後から指定された値が同じ設定欄を上書きします。
- 既定値は 0 です。`linear` / `yarn` で有効なとき、0 は `1 / --rope-scale` に解決されます。正数はそのまま角度倍率として使用されます。
- 負数、NaN、無限大は不受理です。正数に明示的な上限はありませんが、解決した RoPE 設定全体の有限性・正値条件も検証されます。
- 値がない場合、parser の `next()` が stderr に `--rope-freq-scale needs a value` を出し、終了コード 2 で終了します。
- `atof` は厳密な数値書式検査をしていません。たとえば変換できない文字列や空文字列は 0 になり、自動値として扱われます。

## 実行時の動作

parser は `--rope-freq-scale` の次の引数を `std::atof` で `Options::rope_freq_scale` に格納します。最初の検証では全 RoPE knob の有限性を調べ、負の frequency scale を拒否します（`src/program/generate.cpp:2449, 3328-3349`）。

RoPE 設定の解決時には `rope_freq_scale` を `freq_scale_in` に設定します。`RopeScaling::freq_scale()` は scaling type が `None` なら 1 を返し、それ以外では正の明示値を使い、0 以下なら `1 / factor` を返します（`src/program/generate.cpp:3702`; `include/strata/kernels/rope_scaling.hpp:77-82`）。従って明示値は `--rope-scale` から自動計算される値を置き換えます。モデル GGUF の scaling type・factor との解決順は、CLI の明示値がモデル metadata より優先し、未指定時はモデル値、その後に構造体既定値です（`src/program/generate.cpp:3642-3647, 3682-3704`）。

設定はプロセス内で `session_init` より前に一度設定されます。RoPE table の生成では各位置の角度に frequency scale を掛け、YaRN correction が有効なら補間角度と外挿角度を混ぜます（`src/program/generate.cpp:3721-3731`; `src/kernels/cuda/rope.cu:61-84`）。CUDA の native RoPE helper も同じ設定値を受け取ります（`include/strata/kernels/rope_scaling.hpp:106-116, 148-160`）。KV cache の K は RoPE 適用後に保存されるため、実行中に値を変える per-request 設定ではありません（`src/program/generate.cpp:450-454`）。

## 適用条件と副作用

- `--rope-scaling linear` / `yarn` で角度縮小率として適用されます。`none` は他の RoPE scaling knob を無効化し、正の `--rope-freq-scale` が指定されていれば stderr に「no rope scaling is active ... have no effect」という注記を出します。周波数 base だけは `none` でも保持されます（`src/program/generate.cpp:3708-3719`; `include/strata/kernels/rope_scaling.hpp:102-116`）。
- YaRN で `ext_factor` が非0の場合は、角度補正に加えて magnitude scale に `1 + 0.1 * ln(1 / freq_scale)` が掛かります。その結果が有限かつ正でない場合、設定全体の検証に失敗します。`ext_factor` は `--yarn-ext-factor` または YaRN の自動既定値で決まります（`include/strata/kernels/rope_scaling.hpp:84-90, 169-183`; `src/program/generate.cpp:3702-3707`）。
- 値は起動時に RoPE table / kernel の設定へ反映されます。オプション自体が直接ファイルやネットワークを操作する処理は確認できません。
- `--native` が Qwen3.6-35B-A3B の専用実装へ振り分けられる build では、通常 parser より前に別実装へ dispatch されます（`src/program/generate.cpp:2393-2407`）。この checkout の `src/qwen35` には `--rope-freq-scale` の参照が見当たらず、その専用経路での受理・効果は確認できません。

## 出力とエラー

- 値が欠落した場合は parser が stderr に不足を表示して終了コード 2 で終了します（`src/program/generate.cpp:2418-2421`）。
- NaN / 無限大は stderr に `a rope scaling knob is not a finite number`、負値は `invalid rope scaling knob` を出し、終了コード 2 で終了します（`src/program/generate.cpp:3328-3349`）。
- scaling type が有効で、解決した構成が不正な場合は `invalid rope scaling configuration` と理由・解決値を stderr に出し、終了コード 2 で終了します（`src/program/generate.cpp:3721-3729`; `include/strata/kernels/rope_scaling.hpp:169-183`）。
- scaling が有効なときは解決後の type、factor、frequency scale、base、magnitude scale、`--max-context` と学習済み context を stderr に表示します。context が学習済み範囲内でも設定値は各角度に適用される旨の注記があります（`src/program/generate.cpp:3731-3750`）。

## 根拠

- parser 値の保持と help 表示: `src/program/generate.cpp:450-463, 867-877, 2446-2450`
- missing value 処理と RoPE knob validation: `src/program/generate.cpp:2416-2421, 3312-3349`
- GGUF / CLI の設定解決、none 時の扱い、起動時出力: `src/program/generate.cpp:3642-3647, 3682-3750`
- frequency scale の自動解決と有効性検査: `include/strata/kernels/rope_scaling.hpp:77-90, 102-116, 164-183`
- table 内の角度適用: `src/kernels/cuda/rope.cu:61-84`
- CLI の文書 scope: [`docs/cli/README.md`](../../README.md) の `strata-engine` 節。調査基準: [`docs/cli/001_investigation.md`](../../001_investigation.md)

調査範囲は上記 revision の checkout に含まれる parser・設定解決・RoPE 実装です。同一 revision の CLI `--help` 実行、build、GPU 実行、性能測定、テストは行っていません。Release 配布物との照合も行っていません。
