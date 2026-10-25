# `--expert-cache-cpu-order`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--expert-cache-cpu-order` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

GPU 上の expert cache hit の expert reduction に、CPU の計算順序に合わせる実験的な経路を選びます。help では “experimental GPU expert reduction matching CPU order” と説明されています（`src/program/generate.cpp:864`）。

## 使い方

```sh
strata generate --pack ./pack --tokens "1,2,3" --expert-cache 128 --expert-cache-cpu-order
```

`--expert-cache-cpu-order` 自体に値は付けません。例の `--expert-cache 128` は expert cache を有効にするための別オプションです。

## 値と既定値

parser はこのフラグを見つけると `expert_cache_cpu_order` を `true` にします。引数値の読み取りや個別 validation はなく、省略時は `Options` の初期値 `false` です（`src/program/generate.cpp:563,2741`）。したがって同じオプションの重複指定も真偽値を再度 true にするだけです。

## 実行時の動作

生成処理は設定値を `drive.d.hit_cpu_order` に渡します（`src/program/generate.cpp:6784`）。CUDA の expert-source hit 処理は hit がある場合に活性値を量子化し、この値が true なら `moe_hit_grouped_s2_cpu_order`、false なら通常の `moe_hit_grouped_s2` を呼び分けます（`src/core/expert_source.cpp:5265-5266,5293-5300`）。これは cache hit の GPU 計算経路の選択であり、cache miss の CPU 側処理を切り替えるフラグではありません。

SYCL 側にも同じ設定の受け渡しと分岐があります（`sycl/src/program/generate.cpp:541,2018,5294`; `sycl/src/core/expert_source.cpp:2921-2926`）。CUDA 側の CPU-order 関数は fp32 activation scale を要求し、入力補正、gate/up projection、後続演算を専用カーネルで処理します（`src/kernels/cuda/s2_expert_grouped.cu:1240-1265`）。

## 適用条件と副作用

効果があるのは expert-source が GPU cache hit を処理する経路です。hit が0件なら処理はそこで戻るため、このフラグによる GPU hit kernel の起動はありません（`src/core/expert_source.cpp:5264-5266`）。expert cache の有効化方法・容量は `--expert-cache` 側で指定します。

このオプションは実験的として案内されています。性能向上や数値差の程度は parser/help と使用箇所からは保証できず、本調査では測定していません。GPU kernel を追加で選択するため、その計算と scratch/output の利用が発生します（`src/core/expert_source.cpp:5295-5300`）。

## 出力とエラー

このフラグ固有の入力 validation や警告経路は parser にありません。未知の引数は stderr に `unknown argument: ...` と usage を出して終了コード 2 になります（`src/program/generate.cpp:2787-2792`）。CUDA の CPU-order kernel に activation scale が渡らない場合は stderr にエラーを出し、終了コード 1 で終了します（`src/kernels/cuda/s2_expert_grouped.cu:1244-1248`）。ただし通常の expert-source 経路では scale が null なら kernel 呼び出し前に処理を失敗状態にします（`src/core/expert_source.cpp:5288-5292`）。

## 根拠

- parser の初期値、help 表示、フラグ受理: `src/program/generate.cpp:563,864,2741`
- engine から Drive への設定伝達: `src/program/generate.cpp:6784`
- CUDA の hit 判定・分岐・失敗状態: `src/core/expert_source.cpp:5264-5266,5288-5300`
- SYCL の同等分岐: `sycl/src/program/generate.cpp:541,2018,5294`; `sycl/src/core/expert_source.cpp:2921-2926`
- CUDA CPU-order kernel の scale 検査と処理: `src/kernels/cuda/s2_expert_grouped.cu:1240-1265`
- parser の未知引数エラー: `src/program/generate.cpp:2787-2792`

確認範囲は上記 checkout のソースです。Release 配布物および各 backend での実行結果は確認していません。
