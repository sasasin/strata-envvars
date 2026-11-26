# `STRATA_PREFILL_CPU_SHARE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。調査対象 checkout は `## main...origin/main` で、未コミット変更はありません。

## 役割

prompt prefill のうち、全 expert を GPU から stream する chunk より小さい staged chunk で、GPU cache にない expert の一部を decode 用 CPU pool に計算させます。CPU が担当するのはその chunk で実際に routing された非 resident expert で、残りは GPU が処理します。CPU の行を GPU に戻して既存の combine に加えるため、CPU/GPU の計算差により出力は bit-identical とは限りません（`engine/src/prefill/prefill.cpp:672-680, 6023-6057, 7588-7605`、`engine/include/strata/prefill/prefill.hpp:301-308`）。

設定値は `Prefill::cpu_share_explicit()` が初回呼び出し時に static cache し、`cpu_share_env()` が既定値や学習済み share と合わせて実際の比率を返します（`engine/src/prefill/prefill.cpp:691-704`）。環境変数を実行中に変更しても cache 済みの判定値は更新されません。serve 起動時にはメモリ不足時の警告用に環境変数を直接再確認する箇所もあります（`engine/src/program/generate.cpp:12273-12300`）。

## 値と判定

| 条件 | 判定 | 例 |
|---|---|---|
| 未設定 | `cpu_share_explicit()` は未指定 sentinel `-2`。share は実行経路が既定で arm した場合だけ有効になり、それ以外は 0（GPU 側）。 | unset |
| 値が厳密に小文字 `auto` | sentinel `-1`。有効な pool があれば share を有効にし、実行中の計測・balance で各 layer の比率を決める。 | `auto` は有効、`AUTO` は該当しない |
| それ以外 | `std::atof` で数値変換した後 `std::clamp(..., 0.0, 1.0)`。有限値は 0〜1 に制限される。文字列全体の parse 成功や末尾の確認はしない。 | `0.4` → 0.4、`1.5` → 1、`-1` → 0 |
| 空文字、数値変換できない文字列 | `atof` の変換結果 0 となり share は無効。 | `""`、`true`、`false`、`abc`、`0anything` → 0 |
| 数値 prefix の後に文字がある | `atof` が認識する数値 prefix が使われ、後続文字は無視される。 | `0.5tail` → 0.5、`1tail` → 1 |

上記は `engine/src/prefill/prefill.cpp:691-704` の実装によります。`auto` は文字列全体を `strcmp` で比較し、大文字小文字を区別します。数値値は `atof` のため、厳密な文字列形式・整数性・小数桁数の検査はありません。

## 有効になる条件

