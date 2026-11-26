# `--yarn-orig-ctx`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--yarn-orig-ctx` |
| 別名 | なし |
| 値 | 数値 `N`。内部では `double` として扱う。0 は既定値選択、負数・非有限値は拒否される。 |

## 役割

YaRN の RoPE 補正が基準にする、モデルの学習時コンテキスト長を指定します。値は起動時に解決され、同じプロセスの RoPE 設定全体に適用されます。エンジンは KV cache に RoPE 適用後の K を保持するため、リクエストごとに変更するオプションではありません（`engine/src/program/generate.cpp:789-792`）。

## 使い方

```sh
# 例: 学習時コンテキストを 131072 として YaRN scaling を使う
strata generate --native MODEL.gguf --tokens 1 --rope-scaling yarn --rope-scale 2 --yarn-orig-ctx 131072
```

`--native`、`--tokens`、`--rope-scaling`、`--rope-scale` は同じ `strata generate` parser で受理されます（`engine/src/program/generate.cpp:3851-3855,3871-3876,3924-3927`）。

## 値と既定値

- オプションを省略した場合、構成値は GGUF の `*.rope.scaling.original_context_length` が 1 以上ならその値、そうでなければ `RopeScaling` の既定値 262144 になります（`engine/src/program/generate.cpp:5650-5652,5668-5673,5719-5720`; `engine/include/strata/kernels/rope_scaling.hpp:66-75`）。
- `--yarn-orig-ctx 0` も省略時と同じく GGUF 値（利用可能な場合）へフォールバックし、GGUF 値がなければ 262144 です。したがって、0 では GGUF 値を明示的に上書きできません（`engine/src/program/generate.cpp:5719-5720`）。
- 0 より大きい有限値は CLI 指定値として優先されます。整数チェックや上限チェックはありません。RoPE scaling が有効な場合、最終構成の検査で 1 未満は拒否されます（`engine/src/program/generate.cpp:5243-5249,5260-5265,5719-5720`; `engine/include/strata/kernels/rope_scaling.hpp:177-183`）。
- 負数は CLI 検証で拒否されます。NaN や無限大も有限性検査で拒否されます。値の変換には `std::atof` が使われ、変換末尾や変換失敗を個別に検査する処理はありません（`engine/src/program/generate.cpp:3876,5243-5249,5260-5265`）。
- 同じ引数を複数回指定した場合、引数ループが同じフィールドを順に代入するため、最後の指定値が残ります（`engine/src/program/generate.cpp:3842-3847,3876`）。

## 実行時の動作

parser は値を `double` に変換して保持します。起動時、正の CLI 値があればそれを `rope_cfg.orig_ctx` に設定し、そうでなければ GGUF の元コンテキスト値を採用します。解決済み構成は RoPE scaling 設定として登録されます（`engine/src/program/generate.cpp:3876,5650-5673,5719-5720,5752-5759`）。

YaRN 補正窓の境界 `corr_dims` は `orig_ctx`、回転次元、`beta_fast` / `beta_slow`、周波数基底から算出され、その境界が解析カーネル引数にも渡されます。このため、この値は RoPE scaling が有効なときにどの回転ペアが学習済み角度を保つか、補間へ移るかを左右します（`engine/include/strata/kernels/rope_scaling.hpp:92-116`）。`--rope-scaling` が `none` の場合は scaling 設定を既定状態に戻すため、値は回転計算には使われません。ただし、`--max-context` が学習時長を超えた場合の警告判定には、リセット前の値が使われます（`engine/src/program/generate.cpp:5727-5747`）。

構成は起動時に検証されます。無効な解決済み RoPE 構成は stderr に `invalid rope scaling configuration` を出して終了コード 2 になります（`engine/src/program/generate.cpp:5749-5757`; `engine/include/strata/kernels/rope_scaling.hpp:169-183`）。

## 適用条件と副作用

- 実際に YaRN の補正窓へ作用するには RoPE scaling が `yarn` である必要があります。`linear` でも解決済み構成には値が保持されますが、YaRN 補正窓による効果はありません。`none` では回転に不使用です（`engine/src/program/generate.cpp:5719-5739`; `engine/include/strata/kernels/rope_scaling.hpp:92-116`）。
- モデル GGUF の元コンテキスト長は既定値としてのみ使われ、正の CLI 指定値が優先します。RoPE 構成は重みの読み込み後、session 初期化でテーブルを作る前に一度設定されます（`engine/src/program/generate.cpp:5649-5652,5719-5759`; `engine/include/strata/kernels/rope_scaling.hpp:185-193`）。
- ファイル生成やネットワークアクセスはこのオプションの処理では行いません。確認できた出力は、不正値のエラーと、RoPE 無効時の context 超過警告など stderr の診断です（`engine/src/program/generate.cpp:5260-5264,5737-5747,5752-5757`）。

## 出力とエラー

- 値が省略されると stderr に `--yarn-orig-ctx needs a value` を出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3846,3876`）。
- 非有限値は `a rope scaling knob is not a finite number`、負数などの範囲外値は `invalid rope scaling knob` を stderr に出し、終了コード 2 になります（`engine/src/program/generate.cpp:5243-5249,5260-5265`）。
- 未知の引数は stderr に `unknown argument` と usage を出し、終了コード 2 になります（`engine/src/program/generate.cpp:4268-4273`）。
- RoPE scaling が有効な状態で、最終的な `orig_ctx` が 1 未満なら構成検証で失敗します（`engine/include/strata/kernels/rope_scaling.hpp:177-183`; `engine/src/program/generate.cpp:5752-5757`）。

## 根拠

- `engine/src/program/generate.cpp:797,1277,3871-3880` — option の保存先、help 記述、parser 登録。
- `engine/src/program/generate.cpp:5243-5265` — 数値の有限性・範囲検証。
- `engine/src/program/generate.cpp:5650-5673,5719-5759` — GGUF 値との優先順位、`none` の扱い、構成検証と登録。
- `engine/include/strata/kernels/rope_scaling.hpp:66-75,92-116,169-183` — 既定値、補正窓への反映、解決済み構成の検証。
- SYCL parser にも同様の登録・変換・検証・構成設定があります（`engine/sycl/src/program/generate.cpp:481,865,1915,2657-2679,2943-2947,2993-2994,3017-3024`）。
