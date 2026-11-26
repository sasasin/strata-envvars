# `--remote-expert-opt`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--remote-expert-opt` |
| 別名 | なし |
| 値 | なし。指定すると真になるフラグ |

## 役割

helper GPU に配置した remote expert の decode で、expert ごとの出力行を CUDA0 へ個別に返す代わりに、helper 側で token ごとに集約した結果を返す最適化を有効にします。Strata は helper cache の作成や expert の割り当ても別途必要とし、このフラグ単独では remote cache を作りません。

## 使い方

```sh
# CUDA0 の expert cache に入らない expert を CUDA1 にも配置し、serve decode で最適化を有効にする
strata generate MODEL.gguf --serve --expert-profile PROFILE --expert-cache 256 \
  --expert-cache-device1 128 --remote-expert-opt
```

`MODEL.gguf` と `PROFILE` は実際に使うモデルと expert profile に置き換えてください。helper expert cache を使うには、expert profile、CUDA0 の expert cache、expert pool が必要です。

## 値と既定値

値を取りません。既定値は無効（`false`）で、指定すると `remote_expert_opt` が真になります。複数回指定した場合も同じ真値を設定するだけです。parser にこのフラグ固有の数値や文字列の validation はありません。

## 実行時の動作

parser は `strata generate` の引数として受理し、`--serve` がなければ stderr に `strata generate: --remote-expert-opt requires --serve` を出して終了コード 2 で終了します。

`--expert-cache-device1`（CUDA1）の slot 数が正の場合に限り `RemoteExpertOpt` を生成し、remote expert cache に接続します。CUDA2/3 の helper cache を指定していても CUDA1 cache がなければ最適化オブジェクトは作られず、このフラグによる最適化は実行されません。helper cache 自体には `--expert-profile`、正の CUDA0 `--expert-cache`、expert pool が必要です。これらを満たさない場合は remote experts の起動を拒否し、stderr に条件を表示して終了コード 2 で終了します。

最適化が有効な経路では、helper GPU が expert の出力を token 単位で加重集約し、集約結果と helper が処理した行の mask を pinned host memory に返します。CUDA0 側は helper が担当した行を CPU 側の行コピーから除外し、最後に集約済みの値を出力へ加算します。remote expert の読み込み、GPU 計算、host/device memory の割り当てを伴います。CUDA0 cache だけの実行や helper cache を伴わない layer split では効果はありません。

## 適用条件と副作用

- `--serve` が必要です。通常の非 serve 実行では validation error になります。
- 実際に最適化オブジェクトが作られる条件は `--expert-cache-device1` の正の slot 数です。remote cache の通常の起動条件として、profile、CUDA0 cache、expert pool も必要です。
- SYCL engine は未対応です。helper cache が構成されると初期化関数が未対応理由を返し、generate 側が stderr に表示して終了コード 1 で終了します。
- `--pipeline-windows` を使う経路では verifier の `capture_all` が `--remote-expert-opt` を拒否します。
- 最適化オブジェクトがある場合、`--adapt-async` の自動選択条件から外れ、adapt overlap も無効になります。

## 出力とエラー

- serve 以外: `strata generate: --remote-expert-opt requires --serve`（stderr、終了コード 2）。
- remote expert の profile / CUDA0 cache / pool 条件不足: `strata generate: remote experts need --expert-profile, a CUDA0 expert cache and the expert pool`（stderr、終了コード 2）。
- remote expert の open 失敗: `strata generate: <原因>`（stderr、終了コード 1）。
- SYCL engine: `--remote-expert-opt is not supported by the SYCL engine (no second-device expert tier)`（stderr、終了コード 1）。
- pipeline windows の capture: `verify: pipelined windows do not serve --remote-expert-opt` を返します。呼び出し側での表示や最終終了コードは、調査した verifier の範囲では確認できませんでした。

## 根拠

- `engine/src/program/generate.cpp:1423` — help 上のフラグ説明と serve mode の注記。
- `engine/src/program/generate.cpp:904-907,3994` — option state の既定値と parser の受理方法。
- `engine/src/program/generate.cpp:5267-5282` — remote cache 関連 validation と serve 必須条件、エラー時の終了コード。
- `engine/src/program/generate.cpp:10123-10131,10197-10207,10230` — CUDA1 cache を条件とする object 生成、helper cache への接続・open、初期化失敗時の出力と終了コード。
- `engine/src/core/remote_expert_opt.cu:57-69,84-115,118-130` — pinned host buffer と helper GPU buffer の確保、重み付き集約、helper 担当行 mask、結果の combine。
- `engine/src/core/remote_experts.cpp:320-352,361-391` — 最適化 metadata の転送、helper 側 reduce、集約結果の受け取り。
- `engine/src/core/verify.cpp:2921-2922,2966-2967,4079-4083,5899-5903` — helper 行の除外、結果の合成、decode 時の開始・終了、pipeline capture の拒否。
- `engine/src/program/generate.cpp:11784-11794,11801-11811,15122-15129` — `--adapt-async` 自動選択と adapt overlap との相互作用。
- `sycl/src/core/remote_expert_opt_stub.cpp:1-15` — SYCL 未対応理由と初期化エラー。
- `engine/cmake/strata_gpu_engine.cmake:305-314` と `sycl/CMakeLists.txt:290-299` — GPU engine と SYCL engine の構成で異なる実装を選ぶ箇所。