- CPU pool が設定され、対象の呼び出し経路が `applies` を true にする必要があります。`--no-pool` は pool を対象外にします。通常の単一 GPU generate は pool があれば適用候補です。serve では `STRATA_PREFILL_CPU_SHARE_BATCH=1` がない限り batch slot 使用中は pool を共用せず、設定がある場合も slot が decode 中の read では share を block します（`engine/src/program/generate.cpp:11868-11883, 12374-12380, 20757-20765, 20879`）。
- 対象は stream floor より短い staged chunk です。CPU share が arm されると `STRATA_PREFILL_CPU_SHARE_MAX`（通常 3072 tokens、アーキテクチャ既定で変わる場合あり）が stream floor になり、それ以上の chunk は全 expert streaming 経路に入ります（`engine/src/prefill/prefill.cpp:730-743, 850-878, 3868`、`engine/include/strata/prefill/prefill.hpp:310-315`）。
- unset の既定 arm は backend / device / mode に依存します。CUDA 系では通常の single GPU、pool あり、batch 無効、GPU cache に全 expert が揃っておらず、host-memory gate を通る経路が対象です。serve の CUDA layer split は layout 条件に加え、遅い link の stream floor による `arm_cpu_share_split` 条件でも既定 arm されます（`engine/src/program/generate.cpp:11890-11906, 12381-12392, 23977-23983`、`engine/src/prefill/prefill.cpp:3812-3841, 3878-3892`）。
- HIP の unset 既定は gfx12 および discrete gfx11 に限られ、gfx12 は fused IQ2_S/IQ4_XS 状態で上限が変わります。`STRATA_GFX12_DEFAULTS=0` は gfx12 既定を無効化し、gfx11 の場合は `STRATA_GFX11_DEFAULTS=0`、`STRATA_GFX11_WMMA_DEFAULTS=0` または `STRATA_DEFAULTS=026` が既定 arm を止めます。HIP gfx906 はこの既定 arm 分岐から除外されています（`engine/src/prefill/prefill.cpp:3812-3814, 3842-3864`、`engine/src/core/arch_defaults.cpp:109-116`、`engine/include/strata/core/gfx11_extra.hpp:27-36, 139-146`）。
- CUDA/HIP の既定 arm 条件を満たさなくても、明示値は pool が適用可能な経路なら有効です。特に `auto` または 0 より大きい値は既定の layout/device gate を置き換えます。ただし pool がない経路や `applies=false` の経路を作り出す設定ではありません（`engine/src/prefill/prefill.cpp:691-704, 3812-3868`）。
- host memory が既定 share に足りない場合は unset の既定 share は disarm されます。明示値が 0 以外なら要求値は保持され警告が出ます（この memory check は serve と通常 generate の双方から呼ばれます）。GPU cache が全 expert を持つ場合は unset の既定 arm をしませんが、明示値は force 可能です（`engine/src/program/generate.cpp:12273-12300, 12381-12390, 23977-23983`）。
- `STRATA_PREFILL_CPU_SHARE_MAX` は staged chunk の上限を変更し、`STRATA_PREFILL_CPU_SHARE_NT` は CPU が取れる expert の routing token 数上限を変更します。既定 arm の CUDA link rule が有効な場合は `STRATA_PREFILL_CPU_SHARE_AUTO` が link-aware の上限・expert 幅の適用を制御しますが、対象変数が明示されている場合はその自動 arm 判定を使いません（`engine/src/prefill/prefill.cpp:715-743, 3822-3835, 3880-3885`、`engine/include/strata/prefill/share_rules.hpp:89-99`）。
- `STRATA_PREFILL_STREAM_MIN` が 0 以上で設定されている場合は `stream_all_min()` がその値を直接返すため、対象変数が設定する staged/stream 境界より優先されます。単一 CUDA card の `STRATA_SWITCH_POINT` が有効なら、既定 arm 時の share 上限は card の推定 floor から算出される場合があります（既定クラスは discrete CUDA、compute capability 8.6、PCIe probe 済み。`STRATA_SWITCH_POINT=1` は他の CUDA card にも要求、`=0` は無効）。`STRATA_PF_PEER_CPU` がない peer GPU 経路では peer が担当する prompt work と pool が競合するため、CPU share 候補を作りません（`engine/src/prefill/prefill.cpp:648-658, 3816-3821, 6023-6035`、`engine/include/strata/prefill/switch_point_rule.hpp:108-122`）。
- `--draft-costs` の学習済み固定 share は、対象変数が未設定で既定 share が arm された場合の測定比率に優先して使われます。対象変数を設定した場合は対象変数側が優先されます（`engine/src/program/generate.cpp:16445-16447`、`engine/src/prefill/prefill.cpp:687-704`）。この環境変数自体に対応する CLI 引数や設定ファイル上の別名は確認できません。

## 実行時の詳細

serve は初期化時に pool / layout / GPU cache の状態を見て arm し、メモリ条件を確認します。通常 generate も prompt prefill 初期化時に arm してから chunk 用の buffer / cache loan を sizing します。そのため CLI 引数ではなくプロセス環境で指定する設定で、prompt を読む各 chunk のたびに文字列を parse し直すものではありません（`engine/src/program/generate.cpp:11862-11906, 12381-12392, 23972-23984`、`engine/src/prefill/prefill.cpp:691-704, 3868`）。

