# `STRATA_KV_GROW`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata generate` の伸縮 K/V を要求する環境変数。K/V の物理メモリを `--max-context` 全量で初期確保せず、要求が使う cell まで伸ばす機能である。伸長時は条件がそろえば expert cache の slot を K/V に渡し、渡せない場合は CUDA/HIP 系では新しい VRAM だけで伸ばす。GPU の expert cache と K/V の間で使える VRAM の割当が変わるが、最大 context 自体は縮めない（`engine/src/program/generate.cpp:7715-7732, 11520-11540, 11563-11674`、`engine/src/core/kv_grow_rules.hpp:3-10, 26-36`）。

環境変数は engine 初期化時に一度読み、成立条件を満たすと `qsa_set_kv_elastic` と `ExpertCache::set_vmm` に反映する。以降の prompt、window、conversation restore で必要 cell 数に応じて伸長処理が呼ばれる。値の変更を実行中に再読する箇所はない（`engine/src/program/generate.cpp:7718-7732, 18767-18770, 19233-19240, 22975-22980`）。

## 値と判定

`getenv` の結果が未設定または空文字なら `--kv-grow` / `--no-kv-grow` の parse 結果を使う。非空なら先頭文字だけを見て、`0` なら無効、それ以外なら有効とする。文字列全体の数値 parse、空白除去、大文字小文字変換、真偽語の検査はない。従って `1`, `true`, `false`, `x`, ` 0` は有効、`0`, `0anything`, `00` は無効、空文字は CLI の値に戻る。非空値は CLI より優先し、例えば `STRATA_KV_GROW=0` は `--kv-grow` を打ち消し、`STRATA_KV_GROW=1` は `--no-kv-grow` を打ち消す（`engine/src/program/generate.cpp:3908-3909, 7718-7722`、同 SYCL 版 `engine/sycl/src/program/generate.cpp:1947-1948, 4285-4289`）。

| 経路 | 未設定・空文字 | 非空で有効 | 非空で無効 |
|---|---|---|---|
| CUDA/HIP 系 `engine/src/program/generate.cpp` | CLI の既定値は off。`--kv-grow` で on、`--no-kv-grow` で off | 先頭文字が `0` 以外 | 先頭文字が `0` |
| SYCL `engine/sycl/src/program/generate.cpp` | 同じく CLI の既定値は off | 先頭文字が `0` 以外 | 先頭文字が `0` |

## 有効になる条件

- 共通の CUDA/HIP 系では `asked` が true で、単一 GPU、`--kv-resident` が 0 以下、`--expert-profile` が指定済み、`--resident-cpu-experts` でなく、expert cache が無効でなく、remote expert cache がなく、VMM が利用可能、`--batch 0`、`--vram-elastic` なし、`--peer-device` なしの場合に engine の伸縮 K/V を有効にする。条件不足なら要求値が有効でも無効になる（`engine/src/program/generate.cpp:7718-7729`）。
- CUDA/HIP 系で VMM が有効でも、expert cache から slot を受け取れるかは別判定である。CUDA の `kv_grow_start` は VMM range、residency 表、expert source、cache floor より上の slot が揃わない場合も K/V の伸長を有効のままにし、新しい VRAM だけで伸ばす（`engine/src/program/generate.cpp:11541-11553`、`engine/src/core/kv_grow_rules.hpp:23-31`）。
- HIP の VMM はデバイスが VMM を報告し、かつ `STRATA_HIP_VMM` の先頭文字が `0` でない場合に利用可能となる。`STRATA_HIP_VMM=0` ならこの変数を on にしてもゲートで無効となる（`engine/src/core/vmm.cpp:154-167, 188-209`）。CUDA 側も VMM API と device attribute の利用可否を確認する（同 `:25-56`）。
- SYCL も同じ `asked` と主な単一 GPU / profile / resident experts / cache / VMM / batch / peer 条件で初期化する（`engine/sycl/src/program/generate.cpp:4285-4299`）。ただし SYCL の `kvg_start` はさらに expert cache の VMM range、device residency 表、host residency、expert source、floor より上の slot を要求し、どれかがなければ `kvg.on` にしない（同 `:6791-6805`）。
- SYCL では `--kv-grow` CLI フラグが false のとき、環境変数を読む前の自動 KV streaming 選択が `--max-context > 20480` などの条件で正の `--kv-resident` を設定し得る。その後 `STRATA_KV_GROW` が on でも `o.kv_resident <= 0` の条件に失敗して off になる。環境変数だけで要求する場合もこの先行選択の影響を受ける（`engine/sycl/src/program/generate.cpp:4240-4278, 4285-4296`）。
- `STRATA_EXPERT_NIBBLE` が要求されている場合、CUDA の nibble 機能はこの値を競合設定として確認する。空でない値の先頭が `0` 以外なら nibble はこの起動では拒否され、通常の GGUF slot のまま続行する警告を出す。これは `STRATA_KV_GROW` を無効化する判定ではない（`engine/include/strata/core/expert_nibble.hpp:272-295`、`engine/src/program/generate.cpp:3405-3439, 5474-5489`）。

