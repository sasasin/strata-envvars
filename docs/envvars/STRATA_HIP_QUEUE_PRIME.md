# `STRATA_HIP_QUEUE_PRIME`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

HIP の通常エンジン起動時に、指定 GPU 上で非ブロッキング stream を順に作成して小さな memset を同期実行し、キューを先に開く処理を制御する。未設定時は非 Windows の gfx1200 / gfx1201 だけで既定の 2 stream を開く。明示値を指定すると、その既定対象外の GPU でも指定文字数分の stream 作成を試す。Strata が行うのはこの起動時の stream 作成・同期であり、GPU ドライバー内部のキュー配置や後続処理への性能効果はこの変数の実装からは保証できない。実装は `engine/src/program/generate.cpp` の `prime_hw_queues()`（3474-3536 行）。

## 値と判定

値は `std::getenv` で取得し、文字列全体がちょうど `"0"` のときだけ即時 return する。空文字は設定値として扱われず、未設定と同じ既定判定へ進む。それ以外の非空文字列は検証・数値変換せず、各文字を 1 個ずつ処理する。小文字 `h` は優先度範囲の取得に成功した場合だけ最高優先度 stream を試し、それ以外の文字は既定優先度の非ブロッキング stream を試す。したがって `"nn"` は 2 個、`"nnh"` は 3 個、`"1"` や `"false"` もそれぞれ 1 個・5 個を試す。大文字 `H`、空白、`true` / `false` などに特別な意味はない。`"0anything"` も完全一致ではないため無効化値ではなく、10 文字分を試す指定になる（3487-3495、3521-3529 行）。

| ビルド・条件 | unset / 空文字 | 設定時に priming を止める値 | 設定時に stream 指定として使う値 |
|---|---|---|---|
| `STRATA_USE_HIP` かつ `STRATA_HIP_GFX906` なし、非 Windows | `STRATA_PRIMARY_DEVICE` の GPU が gfx1200 / gfx1201 で、`GPU_MAX_HW_QUEUES` が 1 / 2 でなければ `nn` | 完全一致の `0`。または既定対象 GPU で `GPU_MAX_HW_QUEUES` が `atoi` で 1 / 2 になる場合 | `0` 以外の非空文字列。文字ごとに stream を試す。明示値は GPU 世代と queue cap の既定判定を迂回する |
| 同じ HIP build、Windows | priming なし | 完全一致の `0` | `0` 以外の非空文字列。GPU 世代条件なしで文字ごとに試す |
| CUDA / Metal / SYCL、または `STRATA_HIP_GFX906` build | 関数と呼び出しが compile guard 外のため読み取らない | 該当なし | 該当なし |

コードの既定分岐は `_WIN32` 以外を対象にする。ソースコメントとリリース資料は Linux と記すが、実装に Linux 専用 guard はなく、ここではコード上の条件を「非 Windows」として記載した（`engine/src/program/generate.cpp:3495-3503`）。

`GPU_MAX_HW_QUEUES` の判定にも `atoi` を使い、変換結果が 1 以上 2 以下なら既定 priming を止める。従って `1`、`2`、` 2`、`2x` は該当し、`0`、`3`、`-1`、数値で始まらない文字列や空文字は該当しない。これは `STRATA_HIP_QUEUE_PRIME` が unset / 空文字のときだけ判定され、明示的な非空指定は cap を迂回する（3494-3515 行）。

## 有効になる条件

- `generate.cpp` が `STRATA_USE_HIP` でコンパイルされ、`STRATA_HIP_GFX906` が定義されていないこと。HIP backend target は `STRATA_USE_HIP=1` を定義し、gfx906 compat build は別 macro を使う（`engine/cmake/hip_backend.cmake:105-109`、`engine/CMakeLists.txt:97-100`、`engine/cmake/backends/hip.cmake:16-22`）。
- `generate` の通常経路で `prime_hw_queues()` 呼び出しまで到達すること。`STRATA_HAVE_QWEN35` build で `--model` / `--native` のモデルが Qwen3.6-35B-A3B と判定されると、専用経路へ return するためこの処理を通らない（`engine/src/program/generate.cpp:3804-3819`）。
- 対象 GPU は `STRATA_PRIMARY_DEVICE` を `atoi` した値が正ならその index、未設定・空・変換結果が 0 以下なら index 0。GPU 数取得失敗、index が GPU 数以上、明示 index の `cudaSetDevice` 失敗では priming せず return する（`engine/src/program/generate.cpp:3490-3493,3517`）。
- 値が未設定 / 空文字の場合、Windows は既定で常に無効。非 Windows は選択 GPU の `gcnArchName` が gfx1200 または gfx1201 の場合のみ続行し、GPU 情報の取得失敗またはそれ以外の世代では無効。判定 helper は `engine/include/strata/kernels/gfx_arch.hpp:15-20,41-42`。
- 未設定 / 空文字の既定経路では `GPU_MAX_HW_QUEUES` が `atoi` で 1 または 2 になると無効で、理由を stderr に出す。明示的な非空指定はこの制限を迂回する（`engine/src/program/generate.cpp:3504-3515`）。
- `--gpu` はこの関数より前に可視 GPU 環境を設定するため、選択される device count / index に影響し得る。ただし `STRATA_HIP_QUEUE_PRIME` 自体には CLI 引数による上書きはない（`engine/src/program/generate.cpp:3781-3802,3490-3493`）。

