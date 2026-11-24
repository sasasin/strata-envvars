# `STRATA_HIP_HYB_PROF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

HIP backend の hybrid decode MoE 経路で、router 同期、GPU 処理と CPU 待ちの時間区分を計測して定期的に stderr へ出す診断用フラグ。`HybProf` の `on` が true でも MoE の計算経路や結果を切り替える処理はなく、計時・カウンター加算・レポートだけが有効になる（`engine/src/inkling2/hip/ink_hip_hybrid.hpp:31-50`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:4425-4429,4599-4619`）。

HIP backend クラスは `HybProf hyb_prof_` をメンバーとして持ち、backend オブジェクト構築時にこのフラグを読む（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:5826-5829`）。

## 値と判定

`std::getenv` で設定有無を確認したうえで、文字列の先頭 1 文字だけを `'1'` と比較する。文字列全体の parse、数値変換、空白除去、大文字小文字変換はしない（`engine/src/inkling2/hip/ink_hip_hybrid.hpp:39-42`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HIP backend の `HybProf` 構築時 | `on=false` | 先頭が `1`（`1`, `10`, `1anything`） | 空文字、`0`, `true`, `True`, ` 1`, `x1` |

CLI 引数・設定ファイル・他の環境変数による上書きや優先順位はない。この環境変数の読み取り箇所は `engine/src/inkling2/hip/ink_hip_hybrid.hpp:40` のみ。

## 有効になる条件

- HIP backend をビルドして、その backend オブジェクトが生成されること。読み取りは `HybProf` のコンストラクターで行われる（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:21,5826-5829`）。
- hybrid controller が active で、MoE dispatch が `B <= 16` の hybrid decode 分岐に入ること。このときだけカウンターが進みレポートされる（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:4425-4428,4611-4619`）。
- controller は `max_exp_bytes > 0` かつ GPU に全 expert が載らないときに初期化される。初期化が失敗すれば backend 初期化も失敗する（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1395-1401`）。
- GPU resident の通常経路や `B > 16` の hybrid prefill 経路では、この計測・レポート分岐を通らない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:4160-4165,4425,4621-4623`）。

## 実行時の詳細

フラグは backend オブジェクト構築時に一度読み、`HybProf::on` に保持する。各 hybrid decode MoE visit の冒頭から、router の ID・重み・入力ベクトルの device-to-host 転送と stream 同期完了までを `route_sync` として測る。続く GPU/CPU dispatch と GPU 処理区間を `launch_to_wait`、CPU pool の `wait_and_reduce` を `cpu_wait`、後処理を `rest` に累積する（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:4428-4439,4549-4609,4611-4618`）。

カウンターは backend オブジェクト内で累積し、`visits` が 480 の倍数になるたびに報告する。環境変数をプロセス実行中に変更しても、保持済みの `on` は再評価されない（`engine/src/inkling2/hip/ink_hip_hybrid.hpp:32-42,43-50`）。

## ログと測定値

有効時は 480 visits ごとに次の形式を stderr に出す。`route-sync`、`gpu+launch`、`cpu-wait`、`rest` は `visits / 48.0` を token 数として換算した 1 token あたりの累積ミリ秒、`cpu jobs/visit` は累積 CPU job 数を visits で割った値。コードコメントは 480 visits を 10 tokens と説明しているが、これは計測器の出力単位の説明であり、性能ベンチマーク結果ではない（`engine/src/inkling2/hip/ink_hip_hybrid.hpp:31,43-50`）。

```text
[hyb-prof] %ld visits: per token ms: route-sync %.2f | gpu+launch %.2f | cpu-wait %.2f | rest %.2f | cpu jobs/visit %.2f
```

unset または先頭文字が `1` 以外の場合、および上記 hybrid decode 分岐を通らない場合、この profiler のログは出ない。環境変数自体による警告・エラー・終了経路はない。実行時測定値の記録は行わず、ログに表示する累積値だけを計算する。

## 根拠

- `engine/src/inkling2/hip/ink_hip_hybrid.hpp:31-50` — フラグ判定、初期値、報告条件・文言・換算式。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:21,4425-4439,4599-4619,5826-5829` — HIP backend への組み込み、計測区間、集計・報告、メンバーの生成。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1395-1401,4160-4165,4621-4623` — hybrid controller の初期化条件と profiler を通らない MoE 経路。
