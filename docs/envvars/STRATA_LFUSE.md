# `STRATA_LFUSE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA 系 verifier と SYCL verifier の speculative decode 検証窓で、共有 expert（shared expert）の gate/up 処理と gate の適用を統合する経路を許可する opt-in 変数。値が有効でも、全 expert が GPU 常駐する窓など後述の条件が揃わなければこの融合経路には入らない。判定関数 `g_lfuse()` は各 verifier の `verify.cpp` にある（`engine/src/core/verify.cpp:125,1521-1525`、`engine/sycl/src/core/verify.cpp:130,1059-1063`）。

## 値と判定

両 verifier とも `std::getenv` の結果が null でなく、かつ `v[0] == '1'` の場合だけ true とする。文字列全体の parse・数値変換・範囲検査はしない。関数内 `static const bool` に初回評価結果を保存する（`engine/src/core/verify.cpp:125`、`engine/sycl/src/core/verify.cpp:130`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA 系 verifier / SYCL verifier の読み取り | false（ただし起動時に GPU 別既定値が設定される場合あり） | `1`、`10`、`1anything`、`1 `（先頭 byte が `1`） | 空文字、`0`、`01`、`true`、` 1` など先頭 byte が `1` でない値 |

大文字小文字、空白、数値としての妥当性は検査しない。環境変数が空文字でも設定済みとして扱われ、既定値設定処理に上書きされず、verifier の判定は false になる（`engine/src/core/nv_defaults.cpp:227-233`、`engine/src/core/arch_defaults.cpp:307-310,320-323`）。

起動時の既定値設定では、対象 GPU の表に `STRATA_LFUSE=1` が含まれ、かつ当該スイッチが未設定の場合に値を追加する。したがって、環境から明示的に `0` や空文字を渡せば優先される。CUDA では sm_86（`STRATA_SM86_PERF` が `0` でない場合）、sm_89、sm_120、sm_70、sm_121 の各表に含まれ、sm_89 / sm_120 / sm_70 / sm_121 は各 `STRATA_SM*_PERF=0` または `STRATA_DEFAULTS=026` で表が無効になる。sm_86 は `STRATA_SM86_PERF=0` で表が無効になる。表が適用されるのは単一の同一 compute capability の GPU 群など `generate.cpp` が `apply_nv_defaults` を呼ぶ経路である（`engine/src/core/nv_defaults.cpp:41-42,63,75-82,95,104-106,123,136-140,150,176-180,210,222-233`、`engine/src/program/generate.cpp:4440-4449`）。

HIP 系既定値には gfx1151（`STRATA_GFX1151_DEFAULTS=0` で無効）、および discrete gfx1100/1101/1102（`STRATA_DEFAULTS=026` または `STRATA_GFX11_DEFAULTS=0` で無効）がある。gfx1103 と gfx1150 は engine の arch defaults ではなく、setup が生成する設定の `env` に `1` を入れる（gfx1103 は opt-in が有効かつ非 Windows、gfx1150 は opt-in が有効な場合）。gfx12 の arch table にはこの変数がない（`engine/src/core/arch_defaults.cpp:64-66,83-89,302-323`、`engine/include/strata/core/gfx11_extra.hpp:27-45`、`terminal/setup.py:4472-4485`、`terminal/strata_control/setup_config.py:452-465`）。

## 有効になる条件

- verifier の窓が `ar_on()`（全 expert が VRAM 常駐し、`ar_off_` ではない状態）であること。常駐条件が崩れた窓では適用しない（`engine/include/strata/core/verify.hpp:364-370`、`engine/sycl/include/strata/core/verify.hpp:364-370`）。
- `STRATA_DEC_BATCH` が未設定、または `atoi` の結果が非 0 であること。`0` や `0tail` は batch decode を無効にし、`lfuse_on` も false になる（`engine/src/core/verify.cpp:1489,1522-1524`、`engine/sycl/src/core/verify.cpp:1048,1060-1062`）。
- 検証窓の行数 `n` が 2〜8、native MoE combine が有効、かつ native BF16 shared expert が有効であること（同上）。
- gate を router GEMV に載せる部分には追加条件がある。`STRATA_LFUSE_GATE` は未設定または先頭文字が `0` 以外なら許可する。router weight があり、native router が有効で、CUDA は `NE == 512 && K == 10`、SYCL は `NE == 512 || NE == 256` かつ `K == 10` のときだけ multi-aux GEMV を試す。モデルに `ffn_gate_inp_shexp.weight` がない、これらの条件を満たさない、または multi-aux 呼び出しが gate を準備できない場合、router は通常の multi GEMV に戻り、共有 expert 側で gate を計算する（`engine/src/core/verify.cpp:188,2631-2646`、`engine/sycl/src/core/verify.cpp:131,1578-1593`）。
- gate/up 行列を一つの MMVQ launch にまとめる部分は `STRATA_LFUSE_PAIR` が未設定または先頭文字が `0` 以外の場合に要求される。実際の pair kernel は gate と up の weight type が同じで、対応する `native_mmvq_pair` が成功するときだけ使われる。interleaved MMVQ が適用できる場合はその経路が優先され、pair 条件が不成立なら別々の MMVQ 呼び出しに戻る（`engine/src/core/verify.cpp:189,2747-2751`、`engine/sycl/src/core/verify.cpp:132,1668-1672`、`engine/src/kernels/cuda/shared_expert.cu:229-244`）。
- 共有 gate の遅延適用は、router で `sg_ready` が true になった場合だけ combine 側で行う。CUDA verifier のこの router 経路は `NE == 512 && K == 10`、SYCL は `NE == 512 || NE == 256` と `K == 10` が条件で、SYCL には gfx906 向けの別 routing 分岐もある（`engine/src/core/verify.cpp:2634-2645,2750-2751`、`engine/sycl/src/core/verify.cpp:1581-1593,1671-1672`）。

