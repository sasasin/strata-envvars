# `--no-fused-gr`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--no-fused-gr` |
| 別名 | なし |
| 値 | 値なしのフラグ |

## 役割

native MMVF の実行時に使われる fused hyper-connection read を無効にし、layer の GR read/write を従来の個別経路に切り替える A/B 用オプションです。単独で fused 経路を有効にするフラグではありません。

## 使い方

```sh
strata generate --pack ./model --tokens "1,2,3" --native ./model/shard1.gguf --no-fused-gr
```

`--native` は native 実行経路の指定例です。実際に fused GR が選ばれ得る条件や除外条件は次節のとおりです。

## 値と既定値

値を取りません。parser は引数 `--no-fused-gr` と完全一致した場合に真偽値を `true` にし、既定値は `false` です。同じフラグを複数回指定しても同じ値を設定します。値を付けた形式はこのフラグとして認識されず、未知引数になります。parser 登録と既定値は `engine/src/program/generate.cpp:955,4263`、同じ設定の SYCL parser は `engine/sycl/src/program/generate.cpp:621,2209`。

## 実行時の動作

エンジンは `layer_set_fused_gr` に、native MMVF が有効であり、このフラグがなく、GPU-stage 計測・layer dump・half dump・stage timing のいずれでもない場合だけ `true` を渡します。それ以外は fused GR を無効にします（CUDA/HIP: `engine/src/program/generate.cpp:6104-6113`、SYCL: `engine/sycl/src/program/generate.cpp:3219-3228`）。`--native` は native 設定を組み立てる際に `gr_native_mmvf` を有効にします（`engine/src/program/generate.cpp:5154-5163`）。従って `--no-fused-gr` は `--native` や `--gr-native-mmvf` と併用して、その fused 経路だけを A/B 比較用に止められます。

layer の実行側では、fused GR が有効かつモデル形状が fused kernel に対応するときに fused read を呼びます。無効、または形状非対応なら通常の `gr_read` と別の `gr_write` に進みます（CUDA/HIP: `engine/src/core/layer.cpp:1500-1501,1557-1568,1720-1730`、SYCL: `engine/sycl/src/core/layer.cpp:1558-1559,1620-1632`）。この切替は GR の読み書き経路に関するもので、生成トークン数や他の native 設定自体を変更する処理は確認できません。

## 適用条件と副作用

- `--gr-native-mmvf`（またはそれを有効にする `--native`）がなければ、fused GR は既に選択条件を満たさないため、このフラグを加えても `layer_set_fused_gr` の値は変わりません（`engine/src/program/generate.cpp:779,3913,5161,6112-6113`）。
- `--gpu-stages`、`--dump-layers`、`--dump-halves`、`--stage-timing` のいずれかがある場合も、計測・dump 用に fused 経路を無効にします（`engine/src/program/generate.cpp:6112-6113`）。
- CUDA/HIP の通常 GR fallback は、HC Q8 射影スケールがあると `STRATA_HC_REQ8 needs the fused hyper-connection read` を設定して失敗します（`engine/src/core/layer.cpp:1566-1568`）。同じ分岐にこの明示的なエラー確認は SYCL 側では見当たりません（`engine/sycl/src/core/layer.cpp:1622-1631`）。このため HC Q8 条件での利用可否は backend により異なります。
- parser はこのフラグ専用の警告・出力を行いません。未知引数は stderr に `unknown argument: ...` と usage を出して終了コード 2 で拒否されます（`engine/src/program/generate.cpp:4268-4273`）。

## 根拠

- `engine/src/program/generate.cpp:955,1375-1376,4263` — フラグの既定値、help 表示、parser 登録。
- `engine/sycl/src/program/generate.cpp:621,936-937,2209` — SYCL parser と help 表示。
- `engine/src/program/generate.cpp:6112-6113`、`engine/sycl/src/program/generate.cpp:3227-3228` — fused GR を有効にする条件。
- `engine/include/strata/core/layer.hpp:488-493`、`engine/src/core/layer.cpp:1500-1501,1557-1568,1720-1730`、`engine/sycl/src/core/layer.cpp:1558-1559,1620-1632` — fused 経路と fallback の使用箇所。

調査範囲は parser、設定反映、および CUDA/HIP・SYCL の layer 実装です。prefill 経路全体でこの設定がどの箇所まで共有されるかは、この文書では確認できた範囲を超えて断定していません。
