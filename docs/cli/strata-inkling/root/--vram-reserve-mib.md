# `strata-inkling --vram-reserve-mib`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root） |
| オプション | `--vram-reserve-mib` |
| 別名 | なし |
| 値 | 整数 MiB。数値検証や明示的な範囲制限はない |

## 役割

CUDA backend がモデル初期化時に確保する VRAM のうち、KV・workspace などのために残す最低量を増やす。これにより expert の VRAM 常駐予算が小さくなり、収まらない expert は host 側に置かれる。host 側 expert が発生しても、CPU hybrid doorbell を使うには別途 `--cpu-threads` を正数で指定する必要がある。

## 使い方

```sh
# CUDA で benchmark し、CUDA backend の最低 VRAM 予約量を 2048 MiB にする
strata-inkling --bench --native ./model.strata --vram-reserve-mib 2048
```

## 値と既定値

- 値は `std::atoi` で整数に変換される。省略時の `BackendOpts::vram_reserve_mib` は `-1`。
- CUDA backend では `-1` など負数は明示予約なしとして扱い、既定の KV・workspace 見積もりを使う。0 以上なら指定 MiB を最低予約量に加味する。
- parser に範囲検証はない。空文字列や整数に変換できない文字列は `atoi` により 0 となり、数値の後ろに変換不能な文字がある場合は変換できた先頭部分が使われる。値を省略すると `missing value after --vram-reserve-mib` を stderr に出して終了コード 2 で終了する。
- 同じ引数を複数回指定すると parser の逐次代入により最後の値が残る。

## 実行時の動作

parser は `cfg.bopts.vram_reserve_mib` に値を設定する。CUDA backend はまず slot 数、KV 構成、context、workspace などから `min_reserve_bytes` を算出し、指定値が 0 以上なら `max(算出値, 指定 MiB)` をモデルローダーへ渡す。この予約量は expert の常駐領域と競合し、VRAM に収まらない expert は host 側へ回る。

EP の dual-GPU 配置では、GPU0 の expert budget から、指定値が 0 以上なら `指定 MiB + 512 MiB`、未指定または負数なら `1536 MiB` を差し引く。GPU1 はこのオプション値ではなく固定の `768 MiB` を差し引く。さらに単一 GPU で `--vram-experts-gb` も指定した場合、その上限との小さい方が GPU0 の expert budget になる。

オプションは root parser が受理するが、`--info` と `--export-tokenizer` は backend 初期化より前に処理を終えるため、この値はそれらの処理に影響しない。backend を初期化する benchmark、serve、通常生成などでは、選択された backend が値を参照する場合に効果がある。

## 適用条件と副作用

- 調査した checkout では、値を VRAM 予約量へ反映する実装は CUDA backend（`engine/src/inkling2/cuda/ink_cuda_backend.cu`）と CUDA EP 配置（`engine/src/inkling2/ep_dual_gpu.cu`）で確認できた。HIP、Metal、SYCL backend にこの値を使う実装は確認できず、これらでの効果は確認できない。
- 予約を増やすと expert の VRAM 常駐数を減らす可能性がある。未常駐 expert は host storage に配置される。CPU doorbell offload の有効条件は単一 GPU、host expert が 1 件以上、かつ `--cpu-threads > 0` のすべてを満たすこと。
- モデル読込時の GPU メモリ予算にだけ関わる。ファイル変更やネットワークアクセスはこのオプションからは発生しない。

## 出力とエラー

- オプション値そのものに対する専用の validation error はない。
- backend 初期化失敗時は `init: <原因>` を stderr に出して終了コード 1 で終了する（serve モードではプロトコル形式の `ERR init: <原因>`）。GPU の空き容量やモデル条件により、失敗内容は異なる。
- 通常の初期化成功時、CUDA EP 配置は VRAM / host expert 数と doorbell 状態を stderr の `[inkling2-ep] Loaded ...` 行に出力する。

## 根拠

- `engine/src/inkling2/ink_main.cpp:379-383,439-440` — root 引数 parser。値を `atoi` で読み、値欠落時は stderr に出して終了コード 2。
- `engine/src/inkling2/ink_main.cpp:488-501` — help、未知オプション時の出力と終了コード。
- `engine/src/inkling2/ink_main.cpp:544-568,571-579` — info/export の早期処理と、backend 初期化・失敗時の出力。
- `engine/src/inkling2/ink_backend.h:17-30` — `BackendOpts` の既定値。`vram_reserve_mib = -1`、CPU threads は 0。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:146-199` — CUDA backend の必要予約量を計算し、指定 MiB を最低値としてモデルローダーへ渡す。
- `engine/src/inkling2/ep_dual_gpu.cu:913-924,934-958` — GPU ごとの expert 予算と、VRAM に入らない expert の計上。
- `engine/src/inkling2/ep_dual_gpu.cu:970-972,1037-1068` — host expert 配置、doorbell の有効条件、初期化結果の stderr 出力。
- `docs/cli/README.md:1509-1547` — `strata-inkling` root scope と対象リンクの確認（索引。実装根拠ではない）。

調査範囲は上記 parser と Inkling-2 backend 実装。非 CUDA backend の受理後の処理、および実機ごとのメモリ確保成否はソース確認だけでは確定できないため、効果を断定していない。
