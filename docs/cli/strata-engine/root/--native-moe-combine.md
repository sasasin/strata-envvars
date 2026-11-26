# `--native-moe-combine`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（トップレベルのエンジン引数） |
| オプション | `--native-moe-combine` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると有効 |

## 役割

MoE 層の routed expert 出力を router weight で合成し、shared expert 出力を加える処理を、標準経路から実験的な CUDA native combine カーネルへ切り替える。実装上は routed 部分の重み付き和に shared 出力を一度加算する。MoE 層を実行しないモデル・経路では、この切替による処理は発生しない。カーネルの算術契約とフラグの初期状態は `engine/src/kernels/cuda/native_moe.cu:33-38,41-74`、標準 MoE 経路の切替は `engine/src/core/layer.cpp:520-529`。

## 使い方

`strata generate` の引数として指定する。以下は必須の prompt token を含む構文例であり、実行には対象モデルと通常のモデル設定が必要。

```sh
strata generate --pack DIR --tokens "1,2,3" --native-moe-combine
```

usage は `--pack DIR` と `--tokens LIST` を示し、parser はこのフラグをそのまま受理する（`engine/src/program/generate.cpp:1208-1214,3914-3918`）。

## 値と既定値

値・別引数は不要。オプション状態の初期値は `false` で、指定時に `true` へ設定される。複数回指定しても同じ `true` の代入を繰り返すだけで、専用の重複指定エラーはない（`engine/src/program/generate.cpp:783,3917`）。

未指定時は標準 MoE combine を使う。`--native <model>` を指定した場合は、このフラグを含む native 推論機能群がまとめて有効化されるため、`--native-moe-combine` を別途指定しなくても有効（`engine/src/program/generate.cpp:5155-5164`）。

## 実行時の動作

起動時にフラグ値を `native_moe_combine_set_enabled` へ設定する。通常の層処理では有効時に `native_moe_combine(...)`、無効時に `moe_combine(...)` を呼び、例外を層名付きのエラーへ変換する（`engine/src/program/generate.cpp:6114-6119`; `engine/src/core/layer.cpp:520-529`）。

native カーネルは各出力要素について routed expert の `parts[i] * weights[i]` を合計し、shared 出力があればその値を一度加える。shared は router weight で重み付けされない。通常カーネルは入力 F32 行を読み、出力を書き込む。CUDA 実装には単一トークン用と複数トークン用があり、検証窓の複数行では `dec_batch && n > 1 && native_moe_combine_enabled()` の条件で複数行を一度に処理する（`engine/src/kernels/cuda/native_moe.cu:41-74,203-218`; `engine/src/core/verify.cpp:2956-2959`）。

通常経路では `k`（使用 expert 数）が 1〜15、埋め込み幅が正で `int` の範囲内である必要があり、CUDA 実装は非 null の stream、妥当なアラインメント、出力と入力各 span の非重複も要求する。条件を満たす場合でも、`k` がビルド時の expert 数 `KU` と一致し、shared があり、幅が 4 要素単位で、parts/shared/output が 16 バイト整列しているときに限り、専用の vec4 カーネルへ進む。それ以外は通常カーネルを使う（`engine/src/kernels/cuda/native_moe.cu:35-36,162-185,203-218`）。ヘッダーの契約も単一行の `k` を 1〜15 と定めている（`engine/include/strata/kernels/native_moe.hpp:10-17`）。

## 適用条件と副作用

- フラグは起動時にグローバルなカーネル選択状態へ設定される。ヘッダーはセッション構築・CUDA graph capture の前に設定するよう定め、既に capture 済みの graph は後からフラグを変更しても選択カーネルが変わらないとしている（`engine/include/strata/kernels/native_moe.hpp:5-8`; `engine/src/program/generate.cpp:6114-6119`）。
- `--native` プリセットとの相互作用は上記「値と既定値」の通り。このプリセットは `--stream-token` や複数の native 機能も同時に有効化する（`engine/src/program/generate.cpp:5160-5164`）。
- CUDA の verify 窓では、resident/CPU 側 expert hit の加算をcombineに折り込む専用経路や shared gate をcombine内で処理する経路もある。hit 経路は `k == KU`、shared が存在、幅が4要素単位、該当バッファが16バイト整列、token 数が1〜8（wide buildでは上限16）などの条件で選択され、条件外では通常のhit加算経路へ戻る。shared gate 経路は `STRATA_LFUSE` 等を含む別条件であり、いずれも同フラグ有効が条件の一つ（`engine/src/core/verify.cpp:1522-1524,2859-2861,2934-2959`; `engine/src/kernels/cuda/native_moe.cu:187-201`; `engine/include/strata/kernels/native_moe.hpp:18-35`）。
- カーネルは指定 stream に CUDA kernel を enqueue し、ソース上でホスト側の明示的なメモリ確保や同期は行わない。実装は一時ファイル等を生成しない（`engine/src/kernels/cuda/native_moe.cu:162-185,203-218`; `engine/include/strata/kernels/native_moe.hpp:10-17`）。

## 出力とエラー

parser はこのフラグの値検証を行わない。未知の引数は `unknown argument: ...` を stderr に出し、usage を表示して終了コード 2 で返す。`--native-moe-combine` 自体は現行 parser で認識される（`engine/src/program/generate.cpp:3917,4268-4273`）。

native CUDA 関数は stream・寸法・expert 数・span の条件違反を `std::invalid_argument`、CUDA launch error を `std::runtime_error` として返す（`engine/src/kernels/cuda/native_moe.cu:162-185,203-218`）。通常 MoE 層の呼び出し元は例外文を `blk.<layer>.moe_combine: ...` にして失敗を返す（`engine/src/core/layer.cpp:526-529`）。この調査では実行時の標準出力・終了コードへの伝播を別途実行して確認していない。

## 根拠

- parser、既定値、usage、`--native` による暗黙有効化、起動時設定: `engine/src/program/generate.cpp:783,1208-1214,1244-1250,3914-3918,5155-5164,6114-6119`
- combine の選択と層エラー変換: `engine/src/core/layer.cpp:520-529`
- CUDA 算術・入力条件・launch error: `engine/src/kernels/cuda/native_moe.cu:33-38,41-74,162-185,203-218`
- verify の複数 token/hit 適用条件: `engine/src/core/verify.cpp:1522-1524,2859-2861,2934-2959`
- API 契約と capture timing: `engine/include/strata/kernels/native_moe.hpp:5-17`
