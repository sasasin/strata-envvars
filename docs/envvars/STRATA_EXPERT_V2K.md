# `STRATA_EXPERT_V2K`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA/HIP エンジンの grouped expert decode で、対象の Q4_K / Q5_K gate/up と Q5_1 / Q8_0 down に対し、V2K (S27) の gate/up カーネルを選ぶスイッチです。対象外では従来の `native_gu_kernel` / `native_down_kernel` 系へ進みます。Qwen3.6 の該当形状では V2K gate/up と SwiGLU・q8_1 量子化を使い、down は従来の `launch_down<13>` を使います（`engine/src/kernels/cuda/iq_kernels.cu:7134-7182`）。

V2K 分岐は `native_expert_grouped` 内の decode 処理にあり、通常の CPU 経路や prompt の環境変数設定ではありません。同名の SYCL 読み取りはカーネル選択を変えず、注記の出力だけに使われます（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7782-7790`）。

## 値と判定

CUDA/HIP は `getenv` の返す文字列の先頭バイトだけを判定し、数値 parse、文字列全体比較、空白 trim はしません。`v != nullptr && v[0] != '\0'` なら先頭が `'1'` のときだけ有効、それ以外は無効です。未設定または空文字列はビルド・GPU による既定判定へ進みます（`engine/src/kernels/cuda/iq_kernels.cu:7138-7158`）。

| 実行経路 | 未設定または空文字列 | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| CUDA build | 無効 | `1`, `10`, `1anything` | `0`, `true`, ` 1`, `anything` |
| HIP build（`STRATA_HIP_GFX906` 以外） | 現在の device が gfx12、または Windows 上の gfx1151 なら有効。それ以外は無効 | `1`, `10`, `1anything` | `0`, `true`, ` 1`, `anything` |
| HIP gfx906 build | 無効 | `1`, `10`, `1anything` | `0`, `true`, ` 1`, `anything` |
| SYCL build | V2K は無効。注記は出さない | 先頭が `1` のとき注記のみ | `0`, `true`, 空文字列などは注記なし |

大文字小文字は先頭文字 `'1'` との比較に関係せず、`true` / `TRUE` はどちらも無効です。負数、空白、末尾の文字も parse されず、先頭が `1` かどうかだけで決まります。SYCL では同様の先頭文字判定をログ条件にだけ使います（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7783-7788`）。

HIP の未設定時は device query の成功と GPU 名判定が必要です。Windows gfx1151 はこの自動判定に含まれますが、gfx906 はコンパイル条件で自動判定コード自体を通りません。CUDA は明示的な値がない場合 `false` です（`engine/src/kernels/cuda/iq_kernels.cu:7141-7157`）。

エンジン起動時の arch defaults は別途、非 integrated の discrete RDNA3 gfx1100 / gfx1101 / gfx1102 で本変数を `1` に設定します。ただし `STRATA_GFX11_DEFAULTS=0` または `STRATA_DEFAULTS=026` によりこの default list が空になり得ます。すでに環境に変数があれば値が何であっても上書きしません。ここで空文字が設定済みなら `1` は注入されず、後の HIP 判定では空文字扱いで GPU 自動判定に進みます（`engine/include/strata/core/gfx11_extra.hpp:27-45,61-63`; `engine/src/core/arch_defaults.cpp:302-323`; `engine/src/program/generate.cpp:4320`）。

## 有効になる条件

