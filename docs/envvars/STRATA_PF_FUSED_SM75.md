# `STRATA_PF_FUSED_SM75`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の compute capability 7.5（Turing、sm_75）で、Strata の fused prefill expert kernel を利用可能にする opt-in 変数。Q2_0 pack 用 `moe_fused.cu` は `dev_info()` でこの値を確認し、sm_75 用カーネルの利用可否を決める。native pack 用 `moe_fused_iq.cu` も `dev_info()` で読み、Q2_0 / Q2_0 と、設定済みの i-quant などの組み合わせのカーネルを準備する（`engine/src/prefill/moe_fused.cu:649-701`、`engine/src/prefill/moe_fused_iq.cu:2847-2940`）。

この変数だけでは通常の fused prefill を有効にしない。Q2_0 pack 用 `moe_fused.cu` は `STRATA_PF_FUSED` が unset なら有効扱いだが、native pack 用 `moe_fused_iq.cu` は unset の `STRATA_PF_FUSED` を Turing の fused native path を選ぶ既定分岐から除外するため、通常の CUDA build では native pack に `STRATA_PF_FUSED=1` も必要。MMQ を含まない CUDA build は、利用者が設定していなければ起動前に `STRATA_PF_FUSED_SM75=1` と `STRATA_PF_FUSED=1` を設定する（`engine/src/prefill/moe_fused_iq.cu:3415-3432,3517-3533,3581-3586`、`engine/src/prefill/prefill.cpp:223-255`）。

Q2_0 pack では sm_75 用の fused experts が利用可能になり、native pack では準備・適用に成功した層だけが native fused experts を使う。native pack の対応しない層は `native_supported()` が false を返し、呼び出し側の通常の経路に残る。変数は GPU 構成、モデル形式、応答内容を直接指定するものではない（`engine/src/prefill/prefill.cpp:778-805`）。対象 layer が native 対応外なら MMQ がある build では MMQ 側に残り、MMQ なし build では fused 専用層として扱われない。

## 値と判定

CUDA の両読み取り箇所は `std::getenv()` の結果が null でなく、`v[0] == '1'` のときだけ有効とする。文字列全体や数値としての妥当性は検査せず、先頭 1 文字だけを大文字小文字の区別なく（文字比較なので該当なし）判定する。空文字は設定済みだが無効。`1anything` は有効、`0anything`、`true`、空白で始まる ` 1` は無効。未設定は無効（通常 build）だが、MMQ なし build では下記の起動時既定値が入る（`engine/src/prefill/moe_fused.cu:683-685`、`engine/src/prefill/moe_fused_iq.cu:2899-2901`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA build、MMQ あり | 無効 | `1`, `1anything` | 空文字、`0`, `0anything`, `true`, ` 1` |
| CUDA build、MMQ なし | 起動初期化が変数を未設定時だけ `1` にする | 上記に加え、自動設定された `1` | 利用者が値を設定した場合は値を保持し、`0`, 空文字などは無効のまま |
| HIP build | この変数を読み取らない | 該当なし | 該当なし |

CUDA で読み取り値を無効にする別のサブスイッチがある。native pack の i-quant gate/up と IQ4_NL down は `STRATA_PF_FUSED_SM75_IQ=0` で設定対象外になり、K-quant / Q8_0 系は `STRATA_PF_FUSED_SM75_KQ=0` で対象外になる。どちらも先頭文字が `0` かを見ており、これらの値が `0` 以外なら当該抑止条件にはならない（`engine/src/prefill/moe_fused_iq.cu:2903-2919`）。

## 有効になる条件

- 実装対象は CUDA である。HIP build では Q2_0 pack 側が `__HIPCC__` 分岐で sm_75 の確認を行わず、native pack 側も HIP 用 `dev_info()` 分岐から早期 return する（`engine/src/prefill/moe_fused.cu:656-677`、`engine/src/prefill/moe_fused_iq.cu:2854-2886`）。
- 対象 GPU が compute capability 7.5 であること。値が有効でも 7.5 未満では Q2_0 側は利用不可、native 側は Turing 用 setup に入らない。8.0 以上の GPU にこの変数を設定しても sm_75 用の有効化には使われない（`engine/src/prefill/moe_fused.cu:682-686`、`engine/src/prefill/moe_fused_iq.cu:2896-2905`）。
- build に対象カーネルの device code が含まれ、関数属性・PTX version・shared memory・occupancy の setup 条件を満たすこと。Q2_0 側は `expert_kernel` の属性と必要 PTX version を確認し、native 側は個々の instance を setup する。失敗した setup は利用可能状態にならない（`engine/src/prefill/moe_fused.cu:686-700`、`engine/src/prefill/moe_fused_iq.cu:2748-2775`）。
- Q2_0 pack 側の実行にも `STRATA_PF_FUSED` の有効判定が必要（unset は有効、先頭文字 `0` は無効）。native pack 側は Turing 上、通常の default-on 対象から除外されるため、通常 build では `STRATA_PF_FUSED=1` が必要。`STRATA_PF_FUSED=0` は native fused path を無効にする（`engine/src/prefill/moe_fused.cu:712-729`、`engine/src/prefill/moe_fused_iq.cu:3425-3432,3517-3533,3581-3586`）。
- native pack の基本 Turing pair は Q2_0 gate/up と Q2_0 down。i-quant は `kT75Formats` に含まれ、gate/up または down の instance setup が成功した型のみで、down 側は Q2_0、準備済み IQ4_NL、または別途有効な Q8_0 down などの条件に制限される。Q2_0 gate/up は Q2_0 down との組だけを受け付ける（`engine/src/prefill/moe_fused_iq.cu:2903-2912,3223-3232`）。
- native pack の K-quant / Q8_0 family を Turing で使うには `STRATA_PF_FUSED_SM75_KQ` が `0` でなく、さらに対応する通常の `STRATA_PF_FUSED_KQ=1`、`STRATA_PF_FUSED_Q8D=1`、`STRATA_PF_FUSED_Q8GU=1`、または `STRATA_PF_FUSED_Q6K=1` 等の setup 条件が必要。未設定の各追加スイッチはそれぞれ opt-in されない（`engine/src/prefill/moe_fused_iq.cu:2916-2936,3225-3231`）。
- `STRATA_PF_FUSED_SM75_IQ=0` は i-quant setup を省き、`STRATA_PF_FUSED_SM75_KQ=0` は KQ/Q8D/Q8GU/Q6K の setup を省く。Q2_0 / Q2_0 の canonical setup はこれらのスイッチとは別に行われる（`engine/src/prefill/moe_fused_iq.cu:2903-2919`）。

