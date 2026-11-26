# `--rope-scaling`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--rope-scaling` |
| 別名 | なし |
| 値 | `none`、`linear`、`yarn` のいずれか（大文字小文字を区別） |

## 役割

RoPE（回転位置埋め込み）の位置角を選び、学習時の範囲を超えるコンテキストを扱う方法を指定します。`linear` は角度を一様に縮小する線形補間、`yarn` は YaRN の補間・外挿を使います。`none` は学習時の回転を維持します。スケーリング設定は実行中に変更できず、プロセス全体で一つです。

## 使い方

```sh
# YaRN を使い、ほかの RoPE パラメーターは既定値にする例
strata generate --pack /models/pack --ple-gguf /models/ple.gguf \
  --tokens "1,2,3" --max-context 524288 --rope-scaling yarn
```

線形補間なら `yarn` を `linear` に、モデルまたは他の実行設定によるスケーリングを無効にする場合は `none` に置き換えます。拡張倍率などは関連する `--rope-scale`、`--rope-freq-scale`、`--yarn-*` オプションで指定します。

## 値と既定値

- 値は必須です。parser は次の引数を文字列として受け取り、後段で `none`、`linear`、`yarn` の完全一致を検証します。省略時に使われる値は空文字列で、明示指定なしを表します。
- 未指定なら、ネイティブモデルの GGUF に `rope.scaling.type` があればその値を使い、なければ `none`（構造体の既定値）です。GGUF の RoPE キーを読み込む経路は `--native` 使用時です。
- 明示した値は GGUF の type より優先されます。明示した `none` は GGUF のスケーリングを無効にします。
- 同じ引数を複数回指定すると、parser は各指定で同じフィールドを書き換えるため最後の値が残ります。値を省いた場合は `--rope-scaling needs a value` を stderr に出し、終了コード 2 で終了します。

## 実行時の動作

parser は値を `std::string` に格納し、初期検証で `none`、`linear`、`yarn` 以外を拒否します。RoPE の設定はモデルメタデータと関連オプションを組み合わせた後、`session_init` がテーブルを作り、GPU graph が kernel 引数を捕捉する前にプロセス設定として一度登録されます。KV cache の K は RoPE 適用後のため、実行途中で設定を変える機能はありません。

設定が `linear` または `yarn` の場合、既定では `--rope-scale` の値、GGUF の scaling factor、最後に 1.0 の順で倍率が決まります。倍率 1.0 は明示指定でもモデル値より優先されます。周波数 base と元の学習コンテキストも、明示された関連オプション、GGUF 値、構造体既定値の順で決まります。`--rope-freq-scale` は 0 のとき倍率の逆数になります。YaRN の ext factor は未指定なら YaRN で 1、それ以外で 0 です。`--rope-scale` や `--yarn-*` の範囲・意味は各オプションの文書を参照してください。

`none` ではスケーリング用の倍率・補正パラメーターは適用されず、設定が既定の恒等回転に戻ります。周波数 base は回転そのものに使うため保持されます。`linear` / `yarn` の計算は RoPE テーブルに焼き込まれ、解析的に回転する経路では kernel に渡されます。いずれもコンテキストが学習範囲内でも指定設定が全位置に適用されます。

## 適用条件と副作用

- 設定は engine の起動時に解決され、同じ実行プロセスの RoPE テーブルと回転 kernel に適用されます。実行中の切り替えはできません。
- `none` を選び、学習済みコンテキストより大きな `--max-context` を指定した場合、学習範囲外の位置角を使う旨と `yarn` を使う例の WARNING が stderr に出ます。コンテキストが学習済み範囲内かどうかにかかわらず、`linear` / `yarn` を選ぶとスケーリングは全位置に適用されます。
- `none` と同時に倍率・周波数 scale・YaRN 補正を設定すると、それらは無効になる旨の note が stderr に出ます。ただし範囲検証は先に行われるため、不正な数値が `none` によって許容されるわけではありません。
- `--rope-scaling` 自体はファイルを書き換えず、モデル GGUF は読み取り元として参照されます。

## 出力とエラー

- 不正な値では `strata generate: --rope-scaling must be none, linear or yarn (got '…')` を stderr に出し、終了コード 2 で終了します。
- 値がない場合も stderr にエラーを出し、終了コード 2 で終了します。
- `--native` で読む GGUF の `rope.scaling.type` が `none`、`linear`、`yarn` 以外で、CLI による明示指定もない場合は、未対応値を stderr に出して終了コード 2 で終了します。
- parser 通過後、RoPE 関連設定を有限値・正の値などの条件で検証します。解決後の設定が不正なら理由と設定値を stderr に出し、終了コード 2 で終了します。
- 有効な `linear` / `yarn` では、解決した種類、倍率、周波数 scale、base、補正値と `--max-context` を stderr に表示します。必要に応じて学習済み範囲内の note や magnitude correction の note も出ます。

## 根拠

- `engine/src/program/generate.cpp:788-797` — RoPE オプション群の既定値、プロセス単位の設定と優先順位。
- `engine/src/program/generate.cpp:1208-1214`、`1267-1279` — `strata generate` の構文と help 上の値・既定値説明。
- `engine/src/program/generate.cpp:3842-3847`、`3870-3879` — parser が値を必須引数として文字列に格納し、関連オプションも読み取る箇所。
- `engine/src/program/generate.cpp:5227-5265` — 値の許可リスト、有限性と関連数値の範囲検証、エラーと終了コード。
- `engine/src/program/generate.cpp:5641-5646`、`5667-5673`、`5700-5725` — GGUF キー取得条件、CLI とモデル値の優先順位、解決処理。
- `engine/src/program/generate.cpp:5727-5759` — `none` の無効化処理、長いコンテキストへの警告、解決設定の検証と登録。
- `engine/src/program/generate.cpp:5760-5778` — スケーリング状態や条件付き note の stderr 出力。
- `engine/include/strata/kernels/rope_scaling.hpp:30-35`、`48-75`、`164-190` — 設定の固定条件、値の構造体既定値、共通の最終 validation。
- `engine/src/core/layer.cpp:961-973` — 登録済み設定を使った RoPE テーブルの生成と登録。
