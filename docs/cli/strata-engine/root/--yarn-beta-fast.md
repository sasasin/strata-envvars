# `--yarn-beta-fast`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン、root 引数） |
| オプション | `--yarn-beta-fast` |
| 別名 | なし |
| 値 | `F`。有限な正の数 |

## 役割

YaRN の RoPE 補正窓で、学習済み角度を保つ側の境界を決める値です。`RopeScaling::corr_dims()` がこの値を使って補正窓の開始ペアを算出し、補正が有効な回転設定では回転テーブル／解析カーネルに渡します。よく使われるのは YaRN 設定ですが、設定タイプが `none` の場合は値がリセットされ、効果はありません。

## 使い方

```sh
# モデルのトークン列を入力し、YaRN の fast beta を 24 にして推論する例
strata --pack MODEL.gguf --tokens 1,2,3 --max-new 1 --rope-scaling yarn --rope-scale 2 --yarn-beta-fast 24
```

`--yarn-beta-fast` は単独で RoPE scaling を有効にしません。`--rope-scaling` が省略された場合はモデルの RoPE 設定が参照されるため、設定タイプと拡張条件もあわせて確認してください。

## 値と既定値

- parser は次の argv 要素を `std::atof()` で `double` に変換します。値を省略すると `--yarn-beta-fast needs a value` を stderr に出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3846, 3879`）。
- 未指定時は `32.0` です。明示値には有限性と `> 0` が要求されます。0、負数、`NaN`／無限大、および数値に変換できず 0 になる文字列は拒否されます（`engine/src/program/generate.cpp:800, 5243-5264`）。
- 同じオプションを複数回指定した場合、parser は各値を順に代入し、重複を拒否しないため最後の値が残ります（`engine/src/program/generate.cpp:3842-3847, 3879`）。
- 解析時にモデルの GGUF から読み取る RoPE 項目は type、base、factor、original context であり、beta-fast はこの読み取り一覧にありません。そのためこの parser の既定値は 32 で、明示指定値は常にそれを置き換えます（`engine/src/program/generate.cpp:5650-5673, 5724-5726`）。

## 実行時の動作

CLI 値は `rope_cfg.beta_fast` に設定されます。補正窓の開始境界は `floor(rope_yarn_corr_dim(n_rot, orig_ctx, beta_fast, freq_base))` から求められます。`kernel_args()` は `none` 以外の設定でこの境界を補正カーネル引数に含め、回転テーブル経路では `build_rope_table()` が設定を使って cos/sin 値を作ります（`engine/src/program/generate.cpp:5721-5726`; `engine/include/strata/kernels/rope_scaling.hpp:92-116`; `engine/src/core/layer.cpp:961-970`）。

オプション自体は scaling type を切り替えません。型は明示された `--rope-scaling` が優先され、省略時はモデルの RoPE type が使われます。`--yarn-ext-factor` が省略時には YaRN で 1、それ以外で 0 となるため、通常の YaRN では補正境界が使われます。明示的に ext-factor を 0 にすると補正は止まり、beta-fast の境界は計算されても回転結果に影響しません（`engine/src/program/generate.cpp:5700-5726`; `engine/include/strata/kernels/rope_scaling.hpp:148-160`）。

設定は起動時に一度解決され、セッション初期化で回転テーブルが作られます。リクエスト単位で切り替わる設定ではありません（`engine/include/strata/kernels/rope_scaling.hpp:186-190`; `engine/src/core/layer.cpp:961-970`）。

## 適用条件と副作用

- `--rope-scaling none` を選ぶと scaling 設定全体が初期値に戻るため、このオプションの正の値は効果を持ちません。ただし reset より前に CLI 値の有限性・正数チェックが行われるので、`none` でも無効値は拒否されます（`engine/src/program/generate.cpp:5243-5264, 5727-5739`）。なお `none` 時の通知判定は beta-fast 単独の指定を含まないため、正の値だけを指定しても無効化の注記が出ない場合があります（同 `5731-5739`）。
- `engine/sycl/src/program/generate.cpp` にも同じ既定値・parser・validation・設定反映があります（`484, 1918, 2657-2679, 2995-3000`）。ビルドされた実行ファイルの backend によって該当する処理本体が異なります。
- 値の適用は起動時の RoPE 設定と回転テーブル／カーネル引数に限られます。ファイルへの書き込みやネットワークアクセスをこのオプションが行う処理は確認できません。

## 出力とエラー

- 値がない場合は stderr に `--yarn-beta-fast needs a value` を出して終了コード 2 です（`engine/src/program/generate.cpp:3844-3846`）。
- `NaN`／無限大など有限でない値は stderr に `a rope scaling knob is not a finite number (...)`、0 以下の値や数値変換されない文字列は stderr に `invalid rope scaling knob (...)` を出して、いずれも終了コード 2 です（`engine/src/program/generate.cpp:5243-5264`）。
- 値が有効で scaling type が `none` 以外なら、起動時に解決された scaling の概要が stderr に出ます。type が `none` なら beta-fast 指定だけを理由とする出力はありません（`engine/src/program/generate.cpp:5727-5739, 5759-5778`）。

## 根拠

- `engine/src/program/generate.cpp:790-801` — parser の Options 値と既定値。
- `engine/src/program/generate.cpp:3842-3847, 3879` — 引数読み取り、数値変換、値省略時の失敗。
- `engine/src/program/generate.cpp:5243-5264` — 有限性と正数の検証、エラー出力・終了コード。
- `engine/src/program/generate.cpp:5650-5673, 5700-5759` — モデル metadata の読み取り範囲、設定の優先と beta-fast の反映、`none` の reset。
- `engine/include/strata/kernels/rope_scaling.hpp:92-116, 148-160, 164-190` — 補正窓の計算、カーネル引数・設定検証・起動時設定。
- `engine/src/core/layer.cpp:961-970` — 解決済み設定を使った回転テーブル作成と device 転送。
- `engine/sycl/src/program/generate.cpp:484, 1918, 2657-2679, 2995-3000` — SYCL parser と同等の既定値・検証・設定反映。