## 実行時の詳細

`g_lfuse()` は `lfuse_on(n)` が評価される検証窓処理で初回呼び出し時に環境を読み、結果をプロセス内 static に保持する。以降の環境変更は反映されない。GPU 別の既定値は起動初期化時に、ユーザーが事前に設定した値を尊重して `setenv` / `_putenv_s` で補われる（`engine/src/core/verify.cpp:125,1521-1525`、`engine/sycl/src/core/verify.cpp:130,1059-1063`、`engine/src/core/nv_defaults.cpp:227-233`）。

`lfuse_on` が true のとき、かつ `STRATA_LFUSE_GATE` が許可する場合、共有 expert の gate weight を router GEMV の auxiliary row として渡す。`sg_ready` が true なら shared expert は gate を適用せず raw gate 値を保持し、最後に `native_moe_combine_multi_hits_gated` が shared 出力に sigmoid gate を掛けながら combine する。`STRATA_LFUSE_PAIR` が許可すれば `shared_expert_multi` に pair bit を渡し、上記の適合条件で gate/up を融合する（`engine/src/core/verify.cpp:2634-2645,2747-2751,2944-2949`、`engine/sycl/src/core/verify.cpp:1581-1593,1668-1672,1810-1818`、`engine/src/kernels/cuda/shared_expert.cu:216-244,258-281`）。

この変数が許可する融合は shared expert の経路である。KV append の multi-step 呼び出しは `STRATA_DEC_BATCH`、`STRATA_NO_BATCH_KV`、batch 状態などで分岐しており、`STRATA_LFUSE` の判定を参照しない（`engine/src/core/verify.cpp:2350-2375`、`engine/sycl/src/core/verify.cpp:1367-1388`）。

## ログと測定値

この変数だけを理由に出る専用ログはない。GPU 別既定値を自動適用した場合は、起動時の既定値一覧ログにこの名前が含まれる。dispatch reporting が有効な場合、CUDA verifier は router の `shared-expert gate in the router launch=%ld` と combine の `kind %ld (0 per-token, 1 multi, 2 multi+hits, 3 multi+hits gated)` を出す。SYCL verifier には同じ router 計測行はない（`engine/src/core/nv_defaults.cpp:249-255`、`engine/src/core/verify.cpp:2663,2944`）。

router・shared expert・combine の例外はそれぞれ `verify router: `、`verify shared expert: `、`verify combine: ` を `err` に設定してその処理を失敗させる（`engine/src/core/verify.cpp:2646,2752-2754,2946-2949`、`engine/sycl/src/core/verify.cpp:1593,1673-1675,1811-1813`）。この文書では、呼び出し側がその失敗をプロセス終了へ結び付けるかまでは特定していない。性能値は記載しない。

## 根拠

- 読み取り・static cache・適用条件: `engine/src/core/verify.cpp:125,1489,1521-1525`、`engine/sycl/src/core/verify.cpp:130,1048,1059-1063`
- CUDA / SYCL verifier の gate・pair・combine 経路: `engine/src/core/verify.cpp:2631-2646,2747-2754,2944-2949`、`engine/sycl/src/core/verify.cpp:1578-1593,1668-1675,1810-1818`
- 共有 expert の pair 条件と gate 適用: `engine/src/kernels/cuda/shared_expert.cu:216-244,258-283`
- NVIDIA / AMD の GPU 別既定値: `engine/src/core/nv_defaults.cpp:41-42,63,75-82,95,104-106,123,136-140,150,176-180,210,222-233`、`engine/src/core/arch_defaults.cpp:64-89,302-323`、`engine/include/strata/core/gfx11_extra.hpp:27-45`、`terminal/setup.py:4472-4485`、`terminal/strata_control/setup_config.py:452-465`
- all-resident 条件・KV append の別条件: `engine/include/strata/core/verify.hpp:364-370`、`engine/src/core/verify.cpp:2350-2375`、`engine/sycl/src/core/verify.cpp:1367-1388`