## 実行時の詳細

通常経路では、`--gpu` の環境反映と Qwen35 の早期振り分けの後、`Options` の CLI 引数解析より前に呼ばれる。HIP dynamic queue の既定設定も先に反映され、その後 `prime_hw_queues()` を一度呼ぶ（`engine/src/program/generate.cpp:3821-3838`）。関数内で毎回 `getenv` するだけで static cache はない。1 回の `generate` 実行では呼び出し時点の値で処理が決まり、その後の環境変更を再読しない。

priming を続ける場合、選択 device に 256 byte を確保し、優先度範囲を取得して指定文字列の各文字について stream 作成を試す。`h` かつ優先度範囲を取得できた場合は HIP の最高優先度付き作成、それ以外は既定優先度の非ブロッキング作成を使う。作成できた stream ごとに 256 byte の非同期 memset と同期を行い、最後に stream と buffer を解放する。優先度取得失敗時の `h` は既定優先度 stream に fallback する。個別 stream 作成失敗はその文字だけ飛ばして続行し、同期・memset の戻り値も分岐に使わない（`engine/src/program/generate.cpp:3517-3535`）。

## ログと測定値

既定経路が `GPU_MAX_HW_QUEUES` により止まる場合、stderr に `strata generate: GPU queues not primed: GPU_MAX_HW_QUEUES=%s leaves none for the draft stream (STRATA_HIP_QUEUE_PRIME=nn primes them anyway)` を出す。処理を最後まで実行した場合は、作成成功数にかかわらず stderr に `strata generate: opened %zu GPU queues in a fixed order (STRATA_HIP_QUEUE_PRIME=0 turns it off)` を出す。完全一致 `0`、Windows の既定無効、GPU 情報や確保などの失敗による早期 return は、この関数から理由ログを出さない（`engine/src/program/generate.cpp:3489,3496-3503,3509-3512,3517-3535`）。

コードコメントは R9700 の `nn` で 32 回の fresh start 中 unprimed 10 回に対して遅い起動 0 回だったこと、および 5 stream の decode が 2〜3.6% 遅くなったことを記載する（`engine/src/program/generate.cpp:3480-3484`）。リリースノートは 2 台の Radeon AI PRO R9700、Linux / ROCm 7.10、Q2_0 + MTP での測定として、修正前は 32 回中 10 回が遅い起動、修正後は 0 回と記載する（`docs/release-notes-0.2.1.md:46`）。一方、queue cap 抑止変更は gfx1201 向けに compile されたが gfx12 実機では測定していない（`docs/release-notes-0.2.2.md:23`）。ソースコメントだけでは 5 stream 測定の詳細条件は分からない。これらはソースコメント・資料に記載された結果であり、この調査で再測定した値ではない。

## 根拠

- `engine/src/program/generate.cpp:3474-3536` — build guard、読み取り、文字列判定、GPU / cap 条件、stream 作成とログ。
- `engine/src/program/generate.cpp:3781-3819,3821-3838` — `--gpu` の適用、Qwen35 の早期分岐、呼び出し位置と CLI 解析順。
- `engine/include/strata/kernels/gfx_arch.hpp:15-20,41-42` — gfx12 世代の文字列判定。
- `engine/cmake/hip_backend.cmake:105-109`、`engine/CMakeLists.txt:97-100`、`engine/cmake/backends/hip.cmake:16-22` — HIP / gfx906 build macro。
- `docs/release-notes-0.2.2.md:23` — queue cap 対応の実機未測定という記載。
- `docs/release-notes-0.2.1.md:46` — R9700 / Linux / ROCm 7.10 / Q2_0 + MTP での初期起動測定の記載。