## 実行時の詳細

CLI 引数は先に解析され、後から環境変数の非空値が優先して `asked` を決める。成立条件を評価した後、`STRATA_KV_GROW_INIT` を `atoll` で読み、正数なら初期 cell 数に使い、それ以外（未設定、空、0、負数、非数値）は 16384 にする。`qsa_set_kv_elastic` は有効状態と初期 cell 数を保持し、K/V pool をその初期 cell まで map する（`engine/src/program/generate.cpp:7718-7732`、`engine/src/core/layer.cpp:624-626, 680-684, 827-848`）。

CUDA 系の `kvg_ensure` は要求 cell 数を `STRATA_KV_GROW_STEP` の正の倍数へ切り上げ、`--max-context` を上限として K/V pool を伸ばす。`STRATA_KV_GROW_STEP` は `atoll > 0` の場合だけ採用し、既定値は 8192。expert cache からの slot 提供が可能な場合に限り `STRATA_KV_GROW_FLOOR` を同様に正数で読み、cache が保持する slot 数を設定する（`engine/src/program/generate.cpp:11527-11559, 11563-11674`）。SYCL は同じ STEP/FLOOR の正数判定を行い、既定値はそれぞれ 8192 と 128（`engine/sycl/src/program/generate.cpp:6782-6805`）。これらは関連変数であり、対象変数の on/off 判定には使わない。

初期化後は prompt の必要 cell、保存/parked conversation の復元、decode window で伸長を確認する。server 経路では要求ごとの読み直しではなく、起動時に決めた `kvg.on` を使う（`engine/src/program/generate.cpp:18767-18770, 19233-19240, 19952-19958, 22975-22980`）。`STRATA_KV_GROW_HOLD` は server の trim 時に static 初回評価され、非ゼロなら parked conversation の最長長さ分を保持するが、伸縮 K/V の有効化条件は変えない（同 `:20064-20075`）。

## ログと測定値

- 要求されたが条件不足なら stderr に `strata generate: --kv-grow is off (one GPU, a profile, the whole K/V in VRAM, every expert in RAM, no --batch, --vram-elastic or --peer-device)` を出す（`engine/src/program/generate.cpp:7727-7729`）。
- expert cache と連携して開始した場合は stderr に `strata generate: elastic K/V: ...`、伸長時に `strata: K/V grown to ...`、server で trim した時に `strata: K/V trimmed to ...` を出す。処理終了時には stdout に `elastic K/V` の cell/grow/trim/evicted/refilled 集計を出す（`engine/src/program/generate.cpp:11554-11559, 11665-11674, 11742-11745, 25518-25521`）。
- VMM map に失敗すると `strata: the elastic K/V could not map ... (the driver has no VRAM left)`、伸長失敗時は `strata: the K/V could not grow to ...` を stderr に出す。prompt/window/restore の呼び出し元は `ERR the K/V cannot grow...` などを stdout に出して終了または当該復元を拒否する（`engine/src/core/layer.cpp:654-675`、`engine/src/program/generate.cpp:11656-11674, 18767-18770, 19233-19240, 22975-22980`）。
- `docs/DETAILS.md:254` は one GPU、profile、全 K/V VRAM、全 expert RAM を条件として説明している。現行 CUDA 実装では cache から slot を得られない場合も新規 VRAM で伸長を続けるため、「expert cache holds the rest and gives slots back」という資料の説明は全経路に当てはまらない（`engine/src/program/generate.cpp:11537-11553`）。資料記載の性能主張は本調査で再測定していない。

## 根拠

- 候補名の本番読み取り: `engine/src/program/generate.cpp:7718-7732`、`engine/sycl/src/program/generate.cpp:4285-4299`。
- helper 経由の追加参照: `engine/include/strata/core/expert_nibble.hpp:277-295`。呼び出しと警告: `engine/src/program/generate.cpp:3408-3439, 5474-5489`。
- K/V pool の map と失敗ログ: `engine/src/core/layer.cpp:624-676, 680-684, 827-848`。
- CUDA 系の成長判定と更新: `engine/src/core/kv_grow_rules.hpp:23-36`、`engine/src/program/generate.cpp:11541-11674`。
- 文書との照合: `docs/DETAILS.md:246-257`、設定一覧 `docs/SETTINGS.md:148-149`。
