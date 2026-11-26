# `STRATA_WDDM_BUDGET`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Windows 上の HIP ビルドで、Strata が `cudaMemGetInfo`（HIP 互換層では `hipMemGetInfo`）から得た空き VRAM を、DXGI のプロセス別ビデオメモリ予算に合わせて小さく補正する処理を無効にするスイッチです。設定値が `atoi` で 0 になると補正を止めます。未設定時は補正を有効にします（`engine/src/core/device.cu:115-127,191-217`）。

このラッパーを通るメモリ情報の空き量が変わり、例えば expert cache の空き容量判定に使われます。変数自体が GPU メモリを割り当てたり、モデルや生成内容を選んだりはしません（`engine/include/strata/hip_compat/cuda_runtime.h:88-99`; `engine/src/core/expert_cache.cpp:99-114,619-638`）。

## 値と判定

実装は `std::getenv` の結果を関数内 `static const bool` に一度保存し、設定されていて `std::atoi(v) == 0` のときだけ補正を無効にします。文字列全体の数値妥当性は検査しません。`atoi` が先頭の整数部分を読める文字列では、その整数が 0 かどうかで判定し、整数として読めない文字列も 0 として無効化側になります。空文字も 0 です。空白の後の `0` や `0anything` は無効化、`1`・`true`・`-1` は補正を有効にし、`0.5` は先頭整数が 0 のため無効化します。整数変換の範囲外の文字列について、コードに明示的な検査や fallback はありません（`engine/src/core/device.cu:194-198`）。

| ビルド・経路 | unset | 補正を無効にする値 | 補正を有効にする値 |
|---|---|---|---|
| Windows + HIP (`STRATA_USE_HIP`、`_WIN32`) | 有効 | `0`、空文字、`true`、`0anything`、`0.5` など `atoi` 結果が 0 の値 | `1`、`-1` など `atoi` 結果が非 0 の値 |
| CUDA、Linux HIP、通常の Intel Arc SYCL | 対象処理なし | 対象処理なし | 対象処理なし |

## 有効になる条件

- 対象の補正コードは `STRATA_USE_HIP` と `_WIN32` の両方が定義されたビルドに限られます。HIP 互換ヘッダーはその場合 `cudaMemGetInfo` を Strata の `strata::hip_compat::mem_get_info` に割り当てます。CUDA ビルドは NVIDIA の API を使い、Linux HIP は HIP の API に直接割り当てます（`engine/src/core/device.cu:115,191-198`; `engine/include/strata/hip_compat/cuda_runtime.h:88-99`）。
- 変数が未設定または `atoi` 結果が非 0 でも、HIP のメモリ情報取得が成功し、現在の HIP device を取得でき、DXGI adapter とローカルメモリ予算を取得できる必要があります。adapter が見つからない、DXGI 問い合わせが失敗する、予算が 0、または予算が総 VRAM 以上の場合、元の `hipMemGetInfo` の値を返します（`engine/src/core/device.cu:198-209`）。
- `STRATA_WDDM_BUDGET=0`（または同じく `atoi` 結果が 0）なら、メモリ取得が成功しても DXGI による差し引きと予算ログを行いません。CLI 引数や他の環境変数による上書きは、この読み取り箇所にはありません（`engine/src/core/device.cu:194-217`）。
- SYCL ソースにも同じ実装がありますが、こちらも `STRATA_USE_HIP && _WIN32` の条件内です。標準の Intel Arc SYCL 経路はこの条件に該当しません。環境変数一覧の `AMD, Intel Arc` という適用先表示は、このコード条件とは一致しません（`engine/sycl/src/core/device.dp.cpp:148-151,224-251`; `engine/CMakeLists.txt:23-31`）。

## 実行時の詳細

最初に有効な引数で `mem_get_info` が呼ばれたときに環境値を読み、`static` に保存します。その後プロセス内で環境値を変更しても判定は更新されません。NULL の出力ポインターで呼ばれた場合は直接 `hipMemGetInfo` を呼んで戻るため、その呼び出しだけでは環境値の `static` 判定を初期化しません（`engine/src/core/device.cu:191-198`）。

補正が有効な場合、Strata は `total_bytes - DXGI local.Budget` を差し引き量とし、HIP が返した `free_bytes` からそれを引きます。空き量が差し引き量以下なら 0 にします。総量や予算、HIP runtime の値自体はこの補正では書き換えません。各 GPU の DXGI adapter は初回検索結果を保持し、予算補正のログはプロセス内で一度だけ出します（`engine/src/core/device.cu:143-168,204-217`）。

この値は `device_info` の空き・総量表示にも入り（`engine/src/core/device.cu:282-285`; `engine/src/core/device_main.cpp:68-79`）、expert cache は空き量を確認して要求容量が足りなければ `ExpertCache::open` を失敗させ、「Lower --expert-cache.」を含む理由を返します。空きメモリ照会そのものに失敗した場合、`device_free_bytes` は空き量を 0 とし、エラー理由を一種類につき一度 stderr に出します（`engine/src/core/expert_cache.cpp:99-114,619-638`）。

## ログと測定値

DXGI による差し引きが実行される最初の成功時に、stderr に次の形式で一度出します。`STRATA_WDDM_BUDGET` により補正が無効な場合、または前述の条件を満たさず差し引きが行われない場合、このログは出ません（`engine/src/core/device.cu:204-217`）。

```text
strata: Windows budgets <予算 MiB> of this card's <総量 MiB> MiB for this process; free VRAM is counted within that (STRATA_WDDM_BUDGET=0: off)
```

`docs/AMD_HIP.md:148-150` の説明は、Windows HIP の空き量をプロセス予算に合わせて減らし、`STRATA_WDDM_BUDGET=0` で止めるという現行実装と一致します。ここでは測定値を追加しません。

## 根拠

- `engine/src/core/device.cu:115-127,191-217` — Windows HIP 実装、値の判定、DXGI 問い合わせ、差し引き、ログ。
- `engine/include/strata/hip_compat/cuda_runtime.h:88-99` — Windows HIP 時の `cudaMemGetInfo` の割り当て。
- `engine/src/core/expert_cache.cpp:99-114,619-638` — 空き量の利用、照会失敗時の扱い、cache 容量不足の失敗。
- `engine/src/core/device.cu:282-285`; `engine/src/core/device_main.cpp:68-79` — device 情報としての空き・総量の取得と表示。
- `engine/sycl/src/core/device.dp.cpp:148-151,224-251`; `engine/CMakeLists.txt:23-31` — SYCL 側コードの条件と Intel Arc SYCL のビルド入口。
- `docs/AMD_HIP.md:148-150` — 補正と無効化スイッチの説明。
