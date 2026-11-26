# `STRATA_PF_FUSED_KQ`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

K-quant の MoE expert の prompt 計算を、Strata の fused/native kernel に振り分けるスイッチです。主な対象は gate/up が `Q4_K` または `Q5_K`、down が `Q5_1` または `Q8_0` の組です。対応 kernel が設定・利用可能なとき、CUDA では MMQ、HIP の対応経路では MMQ または既存の prompt 経路から切り替わります。通常の decode の選択を直接制御する変数ではありません。CUDA の device 情報は `dev_info()` が構築し、HIP は `kq_on()` が値を判定します。`STRATA_PF_FUSED=0` または `STRATA_PF_FUSED_NATIVE=0` が優先して fused/native 経路を止めます（`engine/src/prefill/moe_fused_iq.cu:3415-3432, 3434-3438`）。

## 値と判定

数値全体の parse はせず、文字列の先頭だけを比較します。CUDA の通常経路は `pf_env()` が未設定・空文字を「unset」、先頭が `1` の値を ON、それ以外を OFF とします。したがって `1`, `10`, `1anything` は ON、`0`, `true`, ` 1`, `2`, `0anything` は OFF です。unset と空文字は同じ判定値ですが、後述の Turing 固有読み取りだけは空文字を明示的な非 opt-in として扱います（`engine/include/strata/prefill/fused_tile_rule.hpp:194-205`; `engine/src/prefill/moe_fused_iq.cu:2913-2925, 2963-2967`）。

| 経路 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA、Turing 固有 setup（sm_75） | setup しない | 先頭が `1`（`1`, `1abc`） | 空文字、`0`, `true`, ` 1`。先頭が `1` でなければ setup しない |
| CUDA、その他の K-quant setup | カード既定則を使う | 先頭が `1` は全カードで要求 | 空文字はカード既定則、先頭が `1` 以外の設定値は OFF |
| HIP の gfx11 K-quant 経路 | 通常は OFF。Windows gfx1151 だけ後述の既定則あり | 空でない値の先頭が `1` | 空文字は gfx1151 の既定則へ、それ以外で先頭が `1` 以外は OFF |

空白除去、大文字小文字変換、数値範囲・負数の検証はありません。たとえば `true` は CUDA の汎用判定と HIP の明示値判定では OFF です。CUDA Turing の判定は unset と空文字を区別し、どちらも setup しないため、汎用 CUDA の unset 時既定則とは異なります（`engine/include/strata/prefill/fused_tile_rule.hpp:180`; `engine/src/prefill/moe_fused_iq.cu:2918-2925, 2963-2967, 3030-3047`）。

## 有効になる条件

- **CUDA:** 通常の unset 既定則は、`fused_tile::kq_takes()` によって sm_86 系・sm_120 系の 80 SM 以上、および staged launch が使える 40–79 SM のカードで ON になります。40–79 SM では `STRATA_PF_FUSED_SM40=0` が既定則を抑えます。先頭 `1` ならこのカード既定則を越えて setup を要求しますが、対応する device/kernel setup が成功する必要があります（`engine/include/strata/prefill/fused_tile_rule.hpp:194-205`; `engine/src/prefill/moe_fused_iq.cu:2957-2971`）。
- **CUDA の Turing:** `STRATA_PF_FUSED_KQ` の先頭 `1` が必要です。さらに `STRATA_PF_FUSED_SM75_KQ=0` でないこと、必要な 128-row kernel setup が通ることが必要です（`engine/src/prefill/moe_fused_iq.cu:2913-2925`）。
- **HIP:** この K-quant の gate/up 実装は gfx11 経路で `kq_on()` により選ばれます。通常の HIP では値が未設定・空なら OFF です。Windows の gfx1151 では空（または unset）の場合、`STRATA_GFX1151_DEFAULTS=0` でなければ device の arch を調べて既定 ON になります。明示値の先頭が `1` ならこの既定判定より優先します（`engine/src/prefill/moe_fused_iq.cu:3030-3048, 3071-3075`）。
- **HIP gfx12:** この変数による K-quant gate/up kernel 経路はありません。`kq_on()` の gate/up 判定は gfx11 のみです（`engine/src/prefill/moe_fused_iq.cu:3071-3075`）。
- すべての backend で `STRATA_PF_FUSED=0` は fused kernel の選択を止め、`STRATA_PF_FUSED_NATIVE=0` も native pack を止めます。K-quant の down は gate/up の組と一致しなければ対象にならず、CUDA の別 down 形式はこの分岐で fused にしません。NT=256 または warp-specialized 経路にも K-quant 形式の kernel がないため対象外です（`engine/src/prefill/moe_fused_iq.cu:3415-3432, 3434-3438, 3495-3499`）。
- 対応形式でも kernel setup が成功しない場合、CUDA は `d.kq` を立てず、対象レイヤーは MMQ に残ります（`engine/src/prefill/moe_fused_iq.cu:2963-2971, 3495-3499`）。
- Qwen3.6 entry（`strata --model` と standalone `strata-q36`）は、値が未設定なら `STRATA_PF_FUSED_KQ=1` をプロセス環境に追加します。既に値がある場合は、その値を保持します。したがって Qwen3.6 では通常の entry と異なる既定値になります（`engine/include/strata/prefill/own_only_switches.hpp:75-82`; `engine/src/qwen35/q36_engine.cu:5431-5439`）。
- `STRATA_PREFILL_FUSED` が有効で `STRATA_PREFILL_MMQ` が無効の build では、起動前の初期化がこのスイッチを含む own-only switch 群を unset 時だけ `1` にします。空文字は「設定済み」なので保持され、既定 ON の補完はされません。CUDA/HIP のどちらも対象ですが、HIP の KQ kernel 対応範囲は上記の通りです（`engine/src/prefill/prefill.cpp:223-256`; `engine/include/strata/prefill/own_only_switches.hpp:18-24, 48-56`）。
- 通常の CUDA `strata` 起動では、全 visible GPU が同じ compute capability の場合、`apply_nv_defaults()` がカード別の既定値を設定します。sm_86、sm_89、sm_120、sm_121 の各既定表にこの変数の `1` が含まれます。`STRATA_SM86_PERF=0`, `STRATA_SM89_PERF=0`, `STRATA_SM120_PERF=0`, `STRATA_SM121_PERF=0` はそれぞれの表を止めます。`STRATA_DEFAULTS=026` は sm_89、sm_120、sm_121 の表を止めますが、sm_86 の表は止めません。ユーザーが値を設定済みなら、空文字を含めその値を維持します。混在 compute capability の GPU 群ではこのカード別既定表を適用しません（`engine/src/program/generate.cpp:4425-4449`; `engine/src/core/nv_defaults.cpp:41-43, 59-67, 75-83, 98-106, 176-192, 222-237`）。

