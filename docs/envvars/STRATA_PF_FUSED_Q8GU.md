# `STRATA_PF_FUSED_Q8GU`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（2026-11-17 時点）。

## 役割

MoE の prompt prefill で、gate/up と down の両方が `Q8_0` の expert 層を、Strata の fused native kernel に割り当てる opt-in スイッチです。CUDA では gate/up と down のカーネル準備を行い、HIP では gfx12 の native kernel にこの型の組み合わせを許可します。対象は `Q8_0 / Q8_0` の層だけで、他の形式の層の選択は変えません。CUDA では準備済みの gate/up・down kernel の両方を起動します（`src/prefill/moe_fused_iq.cu:2481-2487, 2920-2923, 3293-3304`）。

## 値と判定

CUDA と HIP の読み取りはどちらも `getenv` の値が存在し、先頭文字が `'1'` かだけを判定します。文字列全体の parse、数値検証、空白除去、大文字小文字変換はありません。したがって unset・空文字・`0`・`true`・` 1` は無効、`1`・`10`・`1anything` は有効です（`src/prefill/moe_fused_iq.cu:2270-2272, 2677-2679`）。

| 条件 | unset 時 | 有効になる値 | 無効になる値 |
|---|---|---|---|
| 通常の CUDA/HIP ビルド | スイッチ判定は off | 先頭が `1` | 空文字、先頭が `1` 以外 |
| `STRATA_PREFILL_FUSED` あり・`STRATA_PREFILL_MMQ` なしの Strata ビルド | 起動前に `1` が設定される | 既存値はそのまま判定 | 空文字など既存値は保持され、その値に従う |
| `strata-q36` エンジン | `--model` 検査後、未設定なら `1` を設定 | 既存値は保持され、その値に従う | 空文字など既存値は保持され、その値に従う |

MMQ なしのビルドは、CUDA/HIP 別の既定スイッチ一覧にこの名前を含め、環境に名前がなければ `1` を設定します。名前が既にあれば値を問わず上書きしません（`include/strata/prefill/own_only_switches.hpp:18-24, 48-56`）。この初期化は `STRATA_PREFILL_FUSED` が定義され `STRATA_PREFILL_MMQ` が未定義のときだけ実行されます（`src/prefill/prefill.cpp:204-237`）。`strata-q36` は起動時に `STRATA_PF_FUSED_KQ`、`STRATA_PF_FUSED_Q6K` と共にこの変数を未設定時だけ `1` にします（`src/qwen35/q36_engine.cu:3940-3957`）。CLI 引数でこの変数を個別に上書きする経路は見つかりませんでした。

## 有効になる条件

- **CUDA:** device capability が sm_80 以上で、native kernels の共通準備が成功し、Q8_0 gate/up と Q8_0 down の両方の kernel 準備が成功する必要があります。どちらかの準備が失敗すると `d.q8gu` は立たず、その層は fused native の対象になりません（`src/prefill/moe_fused_iq.cu:2428-2431, 2481-2487`）。
- **HIP:** gfx12 の WMMA 対応 device であることと共通 kernel 準備の成功が必要です。gfx11 ではこのスイッチで Q8_0 gate/up は対象になりません（`src/prefill/moe_fused_iq.cu:2390-2414, 2575-2580, 3004-3008`）。
- **両 backend:** 層の型が `Q8_0 / Q8_0` である必要があります（`src/prefill/moe_fused_iq.cu:2920-2923, 3004-3008`）。
- `STRATA_PF_FUSED=0` または `STRATA_PF_FUSED_NATIVE=0` は native fused 経路全体を止めるため、この変数が有効でも層は fused native に進みません（`src/prefill/moe_fused_iq.cu:2891-2908`）。HIP ではさらに、`STRATA_PF_FUSED` が未設定・空の場合の既定対象形式に Q8_0 gate/up は含まれないため、通常の MMQ ありビルドでこの機能を使うには `STRATA_PF_FUSED` も有効である必要があります。明示設定は先頭文字が `1` なら on、`0` やその他の先頭文字なら off です（`src/prefill/moe_fused_iq.cu:2901-2908, 3015-3024`）。
- CUDA では `STRATA_PF_FUSED_NT=256` による NT カーネルまたは warp-specialized kernel が選ばれた場合、この Q8_0 pair は対象外です（`src/prefill/moe_fused_iq.cu:2920-2923`）。

## 実行時の詳細

CUDA と HIP の要求値は、それぞれ関数内 `static const bool` に保存され、最初の評価後はプロセス内で再読込されません。CUDA の kernel 準備結果は `g_dev` に device ごとに一度保存されます（`src/prefill/moe_fused_iq.cu:2240-2241, 2270-2272, 2379-2385, 2677-2679`）。したがって、初回評価後にプロセスの環境値を変えても判定は変わりません。

層の形式が選ばれる際、`native_supported` が gate/up と down の形式・device・スイッチ状態を照合します。条件を満たした `Q8_0 / Q8_0` 層は native fused path に入り、条件を満たさない層は通常の MMQ があれば MMQ、MMQ の tile がない場合は dequantize + FP16 GEMM に進みます（`src/prefill/moe_fused_iq.cu:2891-2923, 3004-3008`; `src/prefill/prefill.cpp:1988-2011`）。native kernel 側は形式が対象外なら `prefill fused experts (native): types %d / %d are not covered here` を stderr に出して終了コード 1 で終了しますが、通常は上流の `native_supported` 判定がその呼び出しを防ぎます（`src/prefill/moe_fused_iq.cu:3114-3128`）。

## ログと測定値

この変数専用の有効・無効ログや kernel 準備失敗の警告はありません。fused prompt expert 経路に入ると、プロセスで最初の層について stderr に `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` を一度出します。これは fused 経路全般のログで、Q8GU 専用ではありません（`src/prefill/prefill.cpp:5477-5482`）。CUDA の準備失敗は `d.q8gu` を設定しない形で処理され、上流の層選択が通常の MMQ または FP16 経路を選びます（`src/prefill/moe_fused_iq.cu:2481-2487`; `src/prefill/prefill.cpp:2001-2011`）。Strata の文書にこの変数の測定値は見つかりませんでした。

## 根拠

- 値判定・cache・CUDA kernel 準備・型ごとの選択: `src/prefill/moe_fused_iq.cu:2270-2272, 2379-2385, 2481-2487, 2570, 2891-2923, 3293-3304`
- HIP の値判定・gfx12 条件・pair 判定: `src/prefill/moe_fused_iq.cu:2390-2414, 2674-2679, 2575-2580, 3004-3008`
- MMQ なしビルドの既定注入: `include/strata/prefill/own_only_switches.hpp:18-24, 48-56`; `src/prefill/prefill.cpp:204-237`
- Qwen3.6 standalone engine の既定注入: `src/qwen35/q36_engine.cu:3940-3957`
- 不成立時の上流 fallback と native kernel の失敗経路: `src/prefill/prefill.cpp:1988-2011`; `src/prefill/moe_fused_iq.cu:3114-3128`
