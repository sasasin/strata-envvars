# `STRATA_GR_UP_WIDE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の fused hyper-connection multi-read で、up projection に使うカーネルを選びます。有効時は 1 warp あたり 1 行を処理する `gr_up_wide_kernel` を起動します。設定は読み取り方式を選ぶもので、環境変数自体を Strata がログに出す処理はありません。

このカーネルは CUDA ビルドの `src/kernels/cuda/fused_gr.cu` にあり、HIP ビルドでは環境変数の値にかかわらず選ばれません。モデル側で fused GR が有効であることも必要です。

## 値と判定

Strata は `std::getenv` の結果を `std::atoi` に渡し、変換結果が 0 かどうかで判定します。文字列全体の妥当性検査はしません。

| `STRATA_GR_UP_WIDE` | 判定 |
|---|---|
| 未設定 | CUDA device ごとの既定値を使う |
| 空文字 | `atoi("") == 0` なので無効 |
| 数値として 0 に変換される文字列（例: `0`, `false`, `abc`） | 無効 |
| `atoi` が 0 以外を返す文字列（例: `1`, `2tail`, `-1`） | 有効 |

したがって `true` は有効値として認識されません。先頭の空白や符号を含む整数は `atoi` の規則で変換され、数値の後ろの文字列は判定に使われません。範囲 clamp や無効文字列時の既定値への fallback はありません。値が設定されている場合は、0 に変換される値も含め、GPU 世代による既定値より明示値が優先します。

未設定時の既定値は次のとおりです。

| 条件 | 既定値 |
|---|---|
| CUDA、compute capability 12.0、`STRATA_DEFAULTS=026` ではなく、`STRATA_SM120_PERF` が unset または `atoi` が 0 以外 | 有効 |
| 上記以外の CUDA device | 無効 |
| HIP ビルド | 無効 |

`STRATA_DEFAULTS=026` は `026`、`0.2.6`、`v0.2.6` の完全一致で有効になり、既定値を無効化します。`STRATA_SM120_PERF` は unset または `atoi` が 0 以外なら有効で、`0` や `false` など 0 に変換される設定は 12.0 系の既定セットを無効にします。どちらも `STRATA_GR_UP_WIDE` が明示設定されていればその判定を上書きしません。

## 有効になる条件

値判定が有効でも、次の条件を満たさなければ wide up kernel は起動しません。

- CUDA 版の `fused_gr_read_multi` から、通常の `launch_multi` 経路に到達すること。Strata の HIP 版は `gr_up_wide_on()` が常に false を返します。
- `launch_multi` に渡る read が `q8w == false` であること。`q8w` は `s_down != nullptr` で判定され、Q8 weight の経路では通常の up kernel が使われます。
- `q8_mixed` 出力がないこと。Q8_1 の出力先がある場合も wide kernel は使われません。
- `STRATA_GR_V3` の分割 read が有効な構成で先に選ばれて return しないこと。V3 の分割が利用できず通常経路へ落ちた場合は wide 判定へ進みます。
- fused GR 自体が有効で、形状がこの kernel のコンパイル対象（`n_embd=2560`, `hc=4`, `hc_lr=320`）に合うこと。generate 経路では `--no-fused-gr`、非 native MMVF、GPU stage、layer/half dump、stage timing などにより fused GR が無効になる場合があります。

通常の generate 経路で fused GR を有効にする条件は `o.gr_native_mmvf && !o.no_fused_gr && !o.gpu_stages && o.dump_layers.empty() && o.dump_halves.empty() && !o.stage_timing` です。`STRATA_GR_UP_WIDE` 自体に対応する CLI 引数はありません。

## 実行時の詳細

`gr_up_wide_on()` は最初に呼ばれた時点で `STRATA_GR_UP_WIDE` を関数内 static に保存します。unset の場合は CUDA device を取得し、device ごとに compute capability を調べて既定値を cache します。起動後にプロセス環境を変更しても再評価されません。`STRATA_SM120_PERF` と `STRATA_DEFAULTS` も各 helper の static 値として一度評価されます。複数 GPU では既定値の判定結果を device ごとに持ちますが、明示された `STRATA_GR_UP_WIDE` の値はプロセス内で共通です。

判定が有効で Q8 条件に当たらない場合、multi-read の token 数に応じたテンプレート版 `gr_up_wide_kernel` を stream 上で起動します。通常の up kernel と同じ出力になる設計としてコードコメントに記載されています。起動時に `cudaGetLastError()` が失敗すると `fused_gr_read_multi: <CUDA error>` を stderr に出して `exit(1)` します。この失敗処理は multi-read の通常経路全体に対するもので、wide kernel 専用のログや失敗分岐ではありません。unset 時に device 取得または capability 判定が失敗しても、wide の既定は有効にならず、ここで環境変数固有の警告は出ません。

コードコメントが記す測定は RTX PRO 5000、IQ3_S、全 expert が VRAM resident の条件で、story decode 197.6→201.3 tok/s（+1.9%）、code decode 243.5→245.1 tok/s（+0.7%）、出力 token ID は 6/6 run で同一です。これはソースコメントに記された測定であり、この調査で再測定した値ではありません。`docs/DETAILS.md` にはこの環境変数名の説明は見つからず、同資料と照合できる対応する説明・測定条件はありません。

## 根拠

- `src/kernels/cuda/fused_gr.cu:466-493` — `atoi` による明示値判定、HIP の無効化、GPU ごとの既定値 cache。
- `include/strata/core/sm120_series.hpp:30-43,103-105` — `STRATA_SM120_PERF` の値判定と compute capability 12.0 での既定値。
- `include/strata/core/defaults_026.hpp:21-29` — `STRATA_DEFAULTS` の完全一致判定と static cache。
- `src/kernels/cuda/fused_gr.cu:1461-1473` — `q8w` / `q8_mixed` 条件、wide kernel の token 数ごとの起動。
- `src/kernels/cuda/fused_gr.cu:2402-2409,2419-2427,2466-2505,2531-2538` — Q8_1 有無、GR_V3 の先行分岐、通常経路と CUDA エラー時の終了。
- `src/program/generate.cpp:4602-4611` — generate 経路で fused GR を有効にする条件。
- `src/core/layer.cpp:1477-1479,1617-1627` — layer 側の fused GR 利用条件。
- `src/kernels/cuda/fused_gr.cu:457-469` — wide kernel の処理方式とコードコメント記載の測定値。
- `CMakeLists.txt:492` — CUDA kernel source として `fused_gr.cu` を含める指定。
