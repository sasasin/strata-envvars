# `STRATA_VERIFY_COHERENT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

HIP ビルドの verifier が使う mapped host memory を、通常の pinned allocation ではなく `hipHostMallocCoherent` を含む allocation で確保する切り替えです。CPU/GPU 間の handshake word や verifier の staging / plan buffer など、`mapped()` 経由で確保する領域が対象です。生成内容や token 選択を変える分岐ではありません。`STRATA_USE_HIP` が定義された `engine/src/core/verify.cpp` だけがこの allocation 分岐を持ちます（`engine/src/core/verify.cpp:336-343,569-582`）。

## 値と判定

`env_on()` は `getenv()` の戻り値が null でなく、先頭バイトが NUL でも `'0'` でもない場合に true を返します。文字列全体の parse や数値変換はしません。大文字小文字・空白・後続文字も検査しません（`engine/src/core/verify.cpp:336-343`）。

| ビルド・経路 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_USE_HIP` 定義あり（HIP backend） | 無効 | `1`、`true`、`false`、` 0`、先頭文字が `0` 以外の値 | 空文字、`0`、`00`、`0anything` |
| CUDA、gfx906 HIP compatibility、Metal、および通常の SYCL target | この変数を読む allocation 分岐なし | 該当なし | 該当なし |

`0anything` は先頭が `'0'` なので無効です。逆に `false` は文字列としては false でも先頭が `'f'` のため有効です。通常の HIP build は `strata_hip_runtime` が `STRATA_USE_HIP=1` を定義し、gfx906 compatibility build は別の `STRATA_HIP_GFX906` 経路です（`engine/cmake/hip_backend.cmake:105-119`、`engine/CMakeLists.txt:91-103,233-241`）。

SYCL verifier にも同名の `env_on()` 呼び出しがありますが、`g_coherent` の宣言と参照は `STRATA_USE_HIP` 条件下にあり、SYCL の `mapped()` は `window_host_uncached()` に応じて別の host allocation を行います（`engine/sycl/src/core/verify.cpp:151-154,187-190,320-338,806-814`）。Intel target はこの macro を定義せず、同梱の B65 調査記録もその点を確認しています（`engine/sycl/CMakeLists.txt:290-301`、`docs/bench-results/2026-10-05-community-arc-b65/README.md:217-221`）。このため通常の SYCL target では環境変数を読みません。

## 有効になる条件

- `STRATA_USE_HIP` を定義した通常の HIP backend であること。CUDA、gfx906 compatibility、Metal ではこの変数による allocation 分岐はありません（`engine/src/core/verify.cpp:340-343,569-582`、`engine/CMakeLists.txt:91-103,233-241`）。
- verifier の `init()` が mapped staging を確保する段階まで進むこと。そこでは window size、expert cache、layer compatibility、artifact geometry などの前提を先に検査します（`engine/src/core/verify.cpp:956-1030`）。
- CLI 引数や別の環境変数による上書きはありません。`STRATA_VERIFY_TRACE` は診断表示の条件ですが、allocation 方法の条件ではありません（`engine/src/core/verify.cpp:341,344,1245-1260`）。

## 実行時の詳細

`g_coherent` は namespace scope の `const bool` として初期化されるため、HIP verifier の翻訳単位の初期化時に一度読み取られます。プロセス起動後に環境を変更しても、この値には反映されません（`engine/src/core/verify.cpp:336-343`）。

HIP で有効な場合、`mapped()` は `hipHostMallocMapped | hipHostMallocCoherent` に、peer portability が必要な場合だけ `hipHostMallocPortable` を加えて確保し、領域をゼロ初期化した後 `cudaHostGetDevicePointer()` で device pointer を得ます。無効の場合は `host_alloc_guarded()` と `cudaHostAllocMapped` を使う経路です。coherent allocation または device pointer 取得が失敗すると `mapped()` は false を返し、通常 allocation への再試行はありません（`engine/src/core/verify.cpp:569-582`）。

この関数は verifier の mapped staging / handshake word 群、plan、条件付きの balance stamp、hand-off word、trace buffer などの確保に呼ばれます（`engine/src/core/verify.cpp:1041-1060,1142-1163,1238-1251`）。初期 staging が失敗した場合 `Verifier::init()` は `verify: mapped staging allocation failed ...` をエラー文字列にして false を返し、plan や hand-off の確保失敗にも個別のエラー文字列があります（同:1060,1161-1163,1238-1244）。環境変数専用の警告はありません。

## ログと測定値

`STRATA_VERIFY_TRACE` が有効で trace buffer の確保処理に進むと、HIP では stderr に `strata verify trace (#649): on; coherent words explicit, doorbell ...`（無効なら `coherent words default`）を出します。通常の mapped allocation 成功だけではこの値を示すログは出ません（`engine/src/core/verify.cpp:344,1245-1260`）。

`docs/DETAILS.md` に本変数の説明・測定値は見つかりませんでした。同梱の B65 調査記録は SYCL target で `STRATA_USE_HIP` が未定義であることと、このスイッチの速度効果を主張しないことを記しています（`docs/bench-results/2026-10-05-community-arc-b65/README.md:217-221`）。

## 根拠

- `engine/src/core/verify.cpp:336-343` — env 判定 helper、HIP macro guard、namespace scope cache。
- `engine/src/core/verify.cpp:569-582` — HIP coherent allocation と既定 allocation。
- `engine/src/core/verify.cpp:956-1060,1142-1163,1238-1260` — verifier 初期化、mapped buffer の呼び出し、失敗文字列、trace log。
- `engine/cmake/hip_backend.cmake:105-119`、`engine/CMakeLists.txt:91-103,233-241` — 通常 HIP と gfx906 compatibility の build macro。
- `engine/sycl/src/core/verify.cpp:151-154,187-190,320-338,806-814`、`engine/sycl/CMakeLists.txt:290-301` — SYCL 側の guarded read / mapped allocation と target 構成。
- `docs/bench-results/2026-10-05-community-arc-b65/README.md:217-221` — B65 調査記録。速度効果の主張なし。
