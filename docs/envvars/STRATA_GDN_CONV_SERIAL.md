# `STRATA_GDN_CONV_SERIAL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GDN prefill の convolution 経路を旧 serial kernel に固定する設定です。値の内容ではなく環境変数が存在するかで判定します。CUDA/HIP 実装では `gdn_conv`、SYCL 実装では `select_gdn_conv_path` が読み取り、serial が選ばれると convolution kernel の後に Q/K L2 normalization を別途実行します。未設定で長い入力の場合に使われる tiled、fused L2、Battlemage 向け経路を選ばせないための A/B 用 override です（`engine/src/prefill/kernels.cu:3053-3079`、`engine/sycl/src/prefill/kernels.dp.cpp:2668-2788`）。

通常の GDN prefill では `gdn_conv` が QKV から convolution 出力 `h` と更新済み convolution history を作り、その後の recurrence に渡されます（`engine/src/prefill/prefill.cpp:5179-5209`、`engine/sycl/src/prefill/prefill.cpp:3544-3553`）。ソースだけから、この override による token 出力の同一性や性能差は断定できません。

## 値と判定

両実装とも `std::getenv(...) != nullptr` の有無判定です。値を parse せず、空文字も設定ありとして serial を選びます。数値境界や無効値の概念はありません。

| ビルド / 経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP の `gdn_conv` | `T <= 64` は serial、それより大きい場合は `STRATA_GDN_CONVL2` 等に従う | 任意の値。例: `1`、`0`、`true`、空文字、`0anything` | なし（存在すれば有効） |
| SYCL の GDN convolution dispatch | `rows <= 64` は serial。それより大きい場合は `STRATA_GDN_CONVL2` と Battlemage 条件に従う | 任意の値。例: `1`、`0`、`true`、空文字、`0anything` | なし（存在すれば有効） |

どちらも関数内 `static const bool` に初回評価結果を保存します。プロセス起動後に環境を変更しても、その実装で最初に評価した後の呼び出しには反映されません（`engine/src/prefill/kernels.cu:3053-3055`、`engine/sycl/src/prefill/kernels.dp.cpp:2773-2779`）。

## 有効になる条件

- 対象の処理が GDN prefill convolution の `gdn_conv` を通る必要があります。通常の CUDA/HIP/SYCL prefill はこの関数を呼びます（`engine/src/prefill/prefill.cpp:5203`、`engine/sycl/src/prefill/prefill.cpp:3546`）。
- HIP では `STRATA_USE_HIP` 下で `gdn_conv_recurrence_fused` が成功すると、呼び出し側が `gdn_conv` を呼ばないため、この変数による分岐も通りません（`engine/src/prefill/prefill.cpp:5196-5204`）。
- `T` / `rows` が 64 以下の場合は変数が未設定でも serial kernel です。設定してもこのケースの選択結果は変わりません（`engine/src/prefill/kernels.cu:3055-3056`、`engine/sycl/src/prefill/kernels.dp.cpp:2779`）。
- CUDA/HIP で `T > 64` のとき、serial 判定が `STRATA_GDN_CONVL2` の読み取りより先です。未設定なら `STRATA_GDN_CONVL2` の `atoi` 結果で fused L2 経路（非 0、2 以上なら別の fused kernel）または tiled + 別 L2 経路を選びます（`engine/src/prefill/kernels.cu:3054-3078`）。
- Linux CUDA のエンジン起動時には、`STRATA_GDN_CONVL2` が未設定なら Strata が既定値 `2` を環境に設定します。ユーザーが `STRATA_GDN_CONV_SERIAL` を設定していれば、serial 分岐がこの既定値より優先されます（`engine/src/program/generate.cpp:4410-4415`、`engine/src/core/arch_defaults.cpp:263-275`）。
- SYCL で `rows > 64` の場合、serial 指定が `STRATA_GDN_CONVL2` より優先されます。serial が未指定で `STRATA_GDN_CONVL2` が存在し、その `atoi` 結果が非 0 なら fused L2、値が 0 なら separate L2 です。変数自体が未設定の場合だけ Battlemage 自動経路の候補になり、さらに `S == 128`、`C % 512 == 0`、Level Zero Battlemage、512 行以上という条件が必要です（`engine/sycl/src/prefill/kernels.dp.cpp:2773-2783`、`engine/sycl/src/prefill/bmg_gdn_tiles.hpp:7-10`）。

## 実行時の詳細

CUDA/HIP は最初の `gdn_conv` 呼び出しで serial の有無を cache します。serial が真、または `T <= 64` なら `gdn_conv_kernel` を起動し、続けて `gdn_l2_kernel` を起動します。長い入力で serial が偽なら `STRATA_GDN_CONVL2` を初回だけ `atoi` し、値に応じて fused または tiled 経路を選びます。SYCL は最初の `select_gdn_conv_path` 呼び出しで serial と `STRATA_GDN_CONVL2` を cache し、その選択を `gdn_conv_impl` に渡します。Serial 経路は `gdn_conv_kernel` を起動し、その後 `gdn_l2_kernel` を別起動します（`engine/src/prefill/kernels.cu:3053-3079`、`engine/sycl/src/prefill/kernels.dp.cpp:2668-2789`）。

CLI 引数がこの変数を上書きする処理は、確認した参照箇所にはありません。明示した `STRATA_GDN_CONVL2` は serial 指定を上書きせず、serial の方が先に判定されます。子プロセスへの転送処理は確認できません。

## ログと測定値

この変数の設定有無を表示するログや専用の警告は確認できません。kernel dispatch 後には両実装とも `check("gdn_conv")` を呼びますが、環境変数固有の失敗メッセージではありません（`engine/src/prefill/kernels.cu:3064-3079`、`engine/sycl/src/prefill/kernels.dp.cpp:2721-2771`）。対象 commit の資料には、この変数を切り替えた条件付き測定値を確認できなかったため、性能値は記載しません。

## 根拠

- `engine/src/prefill/kernels.cu:3053-3079` — CUDA/HIP の設定読み取り、dispatch、L2 normalization。
- `engine/sycl/src/prefill/kernels.dp.cpp:2668-2788` — SYCL の実装、判定優先順位と path dispatch。
- `engine/sycl/src/prefill/bmg_gdn_tiles.hpp:7-10` — Battlemage 自動 path の backend、GPU 世代、行数条件。
- `engine/src/prefill/prefill.cpp:5196-5204`、`engine/sycl/src/prefill/prefill.cpp:3544-3546` — 呼び出し元と HIP fused 経路による迂回。
- `engine/src/program/generate.cpp:4410-4415`、`engine/src/core/arch_defaults.cpp:263-275` — Linux CUDA の関連既定値適用。
