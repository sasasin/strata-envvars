# `STRATA_GR_MORE_GROUPS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL 版 fused hyper-connection read の multi-token down / up kernel を、より小さな work-group に分けるかを選ぶ。`1` はデバイス世代にかかわらずこの分割を選び、`0` は従来の分割を選ぶ。未設定時は Arc A-series（Alchemist）だけで有効になる。値は計算式や CLI 引数を変えず、`fused_gr_read_multi` が投入する kernel の構成を切り替える（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:820-832, 3139-3159, 3360-3370, 3485-3493`）。

## 値と判定

`gr_more_groups` は `std::getenv` の結果が null でない場合に `std::atoi(e) != 0` を使う。文字列全体の妥当性検査や範囲チェックはない。`atoi` が読む先頭の整数部分が 0 なら無効、0 以外なら有効で、先頭空白・符号・数字の後ろの文字は通常の `atoi` の変換規則に従う。したがって空文字、`true`、`false`、`0anything`、`00` は無効、`1`、`01`、`-1`、`1suffix` は有効。整数として読める数字がない文字列も 0 になる。整数範囲外の文字列はコードで扱いを定めていない。

| デバイス世代（`STRATA_INTEL_GEN` 等による判定を含む） | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Alchemist | 有効 | `atoi` の結果が非 0 | `atoi` の結果が 0 |
| Battlemage / Unknown | 無効 | `atoi` の結果が非 0 | `atoi` の結果が 0 |

未設定時だけ `strata::intel_gpu_gen(q->get_device()) == Alchemist` を既定値にする。`STRATA_INTEL_GEN` が空でない有効な値を指定するとデバイス世代判定を上書きするため、この未設定時の既定値にも影響する。同変数の不正値は世代判定側が stderr に警告して自動判定へ戻す（`engine/sycl/include/strata/sycl_queue.hpp:139-153, 154-191`）。

## 有効になる条件

- この読み取り箇所は SYCL エンジンの `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp` にある。CUDA/HIP 実装の環境変数ではない。SYCL ビルドは別プロジェクトとして構成され、同ファイルが SYCL の `strata_kernels` に含まれる（`engine/sycl/CMakeLists.txt:1-11, 262-288`）。
- 通常の `generate` 経路で fused read を使うには、`--no-fused-gr` を指定せず、native MMVF (`o.gr_native_mmvf`) が有効で、GPU stages・layer/half dump・stage timing の各経路を使わないことが必要。さらに対象 geometry が `fused_gr_supported` の寸法条件を満たす必要がある（`engine/sycl/src/program/generate.cpp:3221-3228`; `engine/sycl/src/core/layer.cpp:1558-1559, 1620-1631`）。これらを満たさない経路は通常の `gr_read` へ進み、この変数による切替はない。
- down 側の細分化には `STRATA_GR_DOWN_SLICED` が有効であることも必要（同変数の未設定時は sliced）。sliced が無効なら down 側は別の direct/tiled 経路へ進み、`STRATA_GR_MORE_GROUPS` はその down kernel を切り替えない。ただし up 側は別判定なので、より優先する cached-norm / prepared-LO 経路に入らず、`gr_more_groups` 分岐まで到達すれば細分化される（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:834-836, 3359-3416, 3471-3493`）。
- `STRATA_SYCL_GR_LO_ONCE` または cached-norm の設定により `lo_once` が成立すると、sliced down の more-groups 分岐を通らず、prepared-LO up kernel が選ばれる。この場合、対象変数の down/up 用 more-groups kernel は使われない（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:1149-1152, 3359-3365, 3485-3493`）。
- `STRATA_GR_LARGE_GRF` と併用でき、more-groups kernel の 128/256 GRF 版を選ぶ別条件になる（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:808-818, 3360-3364, 3487-3490`）。Battlemage 専用の private F32 経路は `!gr_more_groups(st)` を条件に含むため、この変数が有効ならその経路を選ばない（同 `:2685-2689`）。

## 実行時の詳細

環境値を読むのは `gr_more_groups(sycl::queue*)` の関数内 static 初期化時、すなわちこの関数への初回到達時である。初回に環境値が設定されていればその真偽値を以後の呼び出しで使い、初回に未設定ならその時渡された queue のデバイス世代による既定値を保持する。関数内 static は関数単位なので、後から別 queue / GPU で呼んでも再判定しない。プロセス起動後に環境を変更しても反映されない（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:826-832`）。この値を子プロセスへ渡す処理は同ファイルにない。

有効時、sliced down は各 slice を row block に分け、コメント上は 80 から 480 work-group に増やす。続く reduction は 8 要素ずつ読み込んで元と同じ順序で加算する。up は 16 列単位の 160 group から 8 列単位の 320 group へ切り替わり、low-rank 値は group 0 が書く。無効時は従来の sliced down / 通常 up kernel を選ぶ（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:731-770, 820-825, 853-856, 3360-3364, 3487-3493`）。

この実装は `fused_gr_read_multi` が実行するたびに `gr_more_groups` を分岐に使う。単一 read も条件に応じて `fused_gr_read_multi` を呼ぶ。generate では layer の mixer / FFN read から呼び出されるほか、SYCL の検証・MTP 経路や `gr_bench` からも呼ばれる（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3139-3159, 3510-3533`; `engine/sycl/src/core/layer.cpp:1620-1631, 1643-1654`; `engine/sycl/src/core/mtp.cpp:948, 1079, 1207-1218`; `engine/sycl/src/core/verify.cpp:1228, 1891-1924`; `engine/sycl/src/kernels/gr_bench.cpp:39-49`）。

## ログと測定値

この変数の読み取り・有効化・無効化に伴う専用ログ、警告、終了分岐はない。`fused_gr_read_multi` の引数が不正な場合は別理由で stderr に `fused_gr_read_multi: invalid arguments` または `fused_gr_read_multi: invalid arguments for token %d` を出して終了するが、環境変数の値を検査した結果ではない（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:3142-3155`）。

実装コメントは A770 の `gr_bench` で 1–6 token の fused GR read が 117–180 µs から 87–149 µs になり、decode が 28.04–28.54 から 29.99–30.00 tok/s になったと記す（`engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:820-825`）。これはソースコメントに記録された値であり、この調査では再測定していない。リポジトリの docs でこの変数名を含む説明は見つからなかった。

## 根拠

- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:820-832` — 既定値、`getenv` / `atoi`、static cache。
- `engine/sycl/include/strata/sycl_queue.hpp:139-191` — Alchemist / Battlemage / Unknown の判定と `STRATA_INTEL_GEN` 上書き。
- `engine/sycl/src/program/generate.cpp:3221-3228`, `engine/sycl/src/core/layer.cpp:1558-1559, 1620-1631` — 通常 generate から fused read を選ぶ条件と呼び出し。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:2685-2689, 3139-3159, 3359-3416, 3465-3500` — 呼び出し時の分岐、優先経路、エラー経路。
- `engine/sycl/src/kernels/cuda/fused_gr.dp.cpp:731-770, 853-856, 3485-3493` — down / reduce / up の work-group 構成。
- `engine/sycl/CMakeLists.txt:262-288` — SYCL engine と kernel のビルド対象。
