# `STRATA_HIP_CPU_SPLIT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

HIP backend の hybrid CPU expert pool が、適格な RAM expert の計算を行単位に複数 worker へ分割する機能を有効にする。無効にしても CPU expert の計算や GPU 側処理は止まらず、CPU pool は通常の expert 単位の job 配分を使う。読み取り箇所は `HybridCpuExpertPool::split_enabled_` の初期化子である [`engine/src/inkling2/hip/ink_hip_hybrid.hpp:330-332`](../../../../Niko1221/Strata/engine/src/inkling2/hip/ink_hip_hybrid.hpp)。

この header は `ink_hip_backend.hip.cpp` から取り込まれ、HIP backend オブジェクトのソースとしてコンパイルされる。したがって対象はこの HIP backend を使う実行経路であり、CUDA backend などの同名でない CPU pool には適用されない（[`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:18-21`](../../../../Niko1221/Strata/engine/src/inkling2/hip/ink_hip_backend.hip.cpp)、[`engine/src/inkling2/hip/CMakeLists.txt:30-32,74-97`](../../../../Niko1221/Strata/engine/src/inkling2/hip/CMakeLists.txt)）。

## 値と判定

C++ の `std::getenv` で値を取得し、値が存在し、かつ先頭文字が文字 `'0'` の場合だけ無効にする。それ以外は有効。文字列全体の parse、数値変換、空白除去、大文字小文字変換はしない（[`engine/src/inkling2/hip/ink_hip_hybrid.hpp:331`](../../../../Niko1221/Strata/engine/src/inkling2/hip/ink_hip_hybrid.hpp)）。

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| HIP hybrid CPU pool が構築される場合 | 有効 | 空文字、`1`、`true`、`false`、` 0`、`00` | `0`、`0anything` |

空文字は設定済みでも先頭文字が `'0'` ではないため有効。`false` も無効値として解釈されず有効になる。判定は大文字小文字を区別する文字比較で、`0` の後続文字や文字列の妥当性は検査しない。`unset` の既定は有効である。

## 有効になる条件

変数による分割が実際に使われるには、すべて次を満たす必要がある。

- HIP backend が使われ、backend 初期化で hybrid controller が有効化されていること。controller は VRAM に全 expert が収まらず、少なくとも 1 expert が VRAM 外にある場合に初期化される（[`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1395-1401`](../../../../Niko1221/Strata/engine/src/inkling2/hip/ink_hip_backend.hip.cpp)）。
- MoE 経路が hybrid fast path に入り、batch `B <= 16` であること（[`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:4425-4427`](../../../../Niko1221/Strata/engine/src/inkling2/hip/ink_hip_backend.hip.cpp)）。
- CPU job が存在すること。RAM 上の S_K / SF4 expert は CPU pool に渡される一方、MX8 は別の GPU streaming job に分けられ、GPU に常駐する expert も CPU split の対象ではない（[`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:4464-4467,4479-4480,4514-4545`](../../../../Niko1221/Strata/engine/src/inkling2/hip/ink_hip_backend.hip.cpp)）。
- CPU pool の worker 数が 2 以上であること。worker 数は `opts.threads` が正ならその数、そうでなければ hardware concurrency に基づく値で初期化される（[`engine/src/inkling2/hip/ink_hip_hybrid.hpp:70-80`](../../../../Niko1221/Strata/engine/src/inkling2/hip/ink_hip_hybrid.hpp)）。
- 各 job が単一 token に対応し、expert body があり、`D` が 8 の倍数、`inter` が 64 の倍数で、codec とデータが `expert_m1_splittable` の条件を満たすこと（[`engine/src/inkling2/hip/ink_hip_hybrid.hpp:113-124`](../../../../Niko1221/Strata/engine/src/inkling2/hip/ink_hip_hybrid.hpp)）。

いずれかが満たされない場合は row split を使わず、通常の CPU expert job 処理へ進む。変数を `0` で無効にした場合も同じく通常経路へ進み、RAM expert の CPU 計算は継続する（[`engine/src/inkling2/hip/ink_hip_hybrid.hpp:113-147,268-317`](../../../../Niko1221/Strata/engine/src/inkling2/hip/ink_hip_hybrid.hpp)）。別の環境変数や CLI 値がこのフラグを上書きする処理は見つからなかった。

## 実行時の詳細

`std::getenv` は `HybridCpuExpertPool` オブジェクトの `split_enabled_` 初期化時に一度呼ばれる。関数内 `static` やリクエスト単位の再読込ではないため、その pool が構築された後の環境変更は反映されない。HIP backend の初期化時に hybrid controller が作られる経路では、その controller 内の pool の構築時に値が確定する（[`engine/src/inkling2/hip/ink_hip_hybrid.hpp:330-332,358-402`](../../../../Niko1221/Strata/engine/src/inkling2/hip/ink_hip_hybrid.hpp)）。

有効で条件を満たすと、各 expert の gate/up 行、activation、down 行の 3 段階を `(job, slice)` task にし、worker が並行して処理する。slice 幅は 8 要素単位に丸め、slice 数は job 数と worker 数から 1〜16 に制限する。完了後は routing に沿った固定 job 順で CPU 出力を加算する。通常経路では worker が expert job を取得し、expert 全体を計算して thread ごとの出力を reduce する（[`engine/src/inkling2/hip/ink_hip_hybrid.hpp:125-137,160-184,189-232,268-317`](../../../../Niko1221/Strata/engine/src/inkling2/hip/ink_hip_hybrid.hpp)）。

backend は CPU job を非同期 dispatch し、GPU 常駐 expert の計算などを進めた後、CPU pool を待って結果を GPU に転送し、MoE 出力に加算する。したがってこの変数が選ぶのは CPU pool 内の計算分割方法であり、expert routing や CPU 対象 job の選択条件ではない（[`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:4549-4552,4556-4572,4599-4605`](../../../../Niko1221/Strata/engine/src/inkling2/hip/ink_hip_backend.hip.cpp)）。

## ログと測定値

`STRATA_HIP_CPU_SPLIT` の値や、row split の有効・無効を直接示すログ・警告・エラーは、確認した実装にはない。split 条件を満たさない場合も通常経路へ静かに切り替わる（[`engine/src/inkling2/hip/ink_hip_hybrid.hpp:113-147`](../../../../Niko1221/Strata/engine/src/inkling2/hip/ink_hip_hybrid.hpp)）。本変数による性能測定値は記載されていない。

## 根拠

- 全リポジトリ参照のうち、実行時に値を読む箇所: `engine/src/inkling2/hip/ink_hip_hybrid.hpp:331`。
- 有効判定、worker split 条件、通常経路: `engine/src/inkling2/hip/ink_hip_hybrid.hpp:113-147,160-184,189-232,268-317,330-332`。
- HIP backend での初期化と適用経路: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1395-1401,4425-4427,4464-4480,4514-4552,4556-4605`。
- HIP backend のビルド対象: `engine/src/inkling2/hip/CMakeLists.txt:30-32,74-97`。
