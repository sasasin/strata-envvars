# `strata generate --expert-cache-per-layer`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--expert-cache-per-layer` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

GPU expert cache の空きスロットを全層で共有せず、層ごとの範囲に分けて割り当てます。既定の共有方式では、実行中に先に到着した層・expert の組がキャッシュを占めることがあります。このフラグを付けると各層が自分の範囲からだけスロットを取得するため、ある層が他層のスロットを使い切らなくなります。キャッシュの退去（eviction）は追加されず、各層の枠が埋まった後の未常駐 expert はキャッシュに入りません（`engine/src/core/expert_cache.cpp:785-803`、`engine/include/strata/core/expert_cache.hpp:181-185`）。

## 使い方

```sh
# pack の expert cache を要求し、層別に割り当てて生成する
strata generate --pack ./model-pack --tokens "1,2,3" --expert-cache 256 --expert-cache-per-layer
```

`strata generate` は `--pack DIR` と `--tokens LIST`（または `--tokens-file`）を受け付けます（`engine/src/program/generate.cpp:1208-1214`）。このフラグ自体には値を続けません。

## 値と既定値

オプションは値なしで `expert_cache_per_layer` を `true` にします。指定しなければ `false` です（`engine/src/program/generate.cpp:909-914,4203-4205`）。このフラグ自体に数値範囲の検証はありません。重ねて指定しても同じ真偽値を設定するだけです。別の値を続けるとその値は独立した引数として扱われ、認識されなければ usage を stderr に出して終了コード `2` で失敗します（`engine/src/program/generate.cpp:4268-4274`）。

## 実行時の動作

この設定だけではキャッシュ容量を作りません。キャッシュのスロット数が正のときに cache が開かれ、設定が `ExpertCache` に渡されます（CUDA/HIP系: `engine/src/program/generate.cpp:9717-9722`、SYCL: `engine/sycl/src/program/generate.cpp:5228-5230`）。`--expert-cache` の既定値は `0`（無効）です（`engine/src/program/generate.cpp:895-904`）。ただし `--expert-profile` を指定して `--expert-cache` を `0` のままにした場合は、自動サイズ指定 `-1` に変換されるため、プロファイルとともにこのフラグが効くことがあります（`engine/src/program/generate.cpp:6746-6756`）。

キャッシュが有効なとき、層 `l` のスロット範囲は `[l*q, (l+1)*q)`（最後の層は余りも使用）です。`q` は総スロット数を層数で割った整数です。総スロット数が層数より少ないと `q=0` となり、最後の層だけが余りのスロットを使います。プロファイルなしの実行では、expert が初めて要求された時に、その層の枠に空きがあれば expert を読み込んで GPU で計算し、枠が満杯なら CPU 側の miss として扱います。通常の共有方式と同様、キャッシュからの退去はありません（`engine/src/core/expert_cache.cpp:769-778,785-803`、`engine/src/core/expert_source.cpp:5990-6019`）。

`--expert-profile` を併用した場合は、プロファイルの順位に従って起動時に各層の枠を埋めます。層別モードではプロファイル全体を走査し、枠が埋まった層の項目だけを飛ばして別の層への充填を続けます（`engine/src/program/generate.cpp:9758-9766,9786-9805`）。

native pack で `--expert-cache N` が正数の場合は、層ごとの blob サイズに合わせたスロット列も組み立てます。要求予算は N 個の最大 blob 相当で、VRAM の空きから reserve を引いた容量との小さい方を上限とし、全層に同じ個数 `q` を割り当てられる範囲でスロット数を再計算します。`q` が正なら実際のスロット数は `q × 層数`（`q` は expert 数を上限とする）になります。この調整内容は stderr に出力されます。`q=0` の場合は層別サイズのスロット列を作らず、共通の uniform slot 経路に進みます（CUDA/HIP系: `engine/src/program/generate.cpp:9438-9469,9655-9657`、SYCL: `engine/sycl/src/program/generate.cpp:4987-5025`）。この経路に入らない pack では、層別 admission は適用されますが、この native pack 向けのサイズ再計算は行われません。

GPU cache hit 経路は expert pool と組み合わせて初期化され、`--no-pool` の場合は hit callback が無効になります。その場合、このフラグによる層別 admission を生成時の GPU hit に利用する経路はありません（`engine/src/program/generate.cpp:10389-10428,10479-10484`）。

## 適用条件と副作用

- 少なくとも一つの GPU expert cache スロットが作られる経路で効果があります。スロット数が `0` なら cache は開かれず、このフラグだけでは GPU cache hit は有効になりません（`engine/src/program/generate.cpp:895-904,9717-9722,10479-10484`）。
- 空きスロットを層別に固定するため、ある層の未使用枠を別の層が借りることはありません。最後の層には割り算の余りが割り当てられます（`engine/src/core/expert_cache.cpp:771-778`）。
- GPU cache の確保・初期化は VRAM を使用します。cache open が失敗し、自動サイズ縮小でも開けない場合はエラーを stderr に出して終了コード `1` で終了します（`engine/src/program/generate.cpp:9649-9683`）。
- CUDA/HIP系とSYCLの parser・cache 設定箇所は確認しました。特定のGPU、driver、buildで利用可能かはそれらの実行環境に依存し、このソース調査だけでは判定できません。

## 出力とエラー

キャッシュが開かれると、stderr にスロット数・VRAM使用量と admission policy が表示され、フラグ指定時は層別スロット範囲の情報も表示されます（`engine/src/program/generate.cpp:9717-9741`、SYCL: `engine/sycl/src/program/generate.cpp:5236-5248`）。cache の確保失敗はエラー文字列を stderr に出し、終了コード `1` になります。フラグ固有の値エラーはありません（`engine/src/program/generate.cpp:9659-9683`）。

## 根拠

- `engine/src/program/generate.cpp:909-914,4203-4205` — フラグの既定値と parser 登録。
- `engine/src/program/generate.cpp:1208-1214,4268-4274` — コマンド構文と未知引数の失敗経路。
- `engine/src/program/generate.cpp:6746-6756,9438-9469,9717-9741,9758-9805` — profile 時の既定 cache sizing、native pack の層別サイズ調整、cache 設定・ログ、profile 充填。
- `engine/sycl/src/program/generate.cpp:2166-2169,4987-5025,5228-5248` — SYCL parser、native pack の層別サイズ調整、cache 設定・ログ。
- `engine/src/core/expert_cache.cpp:769-803`、`engine/include/strata/core/expert_cache.hpp:181-188` — 層ごとのスロット範囲と admission 規則。
- `engine/src/core/expert_source.cpp:5990-6019`、`engine/src/program/generate.cpp:10389-10428,10479-10484` — cache miss の admission・fill と GPU hit 経路の有効条件。
- `engine/src/program/generate.cpp:9649-9683` — cache open の失敗・縮小再試行・終了経路。
