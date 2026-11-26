# `strata --native-ple-key`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--native-ple-key` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

量子化された PLE key を native dense projection としてロードし、PLE の key 投影に native MMVQ 経路を使います。通常の PLE key 経路では活性を Q8_0 に量子化して投影しますが、このフラグが有効で native key が接続された場合は、活性を Q8_1 に量子化して native MMVQ で投影します。実験的な切替です。

## 使い方

```sh
# pack と元モデルの GGUF shard を指定し、PLE key を native 経路にする
strata --pack /path/to/model.pack --ple-gguf /path/to/model-ple.gguf \
  --native-dense-gguf /path/to/model-00001-of-00002.gguf \
  --native-dense-gguf /path/to/model-00002-of-00002.gguf \
  --native-ple-key --tokens 1,2,3
```

`--native-dense-gguf` は native GDN/QSA projection の GGUF shard を指定する引数で、複数回指定できます。ここでは説明用のパスを使っています。実際には pack と対応する GGUF、PLE shard を指定してください。

## 値と既定値

値は不要です。省略時は無効（`false`）で、指定すると `true` になります。parser は引数文字列を `true` に設定するだけで、値の形式・範囲検査はありません。同じフラグを複数回置いても同じ boolean を再度 `true` にするため、追加の効果はありません。parser 定義は `engine/src/program/generate.cpp:782,3916`。

## 実行時の動作

`--native-dense-gguf` で渡された GGUF shard から native dense projection をロードするとき、このフラグが PLE key を対象に含める引数として渡されます。対象は `blk.1.ple_key.weight` の GGUF type 42 / 18 / 23 / 8（ソースコメントでは Q2_0 / IQ3_XXS / IQ4_XS / Q8_0）です。ほかの key 型は native 対象になりません。pack 側の key が非量子化なら BF16 経路が残りますが、pack 側が量子化済みなのに native key がロードされない場合は、後続の PLE 接続でエラーになります（`engine/src/core/native_dense.cpp:180-190,214-228,429-465`、`engine/src/program/generate.cpp:6226-6241`）。

quantized key が native 経路へ接続されると、PLE の key 投影で入力活性を Q8_1 に量子化し、native MMVQ を実行します。フラグなしの経路は Q8_0 活性と `s2_gemv_q8` です。投影後の PLE 処理はこのオプション単独では切り替わりません（`engine/src/program/generate.cpp:6212-6241`、`engine/src/kernels/cuda/ple.cu:308-323`）。同じ経路はバッチ verify の PLE key 投影にも使われます（`engine/src/core/verify.cpp:1728-1738`）。

`--native` プリセットを使うと、このフラグは他の native 系フラグとともに有効化されます。プリセット自身は `--ple-gguf` を要求し、`--native-dense-gguf` が省略された場合は `--native` のモデル shard を基に shard 群を組み立て、必要に応じて PLE shard も加えます（`engine/src/program/generate.cpp:5155-5190`）。

## 適用条件と副作用

- `--native-dense-gguf` が少なくとも1つ必要で、`--no-ple` とは併用できません。違反時は stderr に `strata generate: --native-ple-key requires PLE and --native-dense-gguf` を出し、終了コード `2` で拒否します（`engine/src/program/generate.cpp:5318-5320`）。通常の PLE 実行には `--ple-gguf` が必要で、`--no-ple` と `--ple-gguf` も相互排他です（同 `generate.cpp:5205-5207,5213-5216`）。
- PLE key が対象 GGUF shard に見つからない、または native 対応外の型なら native key としてはロードされません。pack 側の key が非量子化なら BF16 経路が残りますが、量子化済みなら PLE 側は `native PLE key is absent or incompatible` を stderr に出します。対応型の key でも native data または Q8_1 scratch が接続されていない場合は同じエラーになります（`engine/src/core/native_dense.cpp:183-186,622-634`、`engine/src/program/generate.cpp:6226-6241`）。
- native dense の読み込みは GPU メモリへの割り当てと GGUF からの転送を伴います。読み込み失敗時は `native dense projections: ...` を stderr に出して終了コード `1` になります（`engine/src/core/native_dense.cpp:429-465,622-634`、`engine/src/program/generate.cpp:6060-6065`）。
- `--native-dense-gguf` の shard 群に利用可能な native projection がなければ `native dense: no supported GDN/QSA matrices in supplied shards` で失敗します。このエラーは PLE key 以外も含む native dense のロード対象全体に対する条件です（`engine/src/core/native_dense.cpp:622`）。

## 出力とエラー

明示的な前提条件違反は stderr と終了コード `2` で通知されます。native dense のファイル・テンソル検証や GPU load の失敗は stderr に理由を出し、呼び出し側では終了コード `1` になります。正常時は `native projection matrices` の数・重み量・ロード時間を stderr に出しますが、このフラグ単独の成功メッセージはありません（`engine/src/program/generate.cpp:5318-5320,6060-6067`）。

## 根拠

- `engine/src/program/generate.cpp:782,1248,3916` — option の既定値、help 表示、値を取らない parser 登録。
- `engine/src/program/generate.cpp:5318-5320,6060-6067` — 必須条件の拒否、native dense load と失敗・成功時の出力。
- `engine/src/core/native_dense.cpp:180-190,214-228,429-465,622-634` — PLE key の型別対象、shard の走査、テンソル検証、GPU load と native key 情報の設定。
- `engine/src/program/generate.cpp:6212-6241` — PLE key の接続と不整合時のエラー。
- `engine/src/kernels/cuda/ple.cu:308-323` — Q8_1 native MMVQ と通常 Q8_0 経路の分岐。
- `engine/src/core/verify.cpp:1728-1738` — バッチ verify における native PLE key 投影。
- `engine/src/program/generate.cpp:5155-5190` — `--native` プリセットによる自動有効化と shard の補完。

調査範囲は索引が `strata-engine` の parser として指定する `engine/src/program/generate.cpp` と、それが利用する native dense / CUDA PLE 実装です。別実装の SYCL parser はこの文書のコマンド scope として索引に記載されていないため、挙動を統合していません。
