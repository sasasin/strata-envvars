# `--native-rope`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジンの root parser） |
| オプション | `--native-rope` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

テキスト経路の rotary position embedding (RoPE) に、実験的な native CUDA 算術を選びます。標準経路の RoPE ではなく `native_rope_apply` を使う切り替えです。エンジンの usage も「experimental pinned text-only CUDA rotary arithmetic」と説明しています（`src/program/generate.cpp:852`）。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --native-rope
```

`--tokens` は必須のトークン ID 列です。実際の入力 pack とトークン列に置き換えてください（`src/program/generate.cpp:806-812`）。

## 値と既定値

- 引数 parser は `--native-rope` を見つけると `native_rope` を `true` にします。初期値は `false` で、通常は指定しない限り native RoPE を使いません（`src/program/generate.cpp:464`, `src/program/generate.cpp:2496`）。
- 値を要求せず、同じフラグを複数回指定しても真偽値を再度 true にするだけです。フラグの直後に値を置く構文ではありません。余分な値が独立した引数として parser に渡ると未知引数扱いになります（`src/program/generate.cpp:2416-2421`, `src/program/generate.cpp:2496`, `src/program/generate.cpp:2787-2792`）。
- parser 段階でこのフラグ固有の数値 validation はありません。RoPE 関数側は入力ポインタ、行数、幅、回転幅、scaling、アラインメント、stream を検証します（`src/kernels/cuda/native_rope.cu:189-202`）。

## 実行時の動作

起動時に parser の値を `native_rope_set_enabled` に設定します（`src/program/generate.cpp:3941`）。native RoPE が有効な場合、通常レイヤーの QSA 正規化後の回転処理は `native_rope_apply`、無効の場合は `rope_neox_apply` に分岐します（`src/core/layer.cpp:1131-1140`）。検証・MTP の RoPE 経路にも同じ native/標準の分岐があります（`src/core/verify.cpp:1559-1564`, `src/core/mtp.cpp:947-956`, `src/core/mtp.cpp:989-994`）。

native 実装は `RopeScaling` の値を kernel 引数に変換して CUDA kernel を起動し、CUDA launch error は例外にします（`src/kernels/cuda/native_rope.cu:204-217`）。RoPE scaling の値は別オプションやモデル GGUF metadata から組み立てられ、このフラグ自体は scaling 値を変更しません（`src/program/generate.cpp:3669-3707`）。詳細は [`--rope-scaling`](--rope-scaling.md)、[`--rope-scale`](--rope-scale.md)、[`--rope-freq-base`](--rope-freq-base.md) などの文書を参照してください。

`--native SHARD1` を指定した場合、native preset の初期化が `native_rope` を含む native 経路群を自動で有効化します（`src/program/generate.cpp:3263-3268`）。

## 適用条件と副作用

- 実装関数は幅 `128` または `256`、回転幅 `64`、行数 `1..65535`、有効な scaling、4-byte aligned な F32 入出力・position 配列と明示 stream を要求します。入出力の部分重複や position 配列との重複も拒否します（`src/kernels/cuda/native_rope.cu:189-202`）。この関数レベルの条件を満たさない場合、標準 RoPE への fallback は実装されていません。
- `--native-qsa` も有効で、形状が利用条件に合う場合は QSA の RMSNorm と RoPE を一つの kernel にまとめる経路が選ばれます。`STRATA_NO_NORM_ROPE` はこの融合可否に影響しますが、native RoPE 自体の有効化フラグではありません（`src/core/verify.cpp:1566-1572`, `src/kernels/cuda/native_rope.cu:175-186`）。
- `STRATA_ROPE_TABLE=1` が設定され、同じ scaling の RoPE table が登録済みなら、native kernel はその table を使います。未設定・不一致なら別の算術 kernel 経路を起動します。この環境変数は `--native-rope` の代替ではありません（`src/kernels/cuda/native_rope.cu:151-171`, `src/kernels/cuda/native_rope.cu:204-215`）。
- フラグの説明は text-only です。一方、parser に `--vision` との明示的な排他検証はなく、engine 起動時には vision 用 mRoPE table も設定されます（`src/program/generate.cpp:852`, `src/program/generate.cpp:3942-3957`）。この調査では `--native-rope --vision` の対応範囲や正しさまでは確認できません。
- 実行時の副作用は GPU 上の RoPE kernel の選択・起動と、その結果の token/query/key 表現への反映です。ファイルやネットワークへの書き込みをこのオプションが行う処理は確認できません。

## 出力とエラー

- parser が未知の引数を受け取ると `unknown argument: ...` を stderr に出し、usage を stderr に表示して終了コード `2` を返します（`src/program/generate.cpp:2787-2792`）。
- native 関数は引数・shape 不一致で `std::invalid_argument`、CUDA kernel 起動エラーで `std::runtime_error` を送出します（`src/kernels/cuda/native_rope.cu:191-217`）。QSA の該当処理は例外文を `err` に格納して失敗を返し、MTP の該当処理も `mtp: ...` を `err` に格納して失敗を返します（`src/core/layer.cpp:1131-1141`, `src/core/mtp.cpp:982-986`）。最終的な利用者向け表示と終了コードは呼び出し元・実行モードに依存するため、このオプション固有の一律な出力としては確認できません。

## 根拠

- parser の既定値・help・受理: `src/program/generate.cpp:464`, `src/program/generate.cpp:852`, `src/program/generate.cpp:2416-2421`, `src/program/generate.cpp:2496`
- `--native` からの自動有効化・初期設定: `src/program/generate.cpp:3263-3268`, `src/program/generate.cpp:3941`
- native/標準 RoPE の分岐: `src/core/layer.cpp:1131-1140`, `src/core/verify.cpp:1559-1564`, `src/core/mtp.cpp:947-956`, `src/core/mtp.cpp:989-994`
- shape validation・kernel launch・table 経路: `src/kernels/cuda/native_rope.cu:151-217`
- 調査対象 checkout の開始時状態: `git rev-parse HEAD` は `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、`git status --short --branch` は `## main...origin/main`（未コミット変更なし）。
