# `STRATA_QSA_SLOTS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

batch window の QSA decode で、別 slot の行をまとめて処理する slot launcher を選ぶスイッチ。ON の経路では、各行が自分の slot の indexer keys と K/V pool を読み、block scores・top-k・attention を最大 8 行ずつまとめて投入する。OFF または適用外の経路は従来の per-row / per-slot 呼び出しを使う。ソースコメントは各行で同じ arithmetic と説明しているが、この調査では実行による同一性確認はしていない（`engine/src/core/verify.cpp:359-364,2470-2532`）。

## 値と判定

engine の `env_on` は `getenv` の結果が存在し、空文字でなく、先頭文字が `0` でない場合に true を返す。文字列全体の数値変換・比較はせず、大文字小文字や後続文字を検証しない（`engine/src/core/verify.cpp:336-339,363`）。

| engine 起動前の値 | 判定 | 補足 |
|---|---|---|
| 未設定 | 通常は OFF | ただし下記の platform default / setup profile が未設定の場合に `1` を補う |
| 空文字 | OFF | `getenv` は非 null だが `e[0] == 0` |
| `0`, `0anything`, `00` | OFF | 先頭文字が `0` なら後ろを問わず false |
| `1`, `true`, `false`, `yes`, `abc`, ` 0` | ON | 空でなく先頭文字が `0` 以外なら true。数値妥当性、空白除去、大小文字変換なし |

platform default は値の parse より先に環境へ設定する。default 適用時は `getenv(name) != nullptr` だけで「利用者が設定済み」と判定するため、空文字や `0` も保持されて既定値 `1` で上書きされない（`engine/src/core/arch_defaults.cpp:218-223,253-260,346-350`）。

## 有効になる条件

- 値が ON で、QSA 層を処理する verifier の `batch_rec_` 経路に入ること。`batch_rec_` でない通常経路は対象外。一行だけの batch window でも分岐は可能だが、複数 slot をまとめる効果はない（`engine/src/core/verify.cpp:2470-2473`）。
- この変数を直接設定する engine CLI 引数はない。`--batch` / `--slots` は上記 platform default の条件となるが、すでに環境変数が設定されていればその値（空文字や `0` を含む）が優先される（`engine/src/core/arch_defaults.cpp:248-260,346-350`; `engine/src/program/generate.cpp:4410-4414`）。
- `STRATA_BATCH_QSA_STREAM_OPT` の適用経路が先に選ばれず、`STRATA_BATCH_ATTN_ROWS` による `rows_ok` 経路にも入らないこと。後者は batch recording、stream optimization 無効、row 数上限内、全行が resident KV の場合に先行する（`engine/src/core/verify.cpp:2191-2200,2449-2470`）。
- streamed KV（`kv_mode == 1`）で、より先行する stream optimization が成立しない場合は `streamed` が立ち、このスイッチの slot 分岐は使わず per-slot の resolve・attention 経路に進む。コメントも streamed KV では row ごとの resolve-then-attend 順序を保つとしている（`engine/src/core/verify.cpp:2191-2193,2470-2473,2534-2562`）。
- platform default は以下の条件に限られる。いずれも対象変数が未設定のときだけ設定する。
  - Linux CUDA build（`STRATA_USE_HIP`、`STRATA_HIP_GFX906`、`STRATA_GPU_METAL`、`_WIN32` のいずれも定義されない）かつ `o.batch >= 2`: engine が並列 stack の一部として `STRATA_QSA_SLOTS=1` を設定する（`engine/src/program/generate.cpp:4410-4414`, `engine/src/core/arch_defaults.cpp:226-260`）。
  - discrete RDNA3 `gfx1100/1101/1102` かつ `batch_slots >= 2`、GPU が integrated 扱いでなく、`STRATA_GFX11_DEFAULTS=0` でも `STRATA_DEFAULTS=026` でもない場合: `apply_arch_defaults` が `1` を設定する（`engine/include/strata/core/gfx11_extra.hpp:4-12,116-136`, `engine/src/core/arch_defaults.cpp:312-358`）。
  - Windows `gfx1151` かつ `batch_slots >= 2`、`STRATA_GFX1151_DEFAULTS` の先頭が `0` でない場合: parallel stack の一部として `1` を設定する。CUDA/HIP のいずれかの GPU engine で arch defaults が呼ばれる経路（`engine/src/core/arch_defaults.cpp:240-246,433-443`; 呼び出し例 `engine/src/program/generate.cpp:4320`）。
- Terminal setup の profile も engine 用 config の `env` に `1` を補う。四枚の AMD Radeon AI PRO R9700 / HIP / Qwen3.8 IQ3_S の profile は、`amd_four_card.applies` の条件に合い profile が無効化されていない場合に追加し、プロセス環境に利用者自身の値があれば保持する（`terminal/strata_control/amd_four_card.py:27,34-61,82-91`; 適用呼び出し `terminal/strata_control/setup_config.py:501-508`）。opt-in replica profile も、対象モデル・カード・RAM 等の条件を満たして適用されたとき、同じく利用者環境に名前がなければ config env に `1` を補う（`terminal/strata_control/replica_profile.py:37-39,77-99,118-122`; 呼び出し `terminal/strata_control/setup_config.py:487-500`）。
- Metal の slot launcher は false を返す実装なので、環境値が ON でも verifier は per-row 呼び出しへ戻る。slot kernel のない Metal ではこの変数だけで一括 kernel が利用可能にはならない（`engine/metal/src/engine/stubs_144.cpp:57-63`; fallback `engine/src/core/verify.cpp:2515-2532`）。