## 実行時の詳細

両 CUDA 実装とも、GPU ごとの `dev_info()` 初回評価でデバイス情報をキャッシュする。`STRATA_PF_FUSED_SM75` の値自体も関数内 `static const bool` の初回評価でキャッシュされ、プロセス実行中の環境変更は反映されない。Q2_0 pack 側は対象デバイスの compute capability が 75 以上で、7.5 未満の例外がなく、カーネル属性が適合したとき `available()` を true にする。`enabled()` はさらに `STRATA_PF_FUSED` の既定／明示値と prefill override を判定する（`engine/src/prefill/moe_fused.cu:649-701,707-729`）。

native pack 側は対象デバイスの属性を取得後、CC 7.5 でこの変数が有効なときに Turing 用の Q2_0 pair の setup を行う。標準 setup は gate/up と down の各 64-row / 128-row instance を検査する。i-quant setup では 128-row instance が必須で、64-row instance は shared memory と occupancy が適合するときだけ追加される（`engine/src/prefill/moe_fused_iq.cu:2748-2775,2896-2912`）。native 層の選択は `native_supported()` の型・device・switch 条件も通る必要があり、実際の launch は `experts_native()` から行われる（`engine/src/prefill/moe_fused_iq.cu:3415-3432,3529-3586,3686-3700`）。

MMQ なし build では静的初期化が `main()` より前に走り、`getenv(name) == nullptr` の場合だけ `setenv(name, "1", 0)`（Windows では `_putenv_s`）で既定値を入れる。利用者が空文字や `0` を含む何らかの値をすでに設定していれば上書きしない。HIP の既定 switch list にはこの変数が含まれない（`engine/src/prefill/prefill.cpp:223-255`、`engine/include/strata/prefill/own_only_switches.hpp:18-25,48-56`）。また Qwen3.6 entry は MMQ なしの場合に限って、この変数が未設定なら同じ変数を `1` にする。`strata --model` と standalone `strata-q36` の両 entry に適用され、利用者が設定した値は保持する（`engine/include/strata/prefill/own_only_switches.hpp:75-82`、`engine/src/qwen35/q36_engine.cu:5431-5454`）。

## ログと測定値

この変数を有効／無効にしたことだけを示す専用ログは確認できない。native kernel launch に対応しない型の組み合わせが直接 `experts_native()` に到達した場合は stderr に `prefill fused experts (native): types %d / %d are not covered here` を出して `exit(1)` する。通常の選択では先に `native_supported()` が型や device を確認するため、この失敗経路は未対応 pair を誤って launch 関数へ渡した場合のガードである（`engine/src/prefill/moe_fused_iq.cu:3691-3700`）。

`docs/DETAILS.md:1336-1345` は sm_75 kernels を opt-in とし、記載の kernels は置換対象と bitwise equal と述べる一方、チーム内に sm_75 card がなく確認できていないと明記している。これは文書の記載であり、本調査では build・GPU 実行・測定をしていないため独立検証していない。`docs/SETTINGS.md:217` は NVIDIA and AMD と記載するが、現行の読み取りコードは CUDA のみで、HIP は対象外である。

## 根拠

- `engine/src/prefill/moe_fused.cu:649-729` — Q2_0 pack のデバイス判定、環境値 cache、enabled/requested 判定。
- `engine/src/prefill/moe_fused_iq.cu:2748-2775,2847-2940` — native kernels の setup、デバイス別 cache、Turing format setup と補助スイッチ。
- `engine/src/prefill/moe_fused_iq.cu:3223-3239,3415-3432,3517-3586,3686-3700` — Turing pair 判定、native 経路の適用・launch・失敗ガード。
- `engine/src/prefill/prefill.cpp:223-255`、`engine/include/strata/prefill/own_only_switches.hpp:18-25,48-56,75-82`、`engine/src/qwen35/q36_engine.cu:5431-5454` — MMQ なし build の既定値と Qwen3.6 entry の設定。
- `engine/src/prefill/prefill.cpp:778-805` — native layer が未対応時の fused layout 判定。
- `docs/DETAILS.md:1336-1345`、`docs/SETTINGS.md:217` — 補助的な文書記述と実装との差。