有効な chunk では routed id を読んだ後、cache 非 resident の expert から CPU が読める安定 blob を候補にし、`STRATA_PREFILL_CPU_SHARE_NT` の上限以下の expert を少ない routing 数から選びます。要求割合に `nstream` を掛けて四捨五入した数まで CPU に割り当て、1 layer あたりの CPU rows 上限も適用します。CPU の expert 計算中は GPU が残りの expert を処理し、CPU rows を GPU に戻して combine します（`engine/src/prefill/prefill.cpp:6023-6057, 6206-6235, 7588-7605`）。

`auto` と未設定の既定 share は処理時間を計測し、CPU と GPU の相対速度・layer gate に応じて比率を更新します。数値を指定した場合はその固定割合を使い、auto の timing balance / per-layer gate は通りません（`engine/src/prefill/prefill.cpp:5895-5905, 5956-5967, 6037-6039, 6237-6240, 7590-7598`）。

## ログと測定値

- CUDA の既定 arm 時は `prefill: the CPU share is ON by default for prompt chunks up to ...` を stderr に出します。link rule を使う CUDA 経路では先に `prefill: CPU share rule: ...` または layer split 用の `prefill: CPU share rule on a layer split: ...` も出ます（`engine/src/prefill/prefill.cpp:3822-3840, 3880-3892`）。
- HIP gfx12 / gfx11 の既定 arm も stderr に `prefill: the CPU share is ON by default ...` を出します（`engine/src/prefill/prefill.cpp:3842-3862`）。
- serve または通常 generate の既定 share が RAM / Windows commit 不足などで無効になると `strata: the CPU prefill share is not armed by default: ...` が出ます。明示した非zero値は保持されるものの、同じ条件では `strata: WARNING STRATA_PREFILL_CPU_SHARE=... is set and kept, but ...` が出ます。`=0` はこの明示値警告を出しません（`engine/src/program/generate.cpp:12273-12300, 23977-23983`）。
- share buffer を確保できない場合は、その engine 実行中の share を止め、`prefill: the CPU share is off for this run: the host could not give ... (RAM is short); the GPU streams every expert` を出します。CPU expert の blob が取れない場合は `prefill: a CPU expert has no blob` で prefill が失敗します（`engine/src/prefill/prefill.cpp:5878-5887, 5914-5920, 5941-5953, 7590-7592`）。
- ソースコメントは CUDA の過去の測定として、RTX 3060 / Tesla P100 / RTX 5070 で 512・1000 token の prompt が 20〜35%短縮、平均 KL 約0.004（1,024 token 未満）を記録しています。これは測定値の引用であり、この調査で再測定・再検証した値ではありません（`engine/src/prefill/prefill.cpp:681-683`）。`docs/DETAILS.md:1202-1204` にも別条件の現行 CPU share 設定・測定記載があり、実装の対象機能と概ね整合します。資料値を一般化した性能保証としては扱いません。

## 根拠

- `engine/src/prefill/prefill.cpp:672-704` — share の目的、値解析、未設定時 fallback、static cache。
- `engine/src/prefill/prefill.cpp:3812-3892` — backend ごとの既定 arm、上限・link rule、明示値の適用。
- `engine/src/program/generate.cpp:11862-11906, 12273-12300, 12374-12392, 23972-23984` — serve / generate の適用条件、memory gate、ログ。
- `engine/src/prefill/prefill.cpp:4629-4640, 5876-6057, 6206-6235, 7588-7605` — chunk gate、expert 選択と CPU/GPU 計算、結果の取り込み。
- `engine/include/strata/prefill/prefill.hpp:301-327` — pool・chunk 上限・batch・固定 share の API 契約。
- `engine/include/strata/prefill/share_rules.hpp:89-117, 141-159` — link-rule の追加条件と memory 判定。
- `engine/include/strata/prefill/switch_point_rule.hpp:108-122` — CUDA single-card の stream floor rule 条件。
- `engine/src/program/generate.cpp:16445-16447` — `--draft-costs` 固定 share の適用。
- `docs/DETAILS.md:1202-1204` — 実装資料との照合（性能値は資料記載値）。
