# `STRATA_L3_PF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

CPU 側にある expert のデータを、次の layer で使われそうな分だけ先に CPU cache へ読み、GPU の処理と重ねる機能を制御する。`engine/src/program/generate.cpp` の native expert pool では次 layer の BF16 router を現在の入力に適用して候補を選ぶ。選んだデータは予測用の読み込みであり、pool の計算結果には使わないため、コード上は生成結果を変えない（`engine/src/program/generate.cpp:1637-1653`）。

同じ名前は独立した経路にもある。`hy4flash` の HIP CPU expert pool と Inkling2 CUDA hybrid engine は idle worker が前 layer の CPU miss を次 layer 用に prefetch する。これら二経路は未設定時 ON で、`generate` の条件付き自動判定とは既定値が異なる（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1559-1566,2071-2094,3145-3163`; `engine/src/inkling2/cuda/ink_hybrid.cuh:991-995,1032-1039,1177-1183`）。

## 値と判定

| 読み取り経路 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `generate` の expert pool | VRAM、resident expert 数、worker 数から自動判定 | 空でない値を `atoi` し、結果が 0 以外（`1`, `2`, `-1`, `1tail`, ` 1`） | 空文字は unset と同じ自動判定。`0`, `0tail`, `true`, `false`, `abc` は `atoi` が 0 を返し無効 |
| `hy4flash` HIP / Inkling2 CUDA | ON | 文字列の先頭 byte が `'0'` 以外（`1`, `true`, `false`, `abc`, 空白始まり、空文字） | 先頭が `'0'`（`0`, `0tail`） |

`generate` は `getenv` で unset と空文字を区別し、空でない値だけ `atoi(env) != 0` とする。文字列全体の妥当性や末尾は検査しない。unset または空文字の自動判定は、総 VRAM が 0 または 13 GiB 超なら OFF、全 expert 数が 0 以下または resident slot が全 expert の 50% 以上なら OFF、それ以外は worker 数 8 以上で ON。境界の 13 GiB 以下は対象、resident がちょうど 50% なら対象外。`generate.cpp` の呼び出しと判定関数を参照（`engine/src/program/generate.cpp:10414-10419`; `engine/include/strata/core/low_vram_rules.hpp:118-126`）。

HIP と Inkling2 は `getenv` が非 null なら `e[0] != '0'` を保存し、unset の場合は初期値 `true` のままにする。空文字は `e[0]` が NUL なので真、つまり ON になる。大文字小文字、数値としての妥当性、文字列全体は判定しない（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:1560,2072`; `engine/src/inkling2/cuda/ink_hybrid.cuh:991,1181`）。

## 有効になる条件

- `generate` では `want_pf` が真で、pool が有効、native expert layout であり、さらに `pool.set_static_slices(true)` が成功して `pool.static_slices()` が真であること。static slices は NUMA split がなく worker が 1 より多い場合に限り有効（`engine/src/program/generate.cpp:10418-10425`; `engine/include/strata/kernels/cpu/pool.hpp:254-259`）。`STRATA_POOL_STATIC` は `atoi != 0` なら slices だけを有効にするが、L3 prefetch 自体を有効にはしない。
- その後、expert source が `FileExpertSource` または `ArenaExpertSource`、AVX2 が利用可能、GPU stage が複数でなく、全 layer の `ffn_gate_inp.weight` が指定 byte 数の BF16-in-F32 weight として得られ、各 router の D2H copy が成功する必要がある。不成立時は L3 prefetch を開始せず、条件判定ブロックでは `strata generate: L3 prefetch off (needs the RAM copy, AVX2, one GPU and BF16 routers)` を stderr に出す（`engine/src/program/generate.cpp:10425-10448`）。
- `generate` は条件を通ると layer ごとの router を RAM に保持する。verify window pool hook が success 状態で RAM-resident experts を持ち、次 layer が存在するときに prefetch を依頼する。末尾 layer、失敗状態、host resident 配列なしでは依頼しない（`engine/src/program/generate.cpp:1637-1653`）。
- HIP 経路では `hy4_graph.hip.h` が CPU miss を記録し、次 layer に保存済み miss がある場合 `CpuExperts::prefetch_experts` を呼ぶ。対象 pool が idle であること、expert body が RAM に resident であることなども必要（`engine/src/hy4flash/run/hy4_graph.hip.h:2445-2453`; `engine/src/hy4flash/run/hy4_cpu_experts.cpp:3145-3163`）。Inkling2 も worker が active で有効な layer・expert ids を受け取る必要があり、直前に記録した次 layer の CPU miss を渡す（`engine/src/inkling2/cuda/ink_hybrid.cuh:1032-1039,1830-1836`）。

