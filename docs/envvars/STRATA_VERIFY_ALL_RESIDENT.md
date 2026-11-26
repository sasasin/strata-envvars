# `STRATA_VERIFY_ALL_RESIDENT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

CUDA/HIP と SYCL の verifier が、初期化時にその stage の全 expert が VRAM 常駐している場合に all-resident（zero-doorbell）graph を選ぶかどうかを制御する。未設定なら選択判定を行い、値を `atoi` で変換して 0 以外なら判定を行う。`0` と変換される値を設定するとこの経路を明示的に無効化し、通常の doorbell graph を使う。expert の VRAM 配置やモデルの重み自体は変更しない。実装は CUDA/HIP の `Verifier::init` と SYCL の `Verifier::init` にある（`engine/src/core/verify.cpp:956-958,1377-1403`、`engine/sycl/src/core/verify.cpp:624-626,897-918`）。

## 値と判定

両 backend とも `std::getenv` の結果を `std::atoi` に渡し、戻り値が 0 以外なら全 expert の常駐検査を行う。文字列全体の厳密な parse やエラー検出はしない。`atoi` は先頭の空白と符号の後の10進数部分を読み、数字がなければ 0 になるため、後続文字は無視される。

| ビルド | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP verifier、SYCL verifier | 常駐検査を行う（既定） | `1`、`-1`、`+2`、`1x`、` 1` など、先頭の数値部分が 0 以外 | 空文字、`0`、`0anything`、`true`、`false`、`x1`、`  ` など、数値部分がないか 0 |

大文字小文字は判定しない。`true` / `false` は真偽値として扱われず、どちらも数値部分がないため 0 になる。小数点以降や数値の後ろの文字は検証されず、たとえば `1.5` は先頭の整数部分 1 として有効。`atoi` の範囲外値について Strata は検出・処理していない。判定箇所は `engine/src/core/verify.cpp:1386-1402` と `engine/sycl/src/core/verify.cpp:904-917`。

## 有効になる条件

- verifier が CUDA/HIP または SYCL backend の `Verifier::init` を実行すること。CUDA/HIP ソース内の Metal 分岐は初期化の早期 return（`engine/src/core/verify.cpp:978-993`）より後に判定箇所があるため、その分岐ではこの読み取りに到達しない。SYCL 版には別の `Verifier::init` がある（`engine/sycl/src/core/verify.cpp:624-626`）。
- `hits.h_res`、`hits.d_res`、`hits.cache_base` がすべて非 null であること。この条件を満たさない場合は変数を読み取らず、`all_resident_` は false のまま。CUDA/HIP では「no expert table on this device」の理由を dispatch note に記録する（`engine/src/core/verify.cpp:1380-1387`）。SYCL も同じポインタ条件で判定を囲む（`engine/sycl/src/core/verify.cpp:900-905`）。
- 変換値が 0 以外（または未設定）で、stage の `[lb_, le_)` に属する全 layer・全 expert の host residency table が 0 以上であること。どれかが負なら all-resident graph を選ばない（`engine/src/core/verify.cpp:1388-1400`、`engine/sycl/src/core/verify.cpp:906-917`）。
- CLI 引数や設定ファイルによる値の上書きは、この読み取り箇所にはない。`STRATA_VERIFY_DEVICE_PLAN`（CUDA/HIP では `STRATA_VERIFY_DEVICE_HITS` も参照）は別の device planning 経路を制御するが、`all_resident_` が true の場合はその経路を抑止する（`engine/src/core/verify.cpp:1414-1428`、`engine/sycl/src/core/verify.cpp:919-925`）。

## 実行時の詳細

変数は `Verifier::init` の実行中、expert table のポインタ条件を満たしたときに読み取られる。関数内 static cache ではなく、その初期化ごとに `getenv` する。読み取り結果は `all_resident_` メンバーに反映されるため、初期化後にプロセス環境を書き換えても既存 verifier の選択は変わらない。stage ごとに verifier が初期化されれば、それぞれの table と環境値で判定する（`engine/src/core/verify.cpp:956-958,1380-1398`、`engine/sycl/src/core/verify.cpp:624-626,900-916`）。

選択された graph は expert を device 上で計画し、`parts_` へ直接書き込むゼロ doorbell 経路で、CPU expert への doorbell や PCIe staging を必要としない（`engine/src/core/verify.cpp:1377-1379`、同 `:2829`）。初期化後も実行前に residency table を確認し、prompt loan・VRAM shrink・swap 等で expert が常駐でなくなれば doorbell graph へ切り替え、すべて常駐に戻れば再び zero-doorbell graph に戻す。この動的切り替えは初期化時に all-resident が選ばれた場合だけ行われる（`engine/src/core/verify.cpp:3235-3251,3836-3844`、`engine/sycl/src/core/verify.cpp:2032-2048,2391-2397`）。

## ログと測定値

- CUDA/HIP は選択・不選択理由を `strata::dispatch::note` に記録する。文言は `init: all-resident graph selected (every expert of this stage is in VRAM)`、`init: all-resident graph declined: some expert is not resident (doorbell graph with CPU / PCIe experts)`、`init: all-resident graph declined: STRATA_VERIFY_ALL_RESIDENT=0`、または `init: all-resident graph declined: no expert table on this device (no cache, or no residency map)`。これは通常の stderr 直書きではなく dispatch stats の記録で、stats が有効な場合に `--stats` の出力または `STRATA_DISPATCH_REPORT` の JSON から観測できる。dispatch stats は既定で有効であり、`STRATA_DISPATCH_STATS=0...` で無効になる（`engine/src/core/verify.cpp:1383-1402`、`engine/include/strata/core/dispatch_stats.hpp:9-11,59-69,107-119`）。
- CUDA/HIP と SYCL は初期化時に stderr へ `strata verify: window up to ... tokens, ... MiB of device buffers` を出し、all-resident が選択済みなら末尾に ` (100% VRAM resident: zero-doorbell graph)` を付ける（`engine/src/core/verify.cpp:1450-1453`、`engine/sycl/src/core/verify.cpp:995-998`）。CUDA/HIP は residency が変わって graph を切り替える際にも stderr へ `strata verify: layers [...] have experts out of VRAM (a prompt loan, a shrink or a swap): the doorbell graph runs the windows` または `strata verify: layers [...] are 100% VRAM resident again: the zero-doorbell graph` を出す（`engine/src/core/verify.cpp:3245-3251`）。
- CUDA/HIP と SYCL の all-resident graph が実行中に非常駐 expert を検出した場合、window は `verify: the all-resident plan met an expert that is not in VRAM (the residency table changed during the window)` で失敗し得る（`engine/src/core/verify.cpp:4140-4144,4168-4171`、`engine/sycl/src/core/verify.cpp:2901-2904`）。この環境変数自体に専用の終了処理はない。
- Strata の資料にこの変数の動作を裏付ける条件付き測定値は見つからなかったため、性能値は記載しない。

## 根拠

- `engine/src/core/verify.cpp:956-958,978-993,1377-1403,1414-1428,1439-1453,2829,3235-3251,3836-3844,4140-4144,4168-4171`
- `engine/sycl/src/core/verify.cpp:624-626,897-925,995-998,2032-2048,2391-2397,2901-2904`
- `engine/include/strata/core/dispatch_stats.hpp:9-11,59-69,107-119`