## 実行時の詳細

`qsa_slots_on()` は関数内 `static const bool` に最初の呼び出し時点の判定を保存し、`g_qsa_slots` はそれを参照する。したがって process start 時に固定されるのではなく、最初にこの関数へ到達するまでに platform default が設定されていればその値を読み、以後の環境変更は反映されない。Linux CUDA の `apply_parallel_defaults_cuda` は `generate.cpp` から engine の switch 読み取り前に呼ばれる旨が記されている（`engine/src/core/verify.cpp:355-364`, `engine/src/program/generate.cpp:4410-4414`, `engine/include/strata/core/arch_defaults.hpp:126-134`）。

対象の batch 分岐では、window の行を `kQsaAttnMaxSlots`（8）単位に分割し、各 chunk について slot ごとの indexer buffers と attention pools を渡す。scores slot launcher が `false` を返すと各行の `qsa_block_scores` に戻し、top-k はまとめて実行する。attention slot launcher が `false` を返した場合も各行の `qsa_decode_attn_batch` に戻る。QSA の score/attention 計算と出力先は各行ごとに保たれる（`engine/src/core/verify.cpp:2232-2250,2485-2532`）。

score launcher は `STRATA_SCORES_MULTI` を `atoi` し、未設定なら ON、変換値が `0` なら multi scorer 無効として `false` を返す。さらに行数が上限を超えた場合も辞退する（`engine/src/kernels/cuda/qsa_select.cu:1607-1610,1997-2015`）。attention launcher は slot 数超過、KV mode の不一致、build に pre-sm_75 kernel がありその経路を使うとき `STRATA_ATTN_PRE75_SLOTS` が `atoi` で 0 となる場合、または HIP gfx906 の query-swizzle / streamed KV 条件などで `false` を返す場合がある（`engine/src/kernels/cuda/qsa_decode_attn.cu:978-985,1150-1179`）。通常の decline は上記の per-row fallback で処理される。未対応 geometry や必要 buffer/page table の欠落、CUDA launch error は同関数が stderr に `qsa_block_scores_slots: unsupported indexer geometry`, `qsa_block_scores_slots: %s`, `qsa_decode_attn_slots: unsupported geometry or missing buffers`, `qsa_decode_attn_slots: missing page table`, `qsa_decode_attn_slots: %s` を出して `exit(1)` する経路であり、環境値の無効値エラーではない（`engine/src/kernels/cuda/qsa_select.cu:2001-2015`, `engine/src/kernels/cuda/qsa_decode_attn.cu:1154-1162,1221-1223`）。

## ログと測定値

RDNA3 / Windows gfx1151 の platform default がこの名前を補った場合、並列 switch 一覧の起動ログに `QSA_SLOTS`（`STRATA_` を除いた名前）が含まれる。Linux CUDA の parallel defaults は無言で適用される。既に環境変数があれば RDNA3 / gfx1151 の default 設定ログには含まれず、QSA の runtime 分岐自体は有効・無効を示すログを出さない（`engine/src/core/arch_defaults.cpp:253-260,346-356,438-442`; `engine/include/strata/core/arch_defaults.hpp:126-134`）。launcher decline 時もこの変数名を含む runtime log はなく、per-row fallback へ進む。

`docs/BATCHING.md:115-128` は batch switch を「none is on by default」とし、同書の `:598-608` は four-R9700 profile でこの変数を含む 3 switch の組み合わせについて aggregate throughput を記す。現行ソースには上記の engine platform defaults があるため、「既定で ON/OFF」は構成依存である。また同測定は 3 switch 一括の比較で、QSA_SLOTS 単独の寄与を分離していないため、本書では単独の性能値として扱わない。

## 根拠

- 読み取り・値判定・cache: `engine/src/core/verify.cpp:336-339,359-364`
- batch 分岐・streaming / rows との優先関係・fallback: `engine/src/core/verify.cpp:2191-2200,2232-2250,2449-2534`
- platform defaults: `engine/src/core/arch_defaults.cpp:218-260,312-358,433-443`; `engine/include/strata/core/gfx11_extra.hpp:116-136`; `engine/src/program/generate.cpp:4320,4410-4414`
- kernel decline / error paths: `engine/src/kernels/cuda/qsa_select.cu:1997-2015`; `engine/src/kernels/cuda/qsa_decode_attn.cu:1150-1179,1221-1223`; Metal stubs `engine/metal/src/engine/stubs_144.cpp:57-63`
- setup profiles: `terminal/strata_control/amd_four_card.py:27,34-61,82-91`; `terminal/strata_control/replica_profile.py:37-39,77-99,118-122`; `terminal/strata_control/setup_config.py:487-508`
- 関連資料（測定の独立性を確認）: `docs/BATCHING.md:115-128,598-608`
