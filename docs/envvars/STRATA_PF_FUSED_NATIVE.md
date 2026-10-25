# `STRATA_PF_FUSED_NATIVE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。調査開始時の作業ツリーは `main` で変更なし。

## 役割

`STRATA_PF_FUSED=1` などで選択される native IQ pack の prompt expert fused int8 kernel を、明示的に無効化する A/B 用スイッチです。コードではこの変数を「無効化フラグ」として読み、値の先頭文字が `0` の場合だけ native kernel を不許可にします。`1` を指定して機能を有効にする変数ではありません。

対象は native pack の gate/up と down の型が fused native 実装の対応範囲にあり、デバイス初期化検査も通る場合です。Q2_0 pack の別実装や、native fused をビルドしていない経路をこの変数が制御するわけではありません。

## 値と判定

CUDA/HIP 実装と SYCL 実装は、`native_supported()` の初回呼び出し時に `std::getenv()` で値を読み、関数内の `static const bool` に保存します。文字列全体の parse はせず、先頭文字だけを確認します。

| 値 | native kernel の無効化 |
|---|---|
| 未設定 | しない |
| 空文字 | しない（値は存在するが先頭文字が `\0`） |
| `0`、`0anything` | する |
| `1`、`true`、`false`、その他 `0` 以外で始まる値 | しない |

空白除去、数値変換、大文字小文字変換はありません。最初の `native_supported()` 評価後に環境を変更しても、そのプロセスでは判定は変わりません。

## 有効になる条件

- CUDA/HIP では、`STRATA_PF_FUSED_NATIVE` が無効化を要求しないことに加えて、`STRATA_PF_FUSED` による native 対応の選択、形式対応、デバイス検査が必要です。したがってこの変数単独では kernel を有効化しません。
- CUDA/HIP の native 実装は gate/up と down の型を別々に対応判定します。CUDA の通常経路は IQ2_XXS、IQ2_XS、IQ2_S、IQ3_XXS、IQ3_S、IQ4_XS の gate/up と Q2_0 / IQ4_NL の down が対象です。HIP では追加形式がありますが、Q4_K / Q5_K gate/up と Q5_1 / Q8_0 down は `STRATA_PF_FUSED_KQ=1` の場合に限り対応します。
- HIP 側では gfx11 / gfx12 の対応 kernel がロードされ、デバイス情報・occupancy 検査が通る必要があります。gfx906 はこの native 実装を利用不可として返します。
- CUDA 側では compute capability 8.0 以上で、この build の native kernel の属性設定と occupancy 検査がすべて通る必要があります。
- CUDA/HIP の native 実装では、`STRATA_PF_FUSED` が未設定の場合も gfx12 の IQ3_S / IQ3_XXS gate/up に限り既定で候補になります。`STRATA_PF_FUSED=0` は候補から外します。gfx12 の他の対応形式を含め、`STRATA_PF_FUSED=1` は `requested()` を満たす明示 opt-in です。
- SYCL 実装は `STRATA_PF_FUSED_NATIVE` が `0` でないことに加え、`requested()`（`STRATA_PF_FUSED` の先頭文字が `1`）と対応形式・デバイス検査を要求します。CUDA/HIP 実装にある gfx12 の未設定時既定分岐は SYCL の `native_supported()` にはありません。
- native fused 実装を含まない stub の `native_supported()` は常に `false` を返します。

`prefill.cpp` は `native_supported()` の結果で native pack の fused expert 経路を選びます。false の場合は該当経路で MMQ または既存の別 expert 経路が使われます。native pack 全体の MoE buffer を fused 用に縮められるかも、全 layer が対応するかどうかで判定されます。

## 実行時の詳細

CUDA/HIP の `src/prefill/moe_fused_iq.cu` と SYCL の `sycl/src/prefill/moe_fused_iq.dp.cpp` が、`native_supported()` 内で本変数を読みます。CUDA/HIP 実装では環境変数の抑止判定後に、`STRATA_PF_FUSED` の選択状態、対応形式、backend ごとの既定条件、`dev_info()` を順に確認します。SYCL 実装では抑止判定の後に `requested()`、形式対応、`dev_info().ok` を確認します。

この変数専用のログ出力はありません。上位の prompt 実装が native fused を選んだ場合、初回 prompt で `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` を出力するコードがありますが、これは fused 経路のログであり、本変数の値を報告するものではありません。

## 根拠

- `src/prefill/moe_fused_iq.cu:1118-1139` — CUDA/HIP の無効化判定、`STRATA_PF_FUSED` との組み合わせ、gfx12 既定分岐、対応形式とデバイス条件。
- `sycl/src/prefill/moe_fused_iq.dp.cpp:1361-1366` — SYCL の無効化判定と opt-in / 対応形式 / デバイス条件。
- `src/prefill/moe_fused.cu:667-673`, `sycl/src/prefill/moe_fused.dp.cpp:956-962` — `requested()` が `STRATA_PF_FUSED` の先頭文字 `1` と backend の利用可能性を確認。
- `src/prefill/moe_fused_iq.cu:1076-1089`, `sycl/src/prefill/moe_fused_iq.dp.cpp:1223-1236` — native 実装の gate/up・down 対応形式。
- `src/prefill/prefill.cpp:225-240, 2985-2988, 3016-3018` — native pack の対応判定、fused 経路選択、および fused kernel のログ。
- `src/prefill/prefill.cpp:79-92`, `sycl/src/prefill/moe_fused_stub.cpp:22-30` — fused native を提供しない stub が false を返す。
- `docs/DETAILS.md:27-28`, `docs/AMD_HIP.md:357-369` — native fused の opt-in と gfx12 /測定の説明、および `STRATA_PF_FUSED_NATIVE=0` が MMQ を保つ A/B 設定であること。測定値は各文書に記された環境・条件の報告であり、本調査で再測定していません。
