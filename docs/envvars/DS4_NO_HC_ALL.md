# `DS4_NO_HC_ALL`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 上の DSV41 engine にある hyper-connection mix 処理で、複数 mix をまとめて処理する `ds4_hc_mix_all` dispatch を選ばないためのスイッチです。環境変数が未設定で、かつ `T >= 16`、`n_mix <= 32` のときだけ all-mix kernel を選びます。設定されていれば値の内容にかかわらず通常の `ds4_hc_mix` kernel を選びます。

ただし、現行モデルの通常の Metal 経路ではこの環境変数を読む `hc_mix()` ではなく、mix と split を一つの dispatch にまとめる `hc_mix_split()` が呼ばれます。このため、通常の attention / MoE 経路で `DS4_NO_HC_ALL` が選択を変えることは確認できません。

## 値と判定

`metal/src/engine/ds4_finish.cpp:299` は `std::getenv("DS4_NO_HC_ALL")` の null 判定だけを行い、値を parse しません。

| 環境変数の状態 | `T >= 16 && n_mix <= 32` の場合 | 条件を満たさない場合 |
|---|---|---|
| 未設定 | `ds4_hc_mix_all` を選択 | `ds4_hc_mix` を選択 |
| 設定あり（空文字を含む） | `ds4_hc_mix` を選択 | `ds4_hc_mix` を選択 |

したがって `DS4_NO_HC_ALL=0` も all-mix kernel を無効にします。空文字、数値変換、大小文字、範囲外値に対する個別処理や警告はありません。

## 有効になる条件

- 対象コードは Metal 専用の `strata_ds4` に含まれます。`metal/CMakeLists.txt:135-146,165-169` は `ds4_finish.cpp` と DSV41 engine のソースを同ターゲットに追加し、`STRATA_METAL=1` を定義します。
- `hc_mix()` が呼ばれ、さらに `T >= 16 && n_mix <= 32` のときだけ、未設定と設定済みの差が現れます。条件を満たさない場合は常に `ds4_hc_mix` です。
- ただし、`src/dsv41/ds4_model.cu:8108-8114,8341-8347` の現在の Metal attention / MoE 経路は `hc_mix_split()` を呼びます。`metal/src/engine/ds4_finish.cpp:371-417` のこの実装は `ds4_hc_mix_split` を dispatch し、`DS4_NO_HC_ALL` を参照しません。
- `hc_mix()` は `src/dsv41/ds4_kernels.cu:2221-2225` から Metal host helper に委譲されます。同ファイル内で `hc_mix_chunk()` が `hc_mix()` を呼ぶ経路はありますが、モデル側の `hc_mix_chunk()` 呼び出しは `STRATA_METAL` でない側の `#else` にあります（`src/dsv41/ds4_model.cu:3557-3573,8112-8115,8345-8348`）。現行ソースの呼び出し関係では、通常の Metal モデル処理から当該読み取り箇所に到達する呼び出しは確認できません。
- CLI 引数や他の設定値による優先順位はありません。環境変数を読む `hc_mix()` 経路に限り、設定有無が条件判定に使われます。

## 実行時の詳細

`hc_mix()` は入力配列を Metal の host view として取得し、バッファを wrap した後、条件に応じて `ds4_hc_mix_all` または `ds4_hc_mix` pipeline を取得します（`metal/src/engine/ds4_finish.cpp:281-311`）。all-mix kernel は token ごとに一つの threadgroup を使い、4 mix ずつ計算します。一方、通常 kernel は `(mix, token)` ごとに threadgroup を配置します（`metal/src/engine/msl/ds4_init.metal:229-297`）。環境変数の判定は `hc_mix()` 呼び出しごとに行われ、static cache には保存されません。

設定値に応じたログはありません。`hc_mix()` で `ensure()`、host view / buffer wrap、または pipeline 取得が失敗すると `false` を返します。pipeline 取得失敗時などに呼び出し元の `src/dsv41/ds4_kernels.cu:2221-2225` は一般の CUDA 形式 kernel launch に進みますが、Metal の未実装 launch は stderr に `strata metal: kernel launch with no Metal dispatch at ...` を出して abort します（`metal/include/metal_compat/cuda_launch.h:26-30`）。この失敗経路は `DS4_NO_HC_ALL` 固有ではありません。

## 根拠

- 候補名の全参照検索では、実装上の直接参照は `metal/src/engine/ds4_finish.cpp:299` の一箇所でした。候補一覧には `000_envvers.md:246` に掲載されています。
- 環境変数の判定と pipeline / grid 選択: `metal/src/engine/ds4_finish.cpp:281-311`。
- Metal kernel の計算構成: `metal/src/engine/msl/ds4_init.metal:229-297`。
- Metal host helper からの委譲と未実装 launch の失敗経路: `src/dsv41/ds4_kernels.cu:2221-2225`、`metal/include/metal_compat/cuda_launch.h:26-30`。
- 現行モデルの Metal 経路と環境変数読み取り箇所の到達性: `src/dsv41/ds4_model.cu:3557-3573,8108-8115,8341-8348`、`metal/src/engine/ds4_finish.cpp:369-417`。
- `docs/DETAILS.md` にこの環境変数の説明は見つかりませんでした。
