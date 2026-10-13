# `STRATA_PROMPT_ATTN_XMX`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。調査対象リポジトリは調査時点で `main`、作業ツリーは clean。

## 役割

SYCL 版の QSA プロンプト attention で、Intel XMX 向け `joint_matrix` カーネルを試すための opt-in 変数。通常の attention 処理の代わりに、クエリ位置と KV head ごとに選択済み KV cell の K/V を集め、スコア計算と出力更新を行う。無効または対象外の入力ではこのカーネルは何も launch せず、呼び出し側の既存経路に処理を戻す。CUDA/HIP 版の選択変数ではない。

## 値と判定

カーネル関数の最初の呼び出しで `std::getenv` の結果を `std::atoi` に渡し、その整数を関数内の `static const int mode` に保存する。環境変数を設定したかどうかだけではなく、`atoi` の結果が 0 かどうかで有効性を判定する。

| 設定値 | `atoi` の結果と処理 |
| --- | --- |
| 未設定 | `mode = 0`。無効。 |
| 空文字 | 0。無効。 |
| `0`、または空白・符号の後に変換可能な10進数字がない文字列 | 0。無効。 |
| `1` | 0以外。64-cell chunk を優先し、必要なローカルメモリがなければ32-cell chunkを選ぶ。 |
| `32` | 32-cell chunkを選ぶ。64-cell用メモリがあっても32-cellを使う。 |
| その他の `atoi` 結果 | 0以外なら `32` と同様の特別扱いを除き64-cellを優先する。64-cell用メモリが不足すれば32-cellへ下げる。 |

`atoi` は文字列全体の厳密な数値検証ではないため、先頭に変換可能な整数がある場合は後続文字列の有無で拒否しない（例: `32xyz` は32として扱われる）。空白や符号の後に変換可能な10進数字がない文字列は0となる。範囲外の値について、コードはエラー検査や独自の fallback を設けていない。

## 有効になる条件

- この実装は `sycl/CMakeLists.txt` が `qsa_prompt_attn_xmx.dp.cpp` をカーネルライブラリに追加する SYCL port のもの。CUDA/HIP の attention 実装にはこの変数による分岐はない。
- `mode != 0` かつ `n_q > 0` が必要。
- `k_q4`（Q4_0 K/V pool）がないこと、head dimension が256であること、`n_head == 12 * n_head_kv`、`cap > 0`、`ids`、`steps`、`page_table` が有効であることが必要。条件を満たさなければ `false` を返す。
- 64-cell用ローカルメモリが足りず、32-cell用も足りない場合も `false` を返す。64-cell用が不足していて32-cell用が足りるときは32-cellで実行する。
- `dispatch` は KV pool の実体に応じて、通常の FP16 K/V、INT8 K/Vとscale、または INT8 K + Q4_0 V（hybrid）を選ぶ。必要な pool/scale が欠ける場合は `false`。Q4_0 K/Vは先行条件で対象外。
- 実行コードには、関数内で XMX 対応 GPU の型番や世代を確認する明示的な分岐はない。SYCL の `joint_matrix` を使う実装であり、実行可能なデバイス条件はこの分岐だけからは確定できない。

## 実行時の詳細

`qsa_prompt_attn_batch` の SYCL 分岐から本関数が呼ばれる。変数が0、または上記の形状・pool・メモリ条件を満たさないときは `false` が返り、プロンプト処理側は `qsa_decode_attn_batch` を使う既存 fallback に進む。`STRATA_PROMPT_ATTN_OLD` が設定されている場合はプロンプト側で `qsa_prompt_attn_batch` 自体を呼ばず、同じ fallback を使う。

有効な場合、関数はデバイスの `local_mem_size` を調べて chunk 幅を決め、`joint_matrix` カーネルを submit する。XMX カーネルは16 lane の sub-group を要求する。初めて有効候補として実行経路に入った時に、stderr に次の形式で選択したchunk幅とローカルメモリ量を一度出す（32-cell用メモリも不足するケースでは、このログの後に `false` が返る）。

```text
strata: prompt attention on XMX, <32 または 64>-cell chunks (<必要bytes> of <利用可能bytes> bytes of local memory)
```

`mode` は関数内 `static const` なので、値はプロセス内の初回呼び出しで読み込まれて以後固定される。初回に無効値が読み込まれた場合、プロセス稼働中に環境変数を変更してもこの関数では反映されない。なお、プロンプト呼び出しがなく関数が一度も呼ばれなければ読み取りも起きない。

## 文書との照合

`docs/INTEL.md` は64-cellと32-cellを選べる opt-in と説明しており、カーネル側の分岐と一致する。同資料は XMX v2 が既存の FP32 fallback より遅く、32K context の INT8 で1 chunk当たり13.4 ms対5.5 msだったと記す。また、同資料の冒頭にある測定対象は Arc Pro B70 (32 GB)、Ubuntu 24.04 とされている。これらは資料記載の測定値であり、この調査で再測定したものではない。資料は長いプロンプトでの全体性能も悪化したとし、Q4_0 KVはXMXカーネルを使用しないと記載している。

## 根拠

- `sycl/src/kernels/cuda/qsa_prompt_attn_xmx.dp.cpp:364-384` — `getenv` / `atoi`、static cache、shape/pool条件、ローカルメモリによるchunk選択、ログとfallback。
- `sycl/src/kernels/cuda/qsa_prompt_attn_xmx.dp.cpp:324-360` — カーネル起動とFP16 / INT8 / hybrid KV poolのdispatch。
- `sycl/src/kernels/cuda/qsa_prompt_attn_xmx.dp.cpp:338-342` — 16 lane sub-groupを指定したSYCL kernelのsubmit。
- `sycl/src/kernels/cuda/qsa_prompt_attn.dp.cpp:1968-2010` — SYCL側の `qsa_prompt_attn_batch` からの呼び出しと、XMXが処理しない場合の戻り。
- `sycl/src/prefill/prefill.cpp:3160-3164, 3184-3191` — 旧 attention 選択と、batch kernelがfalseのときに使う decode attention fallback。
- `sycl/CMakeLists.txt:205-216` — SYCL kernel libraryへの当該ソースの追加。
- `docs/INTEL.md:1-10, 362-375` — 対象ハードウェアの記載、chunk設定、測定値と全体性能についての説明。
