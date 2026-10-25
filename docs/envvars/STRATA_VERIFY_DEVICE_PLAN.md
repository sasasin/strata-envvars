# `STRATA_VERIFY_DEVICE_PLAN`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

推測検証（Verifier）の各グループについて、ルーティング結果から VRAM 常駐 expert の実行 plan を GPU 上で作ります。そのグループの選択 expert がすべて常駐している場合は、CPU が plan を作って doorbell で渡す処理や CPU 側の結果待ちを省きます。常駐していない expert が含まれるグループでは、skip が立たず、従来の host/CPU との受け渡しに進みます。推測検証の起動時に読まれ、通常の decode 経路全体を切り替える設定ではありません。

## 値と判定

`Verifier::init()` は `std::getenv()` の値を `std::atoi()` で整数変換し、結果が 0 でなければ有効とします。値全体の検証や範囲制限はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、数値に変換できない文字列、`0`、`0tail` | 無効（`atoi` の結果が 0） |
| `1`、`-1`、`2`、`1tail`、先頭の空白の後に数値がある文字列 | 有効（変換結果が非 0） |

数値の後ろの文字は無視されます。`atoi` による変換のため、文字列全体が整数かどうかは検査されません。

## 有効になる条件

設定値が非 0 でも、Verifier の初期化時に `all_resident_` が true なら `device_plan_` は有効になりません。全 expert が VRAM 常駐の場合は、別の all-resident graph 経路が優先されます。また `set_always_publish(true)` が設定されている場合も無効です。これは pipeline windows で host の residency 表が device 側より先に進む場合に、全 layer を host に publish させるためです。該当条件と判定は `src/core/verify.cpp:794-822` にあります。

all-resident 判定には `hits.h_res`、`hits.d_res`、`hits.cache_base` が必要です。device plan は GPU 上の `hits.d_res` と `hits.cache_base` を `resident_plan()` に渡します。`skip_` の確保・初期化、または利用可能な slot offset の device copy に失敗した場合は、初期化中に `device_plan_` も false に戻ります（`src/core/verify.cpp:801-821,832-841`）。

## 実行時の詳細

各層・各 group の router が選んだ expert ID を `resident_plan()` に渡し、device 側の residency 表を使って host pool と同じ形式の plan を構築します。全選択 expert が常駐していれば、その group の `skip_` に ring 値が記録されます。後続処理は skip を見て host の plan/結果待ちを抜け、host からの miss rows の代わりにゼロ rows を置きます。選択 expert に miss がある場合は通常の待ちと host rows のコピーを続けます（`src/core/verify.cpp:1512-1537,1624-1674`、`include/strata/kernels/verify_kernels.hpp:73-89`）。

環境変数は `Verifier::init()` のたびに読み直されます。一方、`expert_source.cpp` の mapped rows の zero 処理を選ぶ補助判定は関数内 `static const` で、プロセス内の初回評価結果を保持します。device plan 時は GPU 自身が作った plan の rows を GPU がゼロ化しないため、host 側が GPU rows を含めてゼロ処理する経路を選びます（`src/core/expert_source.cpp:3881-3885`）。

`STRATA_FS_SLOTS` が正数で foresight swap が要求されているとき、値が非 0 なら foresight swap は作られず、stderr に `strata serve: foresight swap: off beside STRATA_VERIFY_DEVICE_PLAN (the device would plan resident layers without the host)` を出します。`STRATA_FS_SLOTS` が 0 以下なら、この判定・ログには到達しません（`src/core/expert_source.cpp:5150-5159`）。

適応コピー overlap との併用もできません。overlap を有効にしようとした場合、`set_adapt_gate()` が false を返し、生成側は `the device-planned layers (STRATA_VERIFY_DEVICE_PLAN) are on` を理由に overlap を止めます（`include/strata/core/verify.hpp:254-259`、`src/program/generate.cpp:8753-8759`）。

CUDA/HIP の `src/` 実装と SYCL の `sycl/src/` 実装で、環境変数の `atoi` 判定、`all_resident_` / `always_publish_` による抑止、および device plan の構成は同じです（`sycl/src/core/verify.cpp:715-721`、`sycl/src/core/expert_source.cpp:2706-2710`）。

## 根拠

- 値の読み取りと有効条件: `src/core/verify.cpp:816-822`、SYCL: `sycl/src/core/verify.cpp:715-721`。
- 常駐判定と初期化 fallback: `src/core/verify.cpp:794-814,832-841`。
- device plan の生成と実行時の skip/fallback: `src/core/verify.cpp:1512-1537,1624-1674`、kernel API の契約: `include/strata/kernels/verify_kernels.hpp:73-89`。
- foresight swap との排他: `src/core/expert_source.cpp:5150-5159`。
- overlap との排他: `include/strata/core/verify.hpp:254-259`、`src/program/generate.cpp:8753-8759`。
- SYCL の利用例と説明: `docs/INTEL.md:232-249`。この資料は設定例を示しますが、性能測定値は本調査では記載しません。
