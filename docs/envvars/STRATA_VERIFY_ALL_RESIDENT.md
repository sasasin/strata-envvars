# `STRATA_VERIFY_ALL_RESIDENT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Verifier の GPU window で、検証対象 layer の全 expert が VRAM cache に常駐している場合に使う「zero-doorbell graph」を許可するか制御します。有効な場合、GPU が常駐表から実行計画を作り、CPU から layer ごとの doorbell と非常駐 expert の処理を受け取らずに window を実行します。

対象の読み取りは CUDA/HIP の `src/core/verify.cpp` と SYCL 実装の `sycl/src/core/verify.cpp` にあります。Metal は `Verifier::init()` が Metal window の初期化へ戻るため、この判定箇所に到達しません。通常の native decode ではなく、Verifier の window 経路に対する設定です。

## 値と判定

各 `Verifier::init()` で `getenv()` を読み、設定値は `std::atoi()` で整数に変換して判定します。文字列全体の厳密な数値検査はありません。

| 値 | all-resident 判定 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 無効（`atoi("")` は 0） |
| 数値として 0 に変換される値（例 `0`, `00`, `abc`） | 無効 |
| 数値として 0 以外に変換される値（例 `1`, `2`, `-1`, `1tail`） | 有効 |

`atoi` は先頭の空白と符号を受け付け、数字列の後ろは判定に使いません。数値に変換できない先頭なら 0 です。clamp や独自 fallback はありません。設定値は verifier ごとの初期化時に評価され、その verifier の間は環境を書き換えても再評価されません。

## 有効になる条件

値判定が有効でも、次の条件が必要です。

- Verifier の初期化が成功し、`hits.h_res`、`hits.d_res`、`hits.cache_base` がすべて非 null である。
- verifier の layer 範囲 `[lb_, le_)` の全 layer・全 expert について、host residency table `hits.h_res` の値が 0 以上である。
- all-resident 用の GPU 資源確保が成功する。初期化時の確保に失敗すると `all_resident_` と device-plan の両方が無効化される。

`STRATA_VERIFY_ALL_RESIDENT=0` などでこの経路を止めても、`STRATA_VERIFY_DEVICE_PLAN` が非 0 で、`always_publish_` が無効なら、layer ごとの device-plan 経路が別途選ばれる場合があります。all-resident が選ばれた場合は `device_plan_` は無効です。

## 実行時の詳細

初期化時に layer 範囲内を走査し、いずれかの expert が residency table 上で負値（非 resident / swap 中を示す値）なら all-resident は選びません。選択されると stderr に `strata verify: window up to ... (100% VRAM resident: zero-doorbell graph)` と出ます。

CUDA/HIP と SYCL の `run()` および batch 経路は各 window の前に `refresh_ar()` を呼び、同じ host residency table を再確認します。実行中に prompt loan、VRAM 縮小、swap などで対象 expert が resident でなくなれば通常の doorbell graph に切り替え、stderr に `strata verify: layers [...] have experts out of VRAM (a prompt loan, a shrink or a swap): the doorbell graph runs the windows` と出します。再び全 expert が resident になると zero-doorbell graph に戻り、その旨を stderr に出します。これらの更新は環境変数を読み直すものではなく、初期化時に all-resident が許可されていた場合だけ行われます。

zero-doorbell graph が実行中に、residency table が示す状態と実際の VRAM 配置が食い違った場合は、window を失敗させ `verify: the all-resident plan met an expert that is not in VRAM (the residency table changed during the window)` を返す経路があります。

## 根拠

- `src/core/verify.cpp:557-581,797-845`: Verifier 初期化、値の parse、全 expert の residency 確認、GPU 資源確保、初期化ログ。Metal は環境判定より前に専用 window 初期化へ戻る。
- `sycl/src/core/verify.cpp:696-771`: SYCL の同じ初期化判定とログ。
- `include/strata/core/verify.hpp:400-407`: all-resident 状態と per-window `ar_on()` の定義。
- `src/core/verify.cpp:1862-1878,2235-2251,2952`: CUDA/HIP の residency 再確認と graph 切替。SYCL にも同等の `refresh_ar()` があり、`sycl/src/core/verify.cpp:1660-1676,1988-1999,3010` で確認できる。
- `src/core/verify.cpp:3031-3054,3212-3229,2423-2426`: batch 時に host の layer service を省く処理と residency 不整合時のエラー。
- `docs/A770_SPEED_SPEC.md:279-300`: all-resident graph の説明と SYCL の multi-GPU layer-split での制約。環境変数の parse 規則や性能測定の根拠にはしていない。
