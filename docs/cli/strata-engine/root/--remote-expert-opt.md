# `--remote-expert-opt`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数） |
| オプション | `--remote-expert-opt` |
| 別名 | なし |
| 値 | 値なしの boolean フラグ。既定値は無効 |

## 役割

serve 中に helper GPU の expert cache が担当する expert の出力を helper 側で重み付き合算し、helper からホストへ返す行数を減らす最適化です。主 GPU と helper GPU を使う既存の remote-expert decode 経路に対する追加最適化であり、helper cache 自体を有効にするオプションではありません。help は serve mode 用と説明しています（`src/program/generate.cpp:1003-1008`）。

## 使い方

helper GPU 1 の cache を使う serve 起動例です。`PROFILE.gguf` と `MODEL.gguf` は利用環境の実ファイルに置き換えます。

```sh
strata --model MODEL.gguf --serve \
  --expert-profile PROFILE.gguf --expert-cache 4096 \
  --expert-cache-device1 2048 --remote-expert-opt
```

この機能を有効化するには `--serve` が必要です。また helper cache の初期化には expert profile、CUDA 0 の expert cache、expert pool が必要です（`src/program/generate.cpp:3365-3367`, `src/program/generate.cpp:6662-6670`）。

## 値と既定値

値を取りません。parser は引数が `--remote-expert-opt` と一致したとき boolean を `true` にします。既定値は `false` です。同じフラグを重ねて指定しても値は変わりません（`src/program/generate.cpp:561`, `src/program/generate.cpp:2568`）。

## 実行時の動作

フラグと `--expert-cache-device1` の枠数が正の場合に最適化オブジェクトを生成します。remote cache の各 GPU で通常の expert 計算を行った後、最適化が active なら helper 上で各 token の expert 行を routing weight で加算し、合算結果をホストへ返します。通常の経路では helper が所有する個別行を返すため、最適化経路では CPU 側コピー時に helper 所有行を除外し、最後に helper の合算結果を出力へ加えます（`src/program/generate.cpp:6662-6666`, `src/core/remote_expert_opt.cu:23-31`, `src/core/remote_expert_opt.cu:99-131`, `src/core/remote_experts.cpp:319-320`, `src/core/remote_experts.cpp:348-355`, `src/core/remote_experts.cpp:359-389`, `src/core/verify.cpp:2156-2160`, `src/core/verify.cpp:2200-2201`）。

`--remote-expert-opt` だけを指定し helper cache を構成しない場合、フラグ自体は `--serve` 以外の追加エラーになりませんが、最適化オブジェクトが作られず、この最適化は動きません（`src/program/generate.cpp:6662-6666`）。

## 適用条件と副作用

- `--serve` なしでは拒否され、stderr に `strata generate: --remote-expert-opt requires --serve` を出して終了コード 2 になります（`src/program/generate.cpp:3365-3367`）。
- helper cache を使う場合は `--expert-profile`、正の CUDA 0 expert cache、および expert pool が必要です。条件を満たさないと stderr に `remote experts need --expert-profile, a CUDA0 expert cache and the expert pool` を出して終了コード 2 になります（`src/program/generate.cpp:6666-6670`）。
- helper GPU の列挙・cache 展開や remote expert の計算に GPU、ホストメモリ、デバイス間転送を使います。初期化失敗はそのエラーを stderr に出して終了コード 1 になります（`src/program/generate.cpp:6736-6746`, `src/program/generate.cpp:6769`）。
- `--pipeline-windows` が layer split と helper cache の併用で有効になっている場合、エンジンは理由を stderr に表示して pipeline windows を無効化します（`src/program/generate.cpp:4273-4288`）。
- layer split 上の `--batch-mtp` は helper cache またはこの最適化と組み合わせると警告を出して無効化されます（`src/program/generate.cpp:5315-5321`）。
- `--adapt-async 1` と適応 overlap 経路は、この最適化が実際に生成された場合に無効になります（`src/program/generate.cpp:8077-8092`, `src/program/generate.cpp:10099-10108`）。
- Remote expert 最適化を使う verifier は pipelined windows の capture を受け付けず、`verify: pipelined windows do not serve --remote-expert-opt` を返します（`src/core/verify.cpp:4174-4180`）。通常の parser 後段で該当 pipeline windows が無効化される経路とは別に、capture 呼び出し側に残る防御条件です。

## 出力とエラー

このフラグ単独では有効化メッセージを出しません。上記の適用条件エラーは stderr に出力されます。helper cache の open、最適化領域の初期化、CUDA 処理に失敗した場合はエラー文字列を stderr に出して起動・処理を失敗させます（`src/program/generate.cpp:3365-3367`, `src/program/generate.cpp:6736-6746`, `src/program/generate.cpp:6769`）。この調査では各 CUDA backend での具体的な失敗内容・終了タイミングまでは実行確認していません。

## 根拠

- parser、既定値、help 表示、`--serve` の validation: `src/program/generate.cpp:561`, `src/program/generate.cpp:1003-1008`, `src/program/generate.cpp:2568`, `src/program/generate.cpp:3365-3367`
- helper cache 条件と最適化初期化: `src/program/generate.cpp:6662-6670`, `src/program/generate.cpp:6736-6746`, `src/program/generate.cpp:6769`
- helper 側の加算・転送量削減: `src/core/remote_expert_opt.cu:23-31`, `src/core/remote_expert_opt.cu:99-131`, `src/core/remote_experts.cpp:319-355`, `src/core/remote_experts.cpp:359-389`, `src/core/verify.cpp:2156-2160`, `src/core/verify.cpp:2200-2201`
- 他の実行経路との条件: `src/program/generate.cpp:4273-4288`, `src/program/generate.cpp:5315-5321`, `src/program/generate.cpp:8077-8092`, `src/program/generate.cpp:10099-10108`, `src/core/verify.cpp:4174-4180`
