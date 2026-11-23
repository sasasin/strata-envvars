# `STRATA_GU_LANES`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。`git status --short --branch` は `## main...origin/main` で未コミット変更なし。

## 役割

SYCL（Intel Arc）版 engine の grouped expert カーネルで、gate/up の 1 行を何レーンで分担するかを実行時に選ぶ。読み取りは `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4481-4486` の `lanes_env()` と `gu_lanes()`。

変わるのは行あたりのレーン数、それに伴う 1 work-group あたりの行数（`256 / lanes`）と起動グリッド、そして縮小和の加算順序。ルーティング、量子化、サンプリング、ダウン側（別変数 `STRATA_DOWN_LANES`）は変わらない。8 以外を選ぶと 8 レーン前提の最適化カーネル群が使われなくなる（「有効になる条件」を参照）。

このファイルは SYCL プロジェクトだけがビルドする（`engine/CMakeLists.txt:23-33`、`engine/sycl/CMakeLists.txt:141-151,273-286`）。CUDA / HIP / Metal 版に本変数の読み取りはない。

## 値と判定

`std::getenv` で名前を引き、`std::atoi` で整数にして `4`・`8`・`16`・`32` の完全一致だけを採用する。一致しなければ無言で `kExpertLanes`（コンパイル時 macro `STRATA_EXPERT_LANES`、`#ifndef` 既定 8）に戻る（`iq_kernels.dp.cpp:4481-4486`、`1173-1180`）。数値全体の検査、空白除去、大文字小文字の扱いはなく、範囲 clamp もない。

| 設定値 | 採用される lanes |
|---|---|
| 未設定 | `kExpertLanes`（既定 8） |
| `4` / `8` / `16` / `32` | その値（前後の空白や後続文字は無視: ` 8`、`08`、`8x`、`16abc` も可） |
| 空文字 `""` | `kExpertLanes`（`atoi("")` は 0） |
| `0`、`1`、`2`、`64`、`-8` | `kExpertLanes` |
| `4.9` | 4（`atoi` が整数部だけ読む） |
| `0x10` | `kExpertLanes`（`atoi` は 0） |

既定値はビルドの macro に依存する。`STRATA_EXPERT_LANES` を 16 としてビルドした engine では、未設定・空文字・無効値のいずれも 16 になる。

## 有効になる条件

- SYCL engine のバイナリであること（上記ビルド条件）。
- MoE expert の gate/up が `native_expert_grouped` を通る経路であること（`iq_kernels.dp.cpp:7767-7883`）。具体的には検証（spec/verify）ウィンドウの expert 群（`engine/sycl/src/core/verify.cpp:1747-1749`）、peer/remote expert（`engine/sycl/src/core/remote_experts.cpp:435-437`）、および parity / bench ツール。通常デコードの cache hit 経路 `moe_hit_grouped_s2_dev`（`engine/sycl/src/core/session.cpp:1268-1270`）は本変数を読まない。
- `STRATA_EXPERT_SPLIT=1` かつ `STRATA_OLD_IQ_MMVQ` が無効のとき、`Split` を持つ形式は `launch_gu_multi` に移り lanes を使わない（`iq_kernels.dp.cpp:3937`、`6053-6067`）。`STRATA_OLD_IQ_MMVQ=1` なら split の設定にかかわらず lanes 経路のまま（`6049-6058`）。
- `STRATA_KQ_GU_LANES` が設定されていると（空文字でも「設定あり」）、`KqSplit` を持つ形式（K-quant / Q5_1 / Q8_0 など、IQ4_XS を除く）はそちらの値を使う（`4515-4518`、`5944`、`2601-2613`）。
- lanes が 8 でないと、8 レーン前提の経路がすべて外れる。fused GU+SwiGLU+q8_1（`STRATA_EXP_MODE=8` のときだけ。`7797-7800`、`7748-7752`）、IQ3_S two-row reuse（`6025-6038`）、gu_type 16/22 の S4 / WG16 / grid64 変種（`7849-7872`）、`LN == 8` の constexpr 分岐（packed signs、prepared、IQ2_XXS、ps、row reuse。`5848-5910`）。fused が外れると SwiGLU と q8_1 量子化が別カーネルになる。
- 値が 8 でも、上記の各経路は `L.n_embd == 2560`・`L.n_ff == 640`、Battlemage、`STRATA_EXP_MODE` などの追加条件を満たす必要がある。

## 実行時の詳細

読み取りはプロセス内で最初に `gu_lanes()` / `kq_gu_lanes()` が評価された 1 回だけ。関数内 `static const int` に保存され、以後 `setenv` しても反映されず、リクエストごとの再読みもない（`4486`、`4518`）。

採用値は `launch_gu_lanes<TG>` の switch で `gu_port_km<TG, 4|16|32|8>` に振り分けられる（`5939-5950`）。`launch_gu_port` は `ROWS = 256 / LN`、`gx = ceil(2 * n_ff / ROWS)`、256 スレッドの work-group で起動し（`5911-5918`）、`native_gu_kernel` は `row = group(2) * (256 / LN) + local_id / LN`、`sub = local_id % LN` で行を分担する（`2745-2760`）。

縮小和は `row_dot_lanes` が `k += LANES` でストライドし、`lanes_sum<LANES>` が xor permute でまとめる（`1188-1200`）。lanes を変えると加算順序が変わるため、gate/up の値がビット一致する保証はない。ダウン側の式と SwiGLU 以降の式は変わらない。

エンジン自身が本変数を設定・上書きする箇所、子プロセスへ転送する箇所はコードにない。

## ログと測定値

採用値・fallback・無効値のいずれもログや警告を出さない（`lanes_env` は値を返すだけ）。終了コードや失敗経路も変えない。

`docs/A770_SPEED_SPEC.md:596-604` は A770・同一セッション・同一設定の交互 A/B で、8 レーン 12.40 / 12.60 tok/s、16 レーン 12.1 / 12.6 tok/s を報告し、レーン数は「null result」で既定 8 のままと結論している。ただしこれはコンパイル時 macro `STRATA_EXPERT_LANES` の測定であり、本変数の測定ではない。同資料の `-DSTRATA_SYCL_EXPERT_LANES` という CMake オプションはこの commit には存在せず、macro は `STRATA_EXPERT_LANES` だけ（`iq_kernels.dp.cpp:1176-1178`）。

同梱台帳は本変数を status `research`、note "Lane-count tuning knob for SYCL quants; measurement note only." と記録する（`terminal/data/settings-register.json:13332-13361`）。

## 根拠

- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1173-1180`（`kExpertLanes` と既定 8）
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4478-4487`（`lanes_env`、`gu_lanes`、`down_lanes`）
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4515-4518`（`STRATA_KQ_GU_LANES` の優先）
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5843-5918,5939-5950`（起動形状と switch）
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1188-1200,2719-2761`（レーン分担と縮小和）
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:6025-6038,6049-6067,7748-7800,7849-7872`（8 レーン前提の経路）
- `engine/sycl/src/core/verify.cpp:1726-1750`、`engine/sycl/src/core/remote_experts.cpp:435-437`、`engine/sycl/src/core/session.cpp:1263-1270`（呼び出し経路）
- `docs/A770_SPEED_SPEC.md:596-604`、`terminal/data/settings-register.json:13332-13361`（資料と台帳）
