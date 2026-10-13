# `STRATA_KV_RING_OFF`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

`--kv-resident` による K/V ストリーミングが有効な場合に、MTP ドラフター用 K/V のリング化を止め、ドラフターの K/V を全コンテキスト分 GPU VRAM に置く A/B 用スイッチです。コメントも「A/B only」と明記しています。通常セッション（メイン層）の K/V 配置は、この変数ではなく `STRATA_KV_MAIN_OFF` の分岐で決まります。

## 値と判定

文字列や数値として parse せず、`std::getenv("STRATA_KV_RING_OFF") != nullptr` のみを判定します。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | リング化を許可 |
| `""` を含む任意の設定値 | リング化を止める |

`1` である必要はなく、`0`、`false`、空文字も設定されていれば有効です。大文字小文字、空白、数値としての妥当性は検査されません。ソースには CLI 引数や設定ファイルによる上書きはありません。

## 有効になる条件

- `--kv-resident` に対応する `g_kv_resident` が正の値であること。0 以下なら `kv_plan()` はこの変数を調べる前に通常の全常駐計画を返します。
- MTP ドラフター状態の `ring_cells` が正であること。通常これは `--mtp-window` の値が正で `max_cells` 未満の場合に作られます（リング容量は `window + 4 * max_t + 64`）。`--mtp-window` が 0、またはコンテキスト以上ならリング計画にならず、この変数はドラフター配置を変えません。
- リング容量を丸めたページ数 `r` が全ページ数 `p.pages` 未満であること。`r >= p.pages` なら変数が未設定でも `kv_plan()` は `mode = 0` の全常駐計画を返します。
- MTP 状態を初期化する実行経路であること。MTP を使わない実行ではドラフターのリング計画がありません。

`ring_cells < 0` は pinned RAM が足りない場合などの全常駐 fallback を表し、この値より前に全常駐計画として返ります。したがってこの変数は fallback の可否を切り替えません。

## 実行時の詳細

CUDA/HIP 系の `src/core/layer.cpp` と SYCL 系の `sycl/src/core/layer.cpp` の `kv_plan()` に同じ判定があります。`ring_cells > 0` かつこの変数が設定済みなら、リング用ページ数 `r` と `mode = 2` を設定する分岐を飛ばし、初期値の `mode = 0` と全ページ分の `slots = pages` を返します。この計画は `qsa_state_bytes()` と `qsa_state_init()` の両方で使われ、K/V の全ページ分を見積もって確保し、identity page table を初期化します。設定されておらず `r < p.pages` の場合は、リング容量に必要なページ数だけ GPU 側の slot を使う `mode = 2` になり、K/V のホストコピーを用いるリング状態になります。

環境変数の値は `kv_plan()` 内の `static const bool` に保存されます。`g_kv_resident > 0` かつ `ring_cells >= 0` の呼び出しで初めて評価され、その後プロセス内で環境を変更しても再評価されません。起動時から設定しておく必要があります。

ドラフターの全常駐状態を `cudaMalloc` できない場合、MTP 初期化は `mtp: the K/V state does not fit` を返します。リングを使う通常経路で pinned RAM 確保に失敗した場合は `strata mtp: no pinned RAM left for the draft layer's K/V copy; keeping it in VRAM` を出して全常駐へ再試行しますが、この変数で最初から全常駐計画にした経路は、同じ初期化失敗時に全常駐としてエラー終了します。

## 根拠

- `src/core/layer.cpp:634-651` — `kv_plan()` の既定値、早期 return、環境変数の存在判定、リング時のページ数・mode。
- `sycl/src/core/layer.cpp:724-741` — SYCL 実装の同じ計画。
- `src/core/layer.cpp:670-705, 805-813, 848-858` — 計画をサイズ見積りと状態初期化に使い、常駐時は identity table、リング時は ring table を設定する処理。pinned K/V 確保失敗時の戻り値。
- `src/core/mtp.cpp:325-349` — `--mtp-window` からリング容量を決め、状態を確保し、pinned RAM 不足時に `ring = -1` で全常駐を再試行する経路。
- `sycl/src/core/mtp.cpp:322-350` — SYCL の同じドラフター状態計画と fallback。
- `include/strata/core/layer.hpp:279-284, 326-327` — `ring_cells` を K/V 状態の計画・初期化へ渡す API。
- `docs/DETAILS.md:80-94` — `--kv-resident` による K/V ストリーミングの一般説明。この環境変数の説明や測定値は見つかりませんでした。
