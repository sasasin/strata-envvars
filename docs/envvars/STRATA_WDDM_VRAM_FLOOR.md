# `STRATA_WDDM_VRAM_FLOOR`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Windows の離散 WDDM GPU で `--expert-cache auto` を使うとき、カード容量に応じた VRAM 予約下限を適用するかを切り替える。通常（未設定）は既定の 700 MiB などの予約値を 448～1,280 MiB の下限まで引き上げ、自動 expert-cache に使うスロットを少なくして、確保後に空ける VRAM を増やす。値の先頭文字が `0` ならこの引き上げを抑止する。読み取りと予約値の更新は `engine/src/program/generate.cpp` の自動キャッシュ初期化内で行われる（同ファイル: 9001-9005, 9026-9036）。

## 値と判定

`std::getenv` の戻り値を `wddm_effective_reserve_mib` に渡し、関数は未設定でない値の **先頭文字** が `'0'` かだけを判定する。文字列全体の比較、数値変換、空白除去はしない（`engine/src/program/generate.cpp`: 9028-9030、`engine/include/strata/core/low_vram_rules.hpp`: 65-73）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Windows、離散 GPU、WDDM 判定成立、`--expert-cache auto` | 下限適用。既定予約 700 MiB は容量に応じて 448 / 640 / 960 / 1,280 MiB に上がり得る | 先頭が `1`～`9`、空文字、空白など。下限適用 | `0`、`0anything`、`00` など先頭が `0` の任意の文字列。下限適用を抑止 |
| それ以外 | 読み取り箇所に到達しないか、WDDM 予約関数が予約値を変更しない | 影響なし | 影響なし |

空文字は環境変数として設定済みでも `floor_env[0]` が NUL なので無効化条件にはならず、下限適用を許す。`false`、`off`、`true` は先頭が `0` ではないため抑止しない。文字列は大文字小文字を変換せず、数値として妥当かも検証しない。下限は `total_vram_bytes` で段階化される: 15 GiB 以上は 1,280 MiB、9.5 GiB 以上 15 GiB 未満は 960 MiB、5.5 GiB 以上 9.5 GiB 未満は 640 MiB、それ未満は 448 MiB。容量 0 の場合は予約値を変更しない（`engine/include/strata/core/low_vram_rules.hpp`: 26-31, 41-59, 68-73）。

既定の予約は 700 MiB（`generate.cpp`: 958-961）。下限より大きい予約は維持される。`--vram-reserve-mib N` を明示していて現在値が下限未満なら、通常はその値を維持する。ただし Vision 経路で明示値が既定値 700 MiB のままの場合は、互換性のため下限まで引き上げられる（`low_vram_rules.hpp`: 71-73）。CLI 引数は `vram_reserve_given` を立て、環境変数が有効な場合の「下限未満の明示値を維持する」判定に使われる（`generate.cpp`: 3992）。

## 有効になる条件

- `o.expert_cache < 0`、すなわち `--expert-cache auto` の経路であること。既定も auto で、`--expert-cache N` の固定値では環境変数を読み取らない（`engine/src/program/generate.cpp`: 958-961, 3980-3982, 9005）。
- `_WIN32` かつ `STRATA_GPU_METAL` ではないビルドであること。デバイス照会と環境変数の処理全体がこのプリプロセッサ条件内にある（同ファイル: 9014-9043）。
- デバイス照会・`cudaMemGetInfo` が成功し、離散 GPU と判定され、総 VRAM が 0 より大きいこと。Windows CUDA では TCC を除外し、HIP では `tcc` を false として判定する。統合 GPU は除外される（同ファイル: 9016-9030、`engine/include/strata/core/low_vram_rules.hpp`: 47-59）。
- 予約値が容量別下限より低いこと。値がすでに下限以上なら環境変数が unset でも引き上げは発生しない。明示した CLI 予約が下限未満なら、Vision の既定値 700 MiB の例外を除き維持される（`low_vram_rules.hpp`: 68-73）。
- 後続の Windows HIP 自動キャッシュ経路では、別の条件（Windows HIP、非統合 GPU、カード総量 15 GiB 以上、予約未指定）で独立した 2,560 MiB の予約引き上げがある。この分岐は `STRATA_WDDM_VRAM_FLOOR` を参照しないため、この変数を `0` で抑止しても該当条件なら 2,560 MiB が適用され得る（`generate.cpp`: 9083-9100）。

## 実行時の詳細

引数解析後、自動 expert-cache の VRAM 空き量を測る段階で CUDA/HIP デバイス情報と総 VRAM を取得し、WDDM 離散 GPU と確認できたときに環境変数を一度読み取る。関数内 static cache はなく、この起動時の判定以降にプロセス環境を変えても反映されない。サーバーモード専用の条件ではなく、`generate` の自動キャッシュ初期化経路に共通する（`engine/src/program/generate.cpp`: 9005-9036）。

下限が適用されると `o.vram_reserve_mib` が更新され、その予約に加え、prefill バッファ、draft head、後続の遅延確保分などを自動キャッシュのサイズ計算から差し引く。生成される token や選択結果をこの変数が直接変更するコードはない（`generate.cpp`: 9127-9155）。WDDM 経路では確保後に空き VRAM を再確認し、予約値を保つため必要なら expert-cache を小さくする。したがって `=0` はこの容量別下限を外すだけで、確保後の再確認・縮小や後段 HIP 用予約を無効化しない（同ファイル: 9567-9632）。

デバイス照会または VRAM 情報取得が失敗すると、該当エラーを `cudaGetLastError()` で消費してこの WDDM 下限判定を行わない。後続の通常の自動サイズ計算は続く（`generate.cpp`: 9019-9041）。

## ログと測定値

予約値が実際に引き上げられた場合だけ、stderr に次の行を出し、引き上げ後の予約値を表示する。下限が既に満たされている場合、`STRATA_WDDM_VRAM_FLOOR=0` で抑止された場合、または明示予約が維持された場合、この行は出ない（`engine/src/program/generate.cpp`: 9031-9037）。

```text
strata generate: Windows WDDM (%.1f GiB): keeping %d MiB VRAM reserve (was %d MiB) so the driver does not page GPU memory to host RAM (#6128/#5915; STRATA_WDDM_VRAM_FLOOR=0 or explicit --vram-reserve-mib N overrides)
```

自動キャッシュに空きが足りない場合は別途 `only ... MiB free once the slots are written ...; shrinking the expert cache` を出してキャッシュを縮小する。固定 cache の確保失敗では終了コード 1 の経路があるが、この環境変数自体が終了条件を設けるものではない（`generate.cpp`: 9576-9610, 9617-9632）。`docs/DETAILS.md` は auto cache の確保後再確認・縮小と明示 cache の違いを説明しており、ソースのこの挙動と整合する（`docs/DETAILS.md`: 439-449）。この変数に固有の測定値は同資料に記載されていない。

## 根拠

- `engine/src/program/generate.cpp:958-961,3992` — 既定予約値と明示 CLI 予約の記録。
- `engine/src/program/generate.cpp:9001-9043` — auto 条件、Windows build guard、WDDM GPU 判定、環境変数読取、予約更新とログ。
- `engine/include/strata/core/low_vram_rules.hpp:41-73` — 容量別下限と値判定・CLI/Vision 例外。
- `engine/src/program/generate.cpp:9083-9100,9127-9155,9567-9632` — 別個の Windows HIP 予約、auto cache の予約計算、確保後の縮小確認。
- `docs/DETAILS.md:439-449` — cache 自動サイズと確保後確認に関する説明。
