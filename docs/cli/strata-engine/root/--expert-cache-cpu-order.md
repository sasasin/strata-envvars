# `--expert-cache-cpu-order`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--expert-cache-cpu-order` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

GPU expert cache に resident な expert の MoE hit 計算で、通常の grouped-S2 kernel の代わりに CPU 側の演算順序に合わせた GPU kernel を選びます。GPU cache hit の計算結果を CPU 経路に近づける実験用スイッチです。help でも experimental とされています（`engine/src/program/generate.cpp:1266`）。

## 使い方

```sh
# expert cache を有効にした strata generate で、cache hit の GPU 計算に CPU 順序の kernel を使う
strata generate --pack ./model-pack --tokens "1,2,3" --expert-cache 256 --expert-cache-cpu-order
```

`--expert-cache` を指定しない場合は cache slot 数が既定値 0 で、resident hit がないため、このオプションによる kernel 切替も起きません（`engine/src/program/generate.cpp:903`, `engine/src/program/generate.cpp:3984-3987`, `engine/src/core/expert_source.cpp:6030-6031`）。

## 値と既定値

オプションを指定すると `expert_cache_cpu_order` を `true` にし、省略時の初期値は `false` です。値引数を読み取らず、個別の値検証もありません。同じフラグを複数回指定しても、真偽値を `true` にする処理が繰り返されるだけです（`engine/src/program/generate.cpp:908`, `engine/src/program/generate.cpp:4203`）。

## 実行時の動作

parser で設定された値は decode 用 `Drive` の `hit_cpu_order` に渡されます（`engine/src/program/generate.cpp:10231-10246`）。expert source は cache hit がある場合に hit 行と出力先を準備し、GPU 側の処理でこの値が真なら `moe_hit_grouped_s2_cpu_order`、偽なら通常の `moe_hit_grouped_s2` を呼びます（`engine/src/core/expert_source.cpp:6024-6028`, `engine/src/core/expert_source.cpp:6060-6065`）。SYCL 実装にも同じ分岐があります（`engine/sycl/src/program/generate.cpp:5782`, `engine/sycl/src/core/expert_source.cpp:2921-2926`）。

CPU-order kernel は activation の補正・量子化、gate/up 射影、SwiGLU、中間量子化、down 射影の順で処理します。内積の積和と lane の集約も CPU の式順に合わせています（`engine/src/kernels/cuda/s2_expert_grouped.cu:432-455`, `engine/src/kernels/cuda/s2_expert_grouped.cu:481-509`, `engine/src/kernels/cuda/s2_expert_grouped.cu:1385-1408`）。SYCL backend は移植された同等 kernel を呼び出します（`engine/sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp:1737-1874`）。

この切替は GPU cache hit の計算に限られ、cache miss の CPU 側処理や他の GPU 演算全体の順序を切り替えるものではありません。通常経路も CPU-order 経路も、hit 出力を miss 側の結果へ加算します（`engine/src/core/expert_source.cpp:6074-6085`）。ソースコメントは CPU の reduction 順序への整合を説明していますが、CPU/GPU の libc による最下位 bit の差は別途診断するとしているため、全出力の bit 単位一致までは保証されません（`engine/src/kernels/cuda/s2_expert_grouped.cu:485-489`）。

## 適用条件と副作用

- `strata generate` の parser が受理します。`strata-engine` の通常 engine と SYCL engine の parser、decode 設定、hit kernel 分岐で同じオプションが確認できます（`engine/src/program/generate.cpp:4203`, `engine/sycl/src/program/generate.cpp:2167`）。
- resident expert hit がない場合、hit kernel 呼び出しはありません。したがって `--expert-cache` が 0 のままならこの設定は実質的に使われません（`engine/src/program/generate.cpp:903`, `engine/src/core/expert_source.cpp:6030-6031`）。
- CPU-order 経路は FP32 activation scale を必要とします。source 側は scale pointer が null の場合に処理を失敗として記録し、kernel 自体も null scale を受けると stderr にエラーを出して終了します（`engine/src/core/expert_source.cpp:6053-6056`, `engine/src/kernels/cuda/s2_expert_grouped.cu:1371-1375`）。通常の呼び出し元は scale を使う quantize と kernel 呼び出しを行います（`engine/src/core/expert_source.cpp:6047-6062`）。
- cache 設定やファイルを直接変更する作用は parser・dispatch に見当たりません。runtime では GPU kernel の選択と hit 計算が変わります。

## 出力とエラー

このフラグ自体に専用の警告や成功メッセージはありません。未知の引数は `unknown argument` を stderr に出し、usage を表示して status 2 で終了します（`engine/src/program/generate.cpp:4268-4274`）。CPU-order kernel の activation scale が欠落した場合は stderr に理由を出して status 1 で終了します（`engine/src/kernels/cuda/s2_expert_grouped.cu:1371-1375`）。

## 根拠

- `engine/src/program/generate.cpp:908` — option state の既定値。
- `engine/src/program/generate.cpp:1266`, `engine/src/program/generate.cpp:4203` — help 表示と parser 登録。
- `engine/src/program/generate.cpp:10231-10246` — decode `Drive` への設定反映。
- `engine/src/core/expert_source.cpp:6024-6065` — cache hit の選別、scale 準備、kernel 分岐。
- `engine/src/kernels/cuda/s2_expert_grouped.cu:432-455`, `engine/src/kernels/cuda/s2_expert_grouped.cu:1367-1408` — CPU 順序の演算と GPU dispatch。
- `engine/sycl/src/program/generate.cpp:580`, `engine/sycl/src/program/generate.cpp:854`, `engine/sycl/src/program/generate.cpp:2167`, `engine/sycl/src/program/generate.cpp:5782`; `engine/sycl/src/core/expert_source.cpp:2921-2926`; `engine/sycl/src/kernels/cuda/s2_expert_grouped.dp.cpp:1737-1874` — SYCL 側の同等経路。
