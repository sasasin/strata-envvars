# `STRATA_DOWN_LANES`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL エンジンの grouped native expert down-projection kernels で、1 行の計算を分担する lane 数を指定する。選択値は `launch_down_lanes` のテンプレート引数となり、選択した down kernel の行あたりの lane 分割に使われる。CUDA/HIP 側の同名設定は確認できず、この読み取りは `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp` 内にある（`iq_kernels.dp.cpp:4478-4487,5991-5999`）。

## 値と判定

`lanes_env` は `std::getenv` で値を取得し、設定されていれば `std::atoi` で整数変換する。変換結果が `4`, `8`, `16`, `32` のいずれかの場合だけ採用し、それ以外は `kExpertLanes` に戻す。未設定の場合も `kExpertLanes`。このソースでは `STRATA_EXPERT_LANES` が別途定義されていなければ 8 である（`iq_kernels.dp.cpp:1173-1180,4481-4485`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL engine | ビルド時の `STRATA_EXPERT_LANES`（既定 8） | `atoi` の結果が 4 / 8 / 16 / 32。例: `4`, `8`, `16`, `32`, `8tail`, `  +8` | それ以外はビルド既定値。例: 空文字、`0`, `0anything`, `3`, `-4`, `true`, `  ` |

文字列全体の妥当性検査や大文字小文字の判定はない。`atoi` が読む数値 prefix だけで判定するため、`8tail` は 8 として採用され、非数値文字列や空文字は 0 となって既定値に戻る。値は clamp されず、許可された 4 値以外はすべて既定値になる。`atoi` の変換範囲を超える文字列については、このコードから定義された fallback を保証できない。

## 有効になる条件

- `engine/sycl` の SYCL build に含まれる kernel 経路が対象。`engine/sycl/CMakeLists.txt:40-45` は `iq_kernels.dp.cpp` を `strata_kernels` のソースとして登録する。CUDA/HIP engine でこの変数を読む箇所は見つからなかった。
- grouped native expert の down projection が呼ばれ、型別 dispatch が `launch_down<TD>` を選ぶ必要がある。通常の `native_expert_grouped` は down の形式を `L.d_type` で dispatch する（`iq_kernels.dp.cpp:7767-7770,7948-7982`）。SYCL verify-window と remote-expert の native layout 経路からこの関数が呼ばれる（`engine/sycl/src/core/verify.cpp:1726-1749`; `engine/sycl/src/core/remote_experts.cpp:431-442`）。
- `STRATA_OLD_IQ_MMVQ` が有効な場合、または `STRATA_EXPERT_SPLIT` が無効な場合、split 形式を含む down kernel は lane kernel 経由となる。split ではない形式も lane kernel 経由である。split 形式で `STRATA_EXPERT_SPLIT` が有効かつ旧 kernel が無効の場合は `launch_down_multi` に進むため、この変数による lane 分割は使われない（`iq_kernels.dp.cpp:3927-3938,6115-6120`; `kSplit` の形式別指定は `iq_kernels.dp.cpp:1246-1253` 以降）。
- down type 42 では、`STRATA_OLD_IQ_MMVQ` と `STRATA_EXPERT_SPLIT` が無効で、選ばれた値が 8、かつ `q2_word_expand_enabled` が true の場合、`launch_down_q2_word_expand` に分岐して lane dispatch を通らない。`STRATA_SYCL_Q2_WORD_EXPAND` の先頭文字が `0` ならこの fast path 判定は false となる。Battlemage 以外の device でも false（`iq_kernels.dp.cpp:3942-3951,6101-6106`）。
- down type 20 では `STRATA_IQ4NL_DOWN_SLM` が有効で、旧 kernel が無効、かつ `L.n_embd == 2560` / `L.n_ff == 640` の場合に SLM kernel へ分岐し、lane dispatch を通らない（`iq_kernels.dp.cpp:6108-6113`）。
- 該当 fast path が選ばれなければ、値は 4 / 8 / 16 / 32 の down lane kernel に対応する template specialization を選ぶ（`iq_kernels.dp.cpp:5991-5999,6115-6120`）。

## 実行時の詳細

値は `down_lanes()` 内の関数ローカル `static const int` に初回評価時に保存される。実行中にプロセス環境を変更しても、このプロセスでは再評価されない。実際に `launch_down_lanes` または type 42 の lane 数判定へ到達するまでは評価されない（`iq_kernels.dp.cpp:4481-4487,5991-5999,6101-6106`）。

値は down projection の kernel 選択だけに使われる。gate/up projection には別の `STRATA_GU_LANES` 読み取りがある。`STRATA_DOWN_LANES` を gate/up の lane 値としても使う処理は確認できなかった（`iq_kernels.dp.cpp:4486-4487,5991-5999`）。設定の読み取り失敗や無効値に対する警告・終了処理はなく、既定値へ静かに fallback する。

## 根拠

- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:1173-1180` — compile-time 既定 lane 数（未定義時 8）。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:4481-4487` — `getenv`、`atoi`、有効値集合、既定値、static cache。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:5991-5999,6101-6120` — down lane specialization の選択と lane dispatch を迂回する条件。
- `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7767-7775,7948-7982` — grouped expert down 経路の入り口・down 型 dispatch。
- `engine/sycl/src/core/verify.cpp:1726-1749`; `engine/sycl/src/core/remote_experts.cpp:431-442` — SYCL verify と remote-expert native layout 呼び出し。
- `engine/sycl/CMakeLists.txt:40-45` — 対象 kernel source の SYCL build 登録。

`docs/DETAILS.md` と Strata の Markdown docs には、この変数の動作や測定値の記述は見つからなかった。性能・数値出力への影響は測定していない。