## 実行時の詳細

CUDA の汎用経路では `dev_info()` の初期化中に `STRATA_PF_FUSED_KQ` と `STRATA_PF_FUSED_SM40` を読み、カード情報と `kq_takes()` の結果を使って `Q4_K`, `Q5_K`, `Q5_1` の各 kernel を setup します。setup が成立した場合に限り `d.kq=true` となり、利用可能なら `Q8_0` down kernel も別に setup します（`engine/src/prefill/moe_fused_iq.cu:2957-2971`）。`dev_info()` の static 初期化と `kq_on()` の static local による判定のため、通常は最初の参照後に同一プロセスで環境を変更しても再評価されません（`engine/src/prefill/moe_fused_iq.cu:2963-2965, 3030-3048`）。

CUDA の通常起動時既定値は、GPU の compute capability を調べた後、モデル読み込み前に未設定の環境変数へ `1` を設定します。Qwen3.6 はモデルを扱う entry の起動処理で同様に未設定値だけを補います。own-only build はプロセス初期化時に switch 群を設定します。これらはすべてプロセス環境への設定で、CLI 引数からこの変数へ直接値を渡す処理はありません（`engine/src/program/generate.cpp:4425-4449`; `engine/src/prefill/prefill.cpp:223-256`; `engine/src/qwen35/q36_engine.cu:5431-5439`）。

kernel 選択時は対応する gate/up と down の形式、GPU・build の対応、`STRATA_PF_FUSED` の有効性も確認されます。CUDA で fused K-quant 分岐が使われると、対応層は Strata の native kernel を起動し、それ以外の K-quant 層は MMQ 側に残ります。HIP の gfx1151 既定経路は gfx11 の K-quant kernel を選びます。`STRATA_PF_FUSED_KQ` 自体が変えるのはこの prompt の経路で、コード上、この変数による別の設定ファイルや子プロセスへの転送はありません（`engine/src/prefill/moe_fused_iq.cu:3434-3438, 3495-3499, 3071-3075`）。

## ログと測定値

CUDA の `apply_nv_defaults()` がこの変数を含む既定表を一つ以上適用すると、stderr に `strata: <GPU family>: ... speed switches on by default ...` の行を出し、設定した switch 名を列挙します。既定表から除外された場合や、この変数が既に設定されていて新規設定が一つもない場合、この処理による行は出ません（`engine/src/core/nv_defaults.cpp:222-256`）。

CUDA は K-quant prompt の route を表示する別の案内を、モデルに対象形式がある場合に出します。対応 kernel が有効なら `strata: a model with K-quant experts ... reads its prompt on Strata's own kernels ...`、無効なら MMQ route の行です。これは環境変数の値そのもののログではなく、モデル形式と利用可能な route の案内です（`engine/src/core/nv_defaults.cpp:287-299`; `engine/src/program/generate.cpp:5412-5419`）。

この変数が OFF のときに専用の警告や終了処理を行うコードは確認できません。対応 kernel setup が通らなければ MMQ route に残る処理です（`engine/src/prefill/moe_fused_iq.cu:2963-2971, 3495-3499`）。

## 根拠

- `engine/include/strata/prefill/fused_tile_rule.hpp:194-205` — CUDA の K-quant 既定判定と値規則。
- `engine/src/prefill/moe_fused_iq.cu:2913-2925, 2957-2971, 3030-3048, 3415-3438, 3495-3499` — CUDA/HIP の読み取り、kernel setup、適用制約。
- `engine/src/core/nv_defaults.cpp:41-43, 59-67, 75-83, 98-106, 176-192, 222-256, 276-299` — NVIDIA 既定値、優先順位、案内文。
- `engine/src/program/generate.cpp:4425-4449, 5412-5419` — CUDA 起動時の適用とモデル route 案内。
- `engine/src/prefill/prefill.cpp:223-256`、`engine/include/strata/prefill/own_only_switches.hpp:18-24, 48-56, 75-82`、`engine/src/qwen35/q36_engine.cu:5431-5439` — build/entry による unset 時補完。
