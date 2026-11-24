# `STRATA_INK_TIER_LOG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

適応型 Ink expert tier が動いている間、tier の swap 状況を追加で stderr に記録する診断スイッチです。tier の有効・無効や swap の選択自体はこの変数では変わりません。`InkHybridEngine::tier_alloc()` が値を読み、`tier_round()` が周期ログを出します（`engine/src/inkling2/cuda/ink_hybrid.cuh:2268-2296,2313-2359`）。

この実装は Inkling-2 の CUDA backend にあります。backend の定義と CUDA runner から `ink_runner.cuh` を取り込む位置は `engine/src/inkling2/cuda/CMakeLists.txt:1-7`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:1-12` です。確認したソースでは HIP 側にこのログ変数の読み取りはありません。

## 値と判定

`std::getenv("STRATA_INK_TIER_LOG") != nullptr` の結果を `tier_log` に保存します。値の parse や文字列比較はなく、未設定だけが無効です。空文字、`0`、`false`、その他の文字列はいずれも設定されていれば有効です（`engine/src/inkling2/cuda/ink_hybrid.cuh:2288-2291`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Ink CUDA runner で tier が初期化された場合 | 周期ログなし | 空文字、`0`、`false`、その他任意の値 | なし（変数が存在すれば有効） |

## 有効になる条件

- Inkling-2 CUDA runner の適応型 tier が有効で、`tier_alloc()` が成功することが必要です。`tier_alloc()` は class と pool が空でないこと、engine が active で `d_use_cnt` があることを前提にし、pool の `cudaMalloc` が失敗すると tier を有効にせず戻ります（`engine/src/inkling2/cuda/ink_hybrid.cuh:2268-2272,2290-2293`）。
- runner の通常経路では、host に置く expert があり、VRAM に置く expert もあり、SSD expert を使わず、tier が `STRATA_INK_TIER` で無効化されていないことが候補条件です。さらに、VRAM 側 expert の host copy を含む RAM 条件を満たす必要があります（`engine/src/inkling2/cuda/ink_runner.cuh:470-480,1342-1352`）。
- 複数 GPU または SSD などの構成条件も分岐を制限します。第二の runner 経路では `ls_active` と `ep2_active` のどちらも false であることが必要です（`engine/src/inkling2/cuda/ink_runner.cuh:1342-1352`）。
- 条件を満たさない、`STRATA_INK_TIER` が無効、または tier pool の確保に失敗した場合、この変数による周期ログは出ません。RAM 不足や VRAM 不足の経路には `[InkTier] off: ...` の理由行がありますが、`STRATA_INK_TIER_LOG` 自体の値による警告・失敗処理はありません（`engine/src/inkling2/cuda/ink_runner.cuh:473-480,504-522,1346-1352,1383-1400`）。
- CLI 引数による上書きはこの変数の読み取り・使用箇所では確認できません。別の環境変数 `STRATA_INK_TIER` はtier自体の有効条件に使われ、値の先頭文字が `0` なら無効になります（`engine/src/inkling2/cuda/ink_hybrid.cuh:2185-2187`）。

## 実行時の詳細

設定有無を読むのは `tier_alloc()` の初期化時だけで、その結果は `InkHybridEngine` の `tier_log` メンバーに保持されます。初期化後にプロセス環境を変更しても、その engine instance の状態には反映されません。別の engine instance で再度 `tier_alloc()` が呼ばれれば、その時点で読み直します（`engine/src/inkling2/cuda/ink_hybrid.cuh:2181-2182,2268-2291`）。

適応型 tier が有効な場合、decode 後の `step_after()` が使用量の snapshot を扱い、条件が整ったところで `tier_round()` を実行します。各 round は累積 swap 数を更新し、`tier_log` が true で round 番号を 64 で割った余りが 1 のとき、すなわち 1、65、129…回目にログを出します。ログは swap 数が 0 の round でも出ます（`engine/src/inkling2/cuda/ink_hybrid.cuh:2313-2359,2361-2386`）。

## ログと測定値

周期ログは stderr に次の形式で出ます（書式文字列は実装どおりです）。

```text
[InkTier] round %llu: %d swaps (total %llu)
```

このほか、tier 初期化時には有効化行、engine 解放時には round / swap の合計行が stderr に出ます。これら2種類の行は `STRATA_INK_TIER_LOG` が未設定でも tier が有効なら出るため、この変数が追加する周期ログとは区別してください。条件を満たさない場合、tier に関する行が出ないか、runner が出す `[InkTier] off: ...` 行だけになります（`engine/src/inkling2/cuda/ink_hybrid.cuh:2291-2296,2355-2358,2389-2395`）。

この変数についての測定値は、参照した Strata 文書・実装にはありません。`docs/SETTINGS.md:409` は `STRATA_INK_TIER` を NVIDIA / AMD 向けの on/off 設定として載せていますが、`STRATA_INK_TIER_LOG` の項目や挙動は説明していません。同資料の tier 対応表だけでは、このログ変数が AMD backend に適用されるとは確認できません。

## 根拠

- `engine/src/inkling2/cuda/ink_hybrid.cuh:2181-2187,2268-2296` — tier 状態、関連する tier 有効化変数、初期化時のログ変数読み取り。
- `engine/src/inkling2/cuda/ink_hybrid.cuh:2313-2359,2361-2395` — round の処理、周期ログ条件、解放時の集計ログ。
- `engine/src/inkling2/cuda/ink_runner.cuh:470-522,1342-1400` — runner ごとの tier 有効条件、RAM / VRAM による非有効化経路。
- `engine/src/inkling2/cuda/CMakeLists.txt:1-7`、`engine/src/inkling2/cuda/ink_cuda_backend.cu:1-12` — CUDA backend の位置づけと runner の取り込み。
- `docs/SETTINGS.md:409` — 関連する `STRATA_INK_TIER` の一覧記載。対象のログ変数自体の動作根拠ではありません。
