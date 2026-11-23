# `STRATA_BATCH_MTP_ATTN_SLOTS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`STRATA_BATCH_MTP_FUSED` による複数 slot の MTP 融合処理で、slot 間の attention をまとめて計算するための GPU scratch 領域を確保するか選びます。設定値が非ゼロなら確保を要求し、`0` 相当なら確保しません。未設定または空文字の場合は必要量が 32 MiB 以下のときだけ確保します（`engine/src/core/mtp.cpp:2275-2288`）。

scratch があると `qsa_decode_attn_slots` を試し、使えない場合や別条件で選べない場合は slot ごとの attention 計算へ進みます。したがって、この変数は attention のバッチ化と一時 GPU メモリ量を選ぶもので、draft token の個数や選択値を直接指定しません（`engine/src/core/mtp.cpp:2481-2499`）。

## 値と判定

`ensure_batch_mtp_buffers` の初回実行時に `std::getenv` で読み、空文字以外は `std::atoi` で変換します。文字列全体の妥当性検査はなく、`atoi` の結果が非ゼロかだけで判定します（`engine/src/core/mtp.cpp:2284-2288`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `STRATA_GPU_METAL` 以外で融合 MTP バッファを初期化する経路 | scratch 必要量が 32 MiB 以下なら確保、超えるなら確保しない | `atoi` が非ゼロ（例: `1`, `-1`, `2`, `1abc`）なら確保を要求 | `atoi` が 0（例: `0`, `0anything`, `true`, `false`, 空白だけ）なら確保しない |
| Metal | この融合 slot 経路は使われない | 該当なし | 該当なし |

空文字は unset と同じ既定判定です。`atoi` のため先頭空白や符号を含む数値は変換され、数値の後ろに文字があっても数値部分で判定されます。`true` / `false` などは整数として読めず 0 になります。数値として変換可能かを別途検査したり、値の範囲を制限したりする処理はありません（`engine/src/core/mtp.cpp:2284-2288`）。

unset の閾値計算は `attn_bytes = cap_m * attn_scratch_floats_ * sizeof(float)` です。`cap_m` は `max_t_`, `kFusedGrMaxT`, `kQsaAttnMaxSlots`, `8` の最小値です。値を非ゼロにすると閾値を超えても scratch を含めますが、後述の GPU arena 確保が失敗すれば融合 MTP 呼び出しはエラーになります（`engine/src/core/mtp.cpp:2277-2288,2329-2347`）。

## 有効になる条件

- バッチ MTP が有効である必要があります。CLI `--batch-mtp` または `STRATA_BATCH_MTP` がその入口で、さらに `--batch >= 2`、`--mtp`、`--spec T`（`T >= 2`）、`--serve` などの条件があります。条件を満たさないと `strata generate: WARNING: ... is off: ...` を出して batch MTP を無効にします（`engine/src/program/generate.cpp:7770-7802`）。
- 融合経路には別途 `STRATA_BATCH_MTP_FUSED` が空でなく先頭文字が `0` 以外であることが必要です。実際に試す条件は `batch_mtp && !batch_df2 && stages.empty()` です（`engine/src/program/generate.cpp:17186-17192`）。
- 少なくとも 2 slot 分をまとめられ、`MtpDrafter::can_draft_slots` の前提を満たす必要があります。Metal はここで常に不可となり、slot 数、モデル・weight/head、device、KV 状態などの条件が合わない場合も融合 MTP を使いません（`engine/src/core/mtp.cpp:2244-2272`, `engine/src/program/generate.cpp:17323-17344`）。
- この変数が scratch を要求しても、`STRATA_QSA_SPLIT_ATTN` が非ゼロなら fused attention 関数を呼ばず slot ごとの経路へ進みます。また `qsa_decode_attn_slots` がサポート外として `false` を返す場合も同じ fallback です（`engine/src/core/mtp.cpp:2485-2499`）。
- unset 時は必要量が 32 MiB を超えると scratch がなく、slot ごとの attention 計算を使います。明示的な非ゼロ値はこのサイズ判定を上書きしますが、GPU メモリ不足を回避するものではありません（`engine/src/core/mtp.cpp:2283-2288,2329-2337`）。

## 実行時の詳細

融合 MTP は batch loop 内で `STRATA_BATCH_MTP_FUSED` を関数内 `static` に読み、対象 slot の候補を集めてから `draft_slots` を呼びます。attention slot scratch の環境変数は、最初の `ensure_batch_mtp_buffers` 呼び出しで関数内 `static` に読み込まれます。そのためプロセス起動後でも最初の読み取り前の変更は反映されますが、読み取り後の変更は反映されません。値はプロセス内で共有され、各 drafter の buffer arena は `bm_ready_` により一度だけ準備されます（`engine/src/program/generate.cpp:17188-17192,17306-17325`; `engine/src/core/mtp.cpp:2275-2288`）。

scratch が確保され、`STRATA_QSA_SPLIT_ATTN` が無効なら、`qsa_decode_attn_slots` が全 slot をまとめて処理します。同関数は query 数上限、attention geometry、page table、KV mode、ビルド済み pre-75 経路などによって `false` を返すことがあります。`false` の場合は `attn_scratch_` を使う per-slot の split または batch attention に切り替わります（`engine/src/kernels/cuda/qsa_decode_attn.cu:1150-1178`; `engine/src/core/mtp.cpp:2481-2499`）。

GPU arena の `cudaMalloc` に失敗すると `ensure_batch_mtp_buffers` は `mtp batch: staging buffers do not fit` を返します。呼び出し側は `ERR batch MTP fused: ...` を stdout に出して処理を失敗終了します。この経路では scratch なしの slot ごとの attention へ fallback しません。融合対象の前提が満たされない場合には `draft_slots` を呼ばず、従来の slot ごとの drafter を使います（`engine/src/core/mtp.cpp:2331-2337,2735-2747`; `engine/src/program/generate.cpp:17323-17344`）。

## ログと測定値

環境変数の値そのものに対する警告や parse error はありません。バッファ確保が成功すると stderr に `strata mtp: STRATA_BATCH_MTP_FUSED=1 active (chunk_cap=..., staging ... MiB, attn_slots=on)` または `attn_slots=per-row` を出し、選択結果を示します（`engine/src/core/mtp.cpp:2343-2348`）。

融合呼び出しが失敗した場合は stdout に `ERR batch MTP fused: <error>` が出ます。CUDA attention kernel の launch error は stderr に `qsa_decode_attn_slots: <CUDA error>` を出して `exit(1)` します（`engine/src/program/generate.cpp:17323-17327`; `engine/src/kernels/cuda/qsa_decode_attn.cu:1217-1223`）。

この変数による速度・精度・token 同一性の測定値は、調査対象ソースおよび確認した `docs/DETAILS.md` に記載を確認できませんでした。

## 根拠

- 読み取り、unset 時の 32 MiB 判定、確保・ログ: `engine/src/core/mtp.cpp:2275-2288,2329-2348`
- slot attention の融合と fallback: `engine/src/core/mtp.cpp:2481-2499`
- バッチ MTP の起動条件と融合経路: `engine/src/program/generate.cpp:7770-7802,17186-17192,17306-17344`
- attention slot kernel の返却条件と launch error: `engine/src/kernels/cuda/qsa_decode_attn.cu:1150-1178,1217-1223`