## 実行時の詳細

- `generate` は pool 初期化後の設定ブロックで `STRATA_L3_PF` を読み、`want_pf` と routers の初期化結果を保持する。環境変更を再読するコードはこの設定経路にない。`STRATA_L3_PF_TOP` は prefetch 対象数を指定し、未設定時 4、`atoi` 後に 1..16 へ clamp される（`engine/src/program/generate.cpp:1592-1597,10414-10444`）。
- `generate` の verify-window dispatch 後、次 layer の router を現在の入力に適用して token ごとの top-k expert を順位に応じた票で集計し、VRAM 非 resident expert の上位 `top` 個を選ぶ。同点では小さい expert ID を先にし、worker ごとに割り当てられた gate/up/down row 範囲を RAM source から読み、次の pool batch が来ると prefetch は中断される（`engine/src/kernels/cpu/pool.cpp:1620-1633,1635-1726`）。
- HIP と Inkling2 は worker を起動するときに値を一度読む。worker が idle の間に次 layer の CPU miss の body を cache に prefetch し、実計算の work generation が変わると stripe 単位で中断する（`engine/src/hy4flash/run/hy4_cpu_experts.cpp:2071-2094,2097-2129,2132-2149`; `engine/src/inkling2/cuda/ink_hybrid.cuh:1177-1183,1214-1239`）。
- `generate` は有効時に `strata generate: L3 prefetch on: the next layer's top %d non-resident experts, %lld MiB of routers in RAM`、native pool の slices 有効・無効も `strata generate: expert pool: static row slices on` または `... off (the NUMA split, or one thread)` と stderr に出す。HIP は起動時に `[cpuexp] ... l3_pf=on|off` を表示する。Inkling2 のこの設定自体に対応するログは確認できない（同ファイル `1181-1183` 周辺）。

## ログと測定値

`docs/DETAILS.md:1245` は CUDA の一 GPU・native pack・CPU RAM expert・AVX2 条件を説明し、`docs/DETAILS.md:1608` は RTX 3090 / PCIe 4.0 x8 / Ryzen 9 5950X / Linux、0.1.64、`STRATA_L3_PF=1`（top 4）などを条件に decode の測定値を記録している。これは文書にある当時の測定であり、この調査対象 commit での測定ではない。現在の `generate` ソースは明示値に加え、unset・空文字時の自動判定も実装している（`engine/include/strata/core/low_vram_rules.hpp:120-126`; `engine/src/program/generate.cpp:10414-10425`）。

## 根拠

- 判定と自動既定: `engine/include/strata/core/low_vram_rules.hpp:118-126`。
- `generate` の設定、適用条件、ログ: `engine/src/program/generate.cpp:10407-10449`。
- verify-window hook と次 layer prefetch: `engine/src/program/generate.cpp:1628-1653`。
- 候補の集計、RAM row の読み込み: `engine/src/kernels/cpu/pool.cpp:1620-1726`。
- HIP pool の読み取り・worker 動作・呼び出し条件: `engine/src/hy4flash/run/hy4_cpu_experts.cpp:1559-1566,2071-2094,2097-2129,2132-2149,3145-3163`; 呼び出し元 `engine/src/hy4flash/run/hy4_graph.hip.h:2445-2453`。
- Inkling2 CUDA の読み取り・worker 動作・呼び出し条件: `engine/src/inkling2/cuda/ink_hybrid.cuh:991-995,1032-1039,1177-1183,1214-1239,1830-1836`。
- Strata 資料の仕様説明・測定記録: `docs/DETAILS.md:1245,1608`。
