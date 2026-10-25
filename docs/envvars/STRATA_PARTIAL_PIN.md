# `STRATA_PARTIAL_PIN`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版 `FileExpertSource` の resident RAM complement で、page-locked allocation に失敗して通常の `malloc` に fallback した場合、先頭の一部を GPU から直接読む候補として扱うための opt-in です。主に `--resident-experts` または `--resident-budget-gib` と PCIe miss 処理を組み合わせる経路に関係します。

ただし、現 HEAD の SYCL 実装では既存ホストメモリをデバイス用に登録する処理が移植時の no-op になっています。環境変数を有効にするとコード上は prefix を「pinned」として記録しますが、実際の GPU 登録が行われることはソースから確認できません。`docs/UNSLOTH_Q4.md` の説明は「GPU driver に登録する」としていますが、この実装とは一致しません。

## 値と判定

| 値 | 判定 |
|---|---|
| unset | 無効 |
| 空文字 | `atoi("") == 0` のため無効 |
| 整数として 0 になる文字列（例: `0`, `false`, `abc`） | 無効 |
| `atoi` が 0 以外を返す文字列（例: `1`, `-1`, `2tail`） | 有効 |

文字列全体の検証はせず、C の `atoi` で変換します。判定結果は関数内の `static const bool` に保存され、最初にこの経路へ入った後の環境変更は反映されません。参照: `sycl/src/core/expert_source.cpp:1936-1939`。

## 有効になる条件

次の条件がそろったときだけ、この判定が使われます。

- SYCL 実装の `FileExpertSource::pin_cache_complement()` が呼ばれる。呼び出し元では resident CPU experts モードの場合に構築されます（`sycl/src/program/generate.cpp:6357-6373`）。
- `pin` が true で、最初の `sycl::malloc_host` による page-locked allocation が失敗し、`malloc` の fallback に進む。
- `budget_bytes > 0` で、`STRATA_PARTIAL_PIN` が有効。

`--resident-experts` と `--resident-budget-gib` は `resident_pin` を true にしますが、`STRATA_RESIDENT_PIN=0` がその設定を false に上書きします（`sycl/src/program/generate.cpp:1931-1950`）。最初の `sycl::malloc_host` allocation が成功すれば通常の全体 pinned 経路になり、この変数による prefix 処理は行いません。`pin` が false の場合もこの分岐には入りません（`sycl/src/core/expert_source.cpp:1860-1863,1911-1928`）。

## 実行時の詳細

有効時、コードは登録上限を `min(complement bytes, STRATA_PARTIAL_PIN_GIB)` 相当として設定し、2 GiB 刻みで下げながら expert blob の途中を切らない位置を探します。`STRATA_PARTIAL_PIN_GIB` は `atof` で読み、正の値なら GiB に換算します。それ以外（unset、空、非数値、0、負数）は 24 GiB が既定値です。正の小数は byte 換算後 `uint64_t` に変換されます。こちらの値も関数内 `static` に一度だけ保存されます（`sycl/src/core/expert_source.cpp:1940-1957`）。

見つかった prefix については、SYCL 移植時に `cudaHostRegister` が置換されたコメントの直後で `if (0 == 0)` とし、alias に `arena` 自身を設定して `partial_pin = w` とします。実際の host registration API 呼び出しはありません。残りの領域は `lock_resident()` に渡されます（`sycl/src/core/expert_source.cpp:1958-2007`）。したがって、この変数を有効にしたときの確実なソース上の効果は、prefix の長さ・alias pointer・resident/pinned 判定が設定され、残部の resident lock 範囲がずれることです。SYCL device がこの通常の host pointer を直接読み出せるか、実際に DMA できるかは、このコードだけでは保証されません。

後続の `pinned()` は partial mode では prefix に完全に収まる expert だけを pinned と返します。PCIe miss 経路は `--pcie-frac` が正で、`pcie_layer()` が true の場合に miss の一部を選び、`pinned()` の expert を PCIe 処理へ渡します。direct mode では `device_alias()` の pointer を使います（`sycl/src/core/expert_source.cpp:2391-2412,2608-2639,2657-2660`）。

実行ログには prefix を `registered for the GPU` と記載する文言がありますが、上記の no-op 実装のため、ログだけでは登録の実行を裏付けません（`sycl/src/core/expert_source.cpp:1998-2001`）。

## 根拠

- 候補名の直接参照は `sycl/src/core/expert_source.cpp:1936-1944` のみ。Strata の別 backend での読み取りは確認できませんでした。
- resident complement の allocation/fallback: `sycl/src/core/expert_source.cpp:1855-1928`。
- prefix の選択、登録 API の no-op、残部 lock: `sycl/src/core/expert_source.cpp:1946-2007`。
- pinned 判定と PCIe dispatch: `sycl/src/core/expert_source.cpp:2391-2412,2608-2660`。
- 既存資料の主張: `docs/UNSLOTH_Q4.md:234`。同資料は `STRATA_PARTIAL_PIN=1` が最大 `STRATA_PARTIAL_PIN_GIB`（既定24 GiB）を GPU driver に登録すると説明しています。現 HEAD の SYCL 実装との差異があります。資料中の性能値・測定条件は本調査で再測定していません。
