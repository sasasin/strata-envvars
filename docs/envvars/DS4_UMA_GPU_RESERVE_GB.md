# `DS4_UMA_GPU_RESERVE_GB`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 用の同梱エンジン `strata-dsv41` が、UMA（CPU とメモリを共有する統合 GPU）に置く expert 数を決める際、GPU の空きメモリから差し引く追加予約量を GiB 単位で上書きします。値を大きくすると GPU に置く expert の予算が減り、残りは host 側に回ります。

## 値と判定

`place_experts()` が `commit_charged()` と判定した GPU ごとに環境変数を読みます。

| 状態 | `uma_extra`（差し引く量） |
|---|---|
| 未設定 | `max_context` に応じた既定値。`(4.0 + 0.0002 × max(0, max_context - 16384))` GiB |
| 設定あり | `std::atof` で先頭から数値変換した値（GiB）。既定値を置き換える |

`std::atof` を使うため、文字列全体の妥当性検証や明示的な範囲制限はありません。空文字や数値に変換できない文字列は通常 `0` になり、数値の後ろに文字が続いていても数値部分が使われます。負値も拒否されず、その分だけ差し引き量が小さくなります。これは値を GiB から byte に換算した後、空き GPU メモリから引く量です。

## 有効になる条件

- `STRATA_BUILD_DSV41=ON` でビルドする `strata-dsv41` の経路です。この CMake option は既定で OFF です。
- `commit_charged()` が真になる必要があります。通常の実装では Windows 上の統合 GPU が対象です。別環境でも、テスト用の `DS4_COMMIT_CAP_GB` が設定されているとこの判定は真になります。
- この変数自体は UMA 判定を有効にしません。通常 GPU や `commit_charged()` が偽の経路では、この変数を読みません。

`--max-context` は未設定時の既定予約量に影響します。環境変数が設定されていれば、その既定値を置き換えます。`--reserve-mib` は別枠で空き GPU メモリから差し引かれ、`--vram-experts` は差し引き後の予算に乗算されます。

## 実行時の詳細

モデル初期化時、GPU バッファ確保後に `place_experts()` が呼ばれます。同関数は各 group の各 GPU について `cudaMemGetInfo()` で空き量を取り、次の計算で expert の budget を作ります。

```text
max(0, free_bytes - reserve_mib * 2^20 - uma_extra_bytes) * vram_experts
```

group 内では最小 budget を使います。その予算から draft/MTP expert を先に割り当て、残りで通常 expert の VRAM 配置数を決めます。したがって、この変数は確保済み GPU メモリを直接予約・解放するものではなく、expert 配置計画を保守的にする値です。負値を与えると式上の予算を増やし、GPU の実空き量を超える配置計画になり得ます。

環境変数は `place_experts()` の初期化処理中に GPU ごとに読みます。生成ごと・token ごとの再評価ではありません。配置後に残った expert がある場合、Windows の commit 制約経路では stderr に `ds4: WARNING: ... experts stay off the GPU ...` が出て、サーバー情報にも `NOTE experts: ... stay off the GPU ...` と `INFO gpu_commit_capped_gb=... pagefile_hint_gb=...` が追加されます。環境変数の値そのものを表示するログは確認できません。

## 根拠

- `CMakeLists.txt:797-810` — DeepSeek-V4.1 は別実行ファイルの経路で、`STRATA_BUILD_DSV41` は既定 OFF。
- `src/dsv41/ds4_model.cu:1086-1106` — `commit_charged()` の条件。Windows の integrated GPU、または `DS4_COMMIT_CAP_GB` 設定時に真。
- `src/dsv41/ds4_model.cu:2681-2683` — 初期化時に expert 配置計画を実行。
- `src/dsv41/ds4_model.cu:3896-3928` — UMA 追加予約の既定式、環境変数の読み取り、budget 計算。
- `src/dsv41/ds4_model.cu:3939-3968` — 予算から VRAM に配置する expert 数を決定。
- `src/dsv41/ds4_model.cu:3971-3982, 9318-9325` — 配置できず host に残った expert に関するログと server info。
- `src/dsv41/ds4_main.cpp:1212-1214` — `--max-context`、`--reserve-mib`、`--vram-experts` の CLI 設定。
- `docs/DEEPSEEK41.md:93` — 同梱 DeepSeek-V4.1 エンジンの利用概要。`DS4_UMA_GPU_RESERVE_GB` の説明や測定値は確認できません。