- CUDA/HIP の `native_expert_grouped` が呼ばれ、`cap_groups > 0`、`cap_entries > 0` であること。該当値が 0 以下なら、環境判定より前に関数が戻ります（`engine/src/kernels/cuda/iq_kernels.cu:7085-7089`）。
- Blackwell NVFP4 grouped decode が先に成功して戻る場合は V2K 判定へ到達しません（`engine/src/kernels/cuda/iq_kernels.cu:7092-7102`）。
- `STRATA_EXPERT_V2=1` による S26 分岐が該当レイアウトで先に選ばれた場合は、その場で戻り、V2K 分岐には進みません（`engine/src/kernels/cuda/iq_kernels.cu:7121-7132`）。
- V2K の CUDA/HIP 分岐では `L.had_block == 0`、`L.tail_off == 0`、gate/up が Q4_K (`12`) または Q5_K (`13`) であることが必要です。down が Q5_1 (`7`) または Q8_0 (`8`) で形状が `n_embd=2560, n_ff=640`、または Qwen3.6 用に `n_embd=2048, n_ff=512, d_type=13` であることも必要です。モデルが別形式・形状なら値が有効でもこの分岐は使われません（同 `:7159-7182`）。
- `STRATA_TSUM=1` の場合は V2K 内で `s27_launch_ts` による transposed-sum variant を選び、それ以外では通常の `s27_launch` を使います（同 `:7163-7179`）。
- SYCL では S27 カーネルはこの実装に含まれず、変数は無視されます。値の先頭が `1` の場合に限り、その旨の note が出ます（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7782-7788`）。

## 実行時の詳細

CUDA/HIP の値判定は `native_expert_grouped` の関数内 static local `v2k` の初期化時に一度行われ、以後そのプロセス内でキャッシュされます。最初の grouped expert 呼び出しでも、冒頭の早期 return、NVFP4 の成功 return、または S26 の成功 return があれば初期化は遅れます。その初期化後にプロセス環境を変更しても判定値は更新されません（`engine/src/kernels/cuda/iq_kernels.cu:7085-7102,7121-7158`）。

未設定時の HIP 判定は `cudaGetDevice` と `cudaGetDeviceProperties` の成功後に arch 名を調べます。Windows では gfx1151 も自動 on です。query 後に `cudaGetLastError()` を呼びます。明示的な空でない値があれば、GPU query をせず先頭文字の判定結果を使います（同 `:7138-7157`）。

V2K が選ばれると、2560/640 の対象形状では `s27_launch_ts` が選ばれた format の grouped gate/up と down を実行します。Qwen3.6 形状では S27 gate/up、S26 SwiGLU/q8_1、従来の Q5_K down を順に実行します。完了後 `check("native_expert_grouped (v2k)")` を通って戻ります（同 `:7161-7182`）。CUDA/HIP のこの場所では、変数の値を理由にしたログや無効値警告はありません。

## ログと測定値

SYCL の grouped expert 呼び出しで `STRATA_EXPERT_V2K` または `STRATA_EXPERT_V2` の先頭文字が `1` なら、stderr に次の文字列を出します（後ろに改行あり）。この static 初期化の後に環境値を変えても再評価されません。

```text
note: STRATA_EXPERT_V2 / STRATA_EXPERT_V2K are AMD-only experiments, ignored on SYCL
```

`docs/SETTINGS.md:73` は Intel Arc も対応対象として列挙していますが、SYCL ソースで確認できる本変数の動作は上記 note のみで、V2K は「not built here」と明記されています。従って Intel Arc でカーネル選択を切り替える設定としては機能しません（`engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7782-7788`）。`docs/QUANTS.md:37-41` も SYCL 欄では対象カーネルを「kernels built, not run with these files」としています。

測定の再実行はしていません。CUDA ソースのコメントは gfx1201 の Radeon AI PRO R9700、UD-Q4_K_XL での decode を 5 組の交互比較として記録し、story +1.2% (5/5)、code +0.8% (5/5)、after 6K +0.2% (4/5) としています。また Windows gfx1151 の Strix Halo、UD-Q4_K_XL、DFlash2 serve で 16 request pairs 中 16 組が速く、window time -4.0%（平均 x1.040、範囲 x1.020-1.056）と記載しています。いずれもソースコメント上の報告であり、他の GPU への一般化はできません（`engine/src/kernels/cuda/iq_kernels.cu:7135-7149`）。`docs/QWEN36.md:121-127` は R9700 / HIP gfx1201 / UD-Q4_K_XL / 5 interleaved pairs のエンジン全体の比較値を示しますが、V2K 単独の効果量としては扱いません。

## 根拠

- 候補名の全参照を検索し、実際の環境読み取りは CUDA/HIP 実装の `engine/src/kernels/cuda/iq_kernels.cu:7138-7158` と、SYCL 注記の `engine/sycl/src/kernels/cuda/iq_kernels.dp.cpp:7783-7788` に確認しました。その他の参照はコメント、arch default list、設定 register、テスト設定・ケース、または SYCL fixup コメントです。
- V2K カーネルと実装意図: `engine/src/kernels/cuda/iq_kernels.cu:4157-4162,7161-7182`。
- arch defaults の対象と stderr 表示: `engine/include/strata/core/gfx11_extra.hpp:27-45,61-63`; `engine/src/core/arch_defaults.cpp:302-332`; 呼び出し元 `engine/src/program/generate.cpp:4320`。
- synthetic parity harness の対象形状と比較経路（本調査では実行していない）: `engine/src/kernels/iq_multi_parity.cpp:442-446`; CMake で `STRATA_EXPERT_V2K=0` の variant を指定する箇所: `engine/cmake/strata_gpu_engine.cmake:856-860`。
- 設定一覧との照合: `docs/SETTINGS.md:73`; backend 表: `docs/QUANTS.md:35-41`; Qwen3.6 の説明と計測条件: `docs/QWEN36.md:115-127`。
