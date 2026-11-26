# `STRATA_PF_HC_REGION`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

GPU prefill の hyper-connection 読み取り用 scratch（`xn16`、`lo`、`lo16`、`gated` と条件付きの BF16x2 low halves）を、通常の chunk 専用領域ではなく attention/MoE と共有する一時領域の先頭に重ねて置く opt-in です。`Prefill::carve` が通常領域からこれらを外し、共有領域の容量計算で `hc_set_bytes` のサイズも候補に含めます。計算カーネルや値の計算式を切り替える環境変数ではありません。実装コメントは同じ kernel・同じ値で結果の bit は同じと説明しています（`engine/src/prefill/prefill.cpp:2246-2254,2760-2793,2835-2842`）。

設定一覧では NVIDIA と AMD 向けに掲載されています（`docs/SETTINGS.md:219-220`）。Strata の詳細表は関連する scratch 共有の記述を CUDA の prompt path の項に置いています（`docs/DETAILS.md:1278`）。実装上は GPU prefill の共有 `prefill.cpp` にあり、ここでモデルの出力や生成 token を変更する分岐はありません。

## 値と判定

`pf_hc_region()` の初回呼び出し時に `std::getenv` で取得し、`std::atoi(v) != 0` で判定します。未設定は無効、空文字も `atoi` が 0 を返すため無効です。文字列全体の妥当性検証はしません。`atoi` が先頭の空白と符号付き10進整数を読める範囲で変換するため、例のように先頭の整数部分が 0 以外なら有効になり、先頭が数値でない文字列は 0 扱いです（`engine/src/prefill/prefill.cpp:2251-2254`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_GR_UNFUSED` が無効 | `pf_hc_region` の設定値は無効 | `1`、`-1`、`2tail`（`atoi` の結果が非0） | 空文字、`0`、`0anything`、`true`、`  `（結果が0） |
| `STRATA_GR_UNFUSED` が有効 | 無効 | なし（設定値が非0でも `!gr_unfused()` 条件により機能は無効） | すべて |

`atoi` の変換範囲外の値について Strata に独自の検査やエラー処理はありません。読み取り結果は関数内 `static const bool` に保存されます。したがって初回呼び出し以後の環境変更は反映されません。依存する `STRATA_GR_UNFUSED` も別の関数内 `static` で初回評価されます（`engine/src/prefill/prefill.cpp:1055-1059,2251-2254`）。

## 有効になる条件

- GPU prefill の `Prefill::carve` が実行される経路であること。CPU 経路や prefill を使わない処理にはこの割り当て変更は適用されません（`engine/src/prefill/prefill.cpp:2760-2773`）。
- `STRATA_PF_HC_REGION` のキャッシュ値が非0であること。
- `STRATA_GR_UNFUSED` のキャッシュ値が無効であること。これが有効なら `pf_hc_region()` は false を返し、scratch は通常の chunk 領域に割り当てられます（`engine/src/prefill/prefill.cpp:1055-1059,2251-2254,2769-2779`）。
- 追加の `--prefill` 値、モデル型、MMQ/fused-MoE 判定による `pf_hc_region()` 内のゲートはありません。chunk サイズは scratch サイズ・共有領域サイズに影響しますが、この変数の判定を上書きしません（`engine/src/prefill/prefill.cpp:2251-2259,2769-2793`）。

## 実行時の詳細

`Prefill::carve` は `hcr` を一度求め、true の場合は `xn16`・`lo`・`lo16`・`gated` と、`bf16x2_hc(m.f16_io)` が true のときの `xn16_lo`・`lo16_lo` を通常の `Alloc` から取らず、attention/MoE と共有する `base` から別の `Alloc h` で取ります。共有領域は GDN、QSA、MoE、HC scratch 各セットの必要量の最大値で確保されるため、HC scratch が他セットより大きい場合だけ共有領域のサイズを押し上げます。false の場合は同じ scratch を通常領域から割り当て、共有領域サイズの候補には加えません（`engine/src/prefill/prefill.cpp:2255-2260,2769-2793,2835-2842`）。

`Prefill::bytes_needed_impl` も同じ `pf_hc_region()` 判定を使い、true の場合は通常領域からの scratch 計上を省き、共有領域の最大サイズに HC scratch を含めます。実割り当てと事前の必要量見積りで判定を揃える実装です（`engine/src/prefill/prefill.cpp:3718-3755`）。

環境変数の値は CLI 引数や設定ファイルからは読み替えられません。`--prefill` は chunk の選択・サイズに関係しますが、この環境変数とは独立です。評価はプロセス全体で一度の static cache で、リクエストごとの再読込はしません（`engine/src/prefill/prefill.cpp:2251-2254,3718-3755`）。コメント上の目安は「region 外の scratch を約 63 KB/token 分減らす（region はすでにこのセットより大きい）」ですが、実際の内訳は chunk、padding、BF16x2 条件によります（`engine/src/prefill/prefill.cpp:2246-2259`）。

## ログと測定値

`hcr` が true なら carve ごと（ソースコメント上は chunk サイズごとの layout）に stderr へ `strata prefill: chunk %zu tokens: STRATA_PF_HC_REGION on (the hyper-connection read's scratch is in the shared region);` を出します。無効時や `STRATA_GR_UNFUSED` によって抑止された場合、この変数についての行は出ません（`engine/src/prefill/prefill.cpp:2912-2919`）。

scratch の割り当てに失敗した場合は初期化または relayout が false を返し、呼び出し元に `prefill: device buffers for a chunk of <N> tokens do not fit (<free> of <total> MiB free at the failure; <taken> MiB taken, the failing buffer wanted <size> MiB)` 形式のエラー文字列を返します。このエラーは専用の環境変数エラーではなく、GPU buffer carve 全般の失敗経路です（`engine/src/prefill/prefill.cpp:2737-2746,2949-2957`）。

`docs/DETAILS.md` は `STRATA_PF_GROUP_SCRATCH=1` との併用を含む CUDA/MMQ の説明として、cache slot を 0.3–0.5 GiB 空ける測定と、`STRATA_PREFILL_CPU_SHARE=0` のときに限った emulated 8 GB card での +7〜11% を記載しています。これは二変数を併用した記述であり、この変数単独の効果や他環境での速度を示すものではありません（`docs/DETAILS.md:1278`）。

## 根拠

- `engine/src/prefill/prefill.cpp:2246-2259` — 用途、読み取り・変換、キャッシュ、unfused 条件、HC scratch のサイズ。
- `engine/src/prefill/prefill.cpp:2760-2793,2835-2842` — scratch の通常領域からの除外、共有領域のサイズ計算と実割り当て。
- `engine/src/prefill/prefill.cpp:2912-2919` — 有効時の stderr ログ。
- `engine/src/prefill/prefill.cpp:3718-3755` — 必要量見積り側の同じ条件。
- `engine/src/prefill/prefill.cpp:2737-2746,2949-2957` — carve 失敗時のエラー経路。
- `docs/SETTINGS.md:219-220`, `docs/DETAILS.md:1278` — 設定一覧と併用条件付きの説明・測定値。
