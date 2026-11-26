# `STRATA_STAGE_PIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`FileExpertSource` が GGUF などの expert blob を一時保持する stage buffer を、ページロックされた host buffer として確保するかを選ぶ。設定値 `0` または未設定では pageable buffer、`atoi` の結果が 0 以外なら pinned buffer を要求する。CLI 引数や設定ファイルを参照する処理はこの読み取り箇所にはなく、他の値で上書きする分岐もない。対象は stage buffer の確保だけで、expert の選択・値・キャッシュ容量を直接変える分岐はない。実装は `engine/src/core/expert_source.cpp` の `FileExpertSource::claim_stage` にある（同ファイル:2141-2148, 2183-2202）。

この実装は stage buffer を使うファイル読み込み経路に限られる。`blob()` は resident complement または override から返せる場合はファイル読み込みを迂回し、それ以外では `io_pf_` または `staged()` に応じて `io_blob()` / `staged_blob()` / `mapped_blob()` を選ぶ（`engine/src/core/expert_source.cpp:5200-5234`）。`staged()` は role file、direct file、または I/O prefetch のいずれかがある場合に真となる（`engine/include/strata/core/expert_source.hpp:1149-1151`）。

## 値と判定

環境変数を `std::getenv` で読み、未設定なら `-1`、設定されていれば `std::atoi` の結果を保存する。値全体の検証や文字列比較はしない。`atoi` が 0 を返す場合は無効化、0 以外は pin を要求する（`engine/src/core/expert_source.cpp:2189-2193`）。

| 条件 | unset | pin を要求する値 | pin を要求しない値 |
| --- | --- | --- | --- |
| `engine/src/core/expert_source.cpp` の実装 | `pin_mode=-1`。`STAGE_PIN_DEFAULT` が `0` のため pageable | `atoi` が 0 以外になる値（例: `1`, `-1`, `1tail`, ` 1`） | `atoi` が 0 になる値（例: `0`, `0tail`, 空文字, `true`, `false`, `tail`） |

先頭の空白や符号、数値の後ろの文字列は `atoi` の規則で扱われ、Strata は文字列全体の妥当性を検査しない。したがって `1tail` は pin 要求、`0tail` は無効となり、`true` / `false` はどちらも 0 に変換される。`atoi` の整数範囲外入力について、Strata 側の検出や安全な fallback はない（同ファイル:2189-2193）。

## 有効になる条件

- `FileExpertSource` がファイル由来の expert blob を stage buffer に組み立てる経路であること。resident complement / override から blob を返す経路や、staging を通らない mapped 経路では、この確保分岐に到達しない（`engine/src/core/expert_source.cpp:5200-5234`）。
- 新しい stage buffer が必要なこと。`claim_stage()` が既存の blob を見つけたり、再利用できる buffer を確保できたりすると、環境値を使った新規確保分岐には入らない（同ファイル:2161-2181, 2183-2189）。
- 設定値から pin 要求が出た場合も、`cudaHostAlloc` が成功し、返却 pointer が非 null のときだけ pinned 扱いとなる。失敗時は pageable buffer に fallback する（同ファイル:2195-2202）。
- 未設定時の既定は build macro `STAGE_PIN_DEFAULT 0` により常に pageable。既定経路で利用可能 RAM を測る分岐はあるが、macro が 0 のため `available_memory_bytes()` の結果に関係なく pin されない（同ファイル:2144-2145, 2190-2194）。
- この名前の読み取りは `engine/src/core/expert_source.cpp` に一箇所だけあり、この分岐には OS / backend の条件コンパイルがない。通常 GPU engine のソース登録は `engine/cmake/strata_gpu_engine.cmake:305-316`、Metal の host source 登録も同じファイルを含む（`engine/metal/CMakeLists.txt:135-142`）。SYCL 用は別実装 `engine/sycl/src/core/expert_source.cpp` で、この名前の参照がなく、同じ設定が SYCL 実装にも適用されるとは確認できない（SYCL 側の登録: `engine/sycl/CMakeLists.txt:290-299`）。

## 実行時の詳細

設定はプロセス起動直後ではなく、`claim_stage()` が再利用可能な buffer を見つけられず新規 buffer を増やすときに、関数内 `static const int pin_mode` として初回評価される。その後はプロセス内でキャッシュされ、実行中に環境値を変更しても再評価されない（`engine/src/core/expert_source.cpp:2174-2193`）。

pin 要求時には `stage_blob_` のサイズで `cudaHostAlloc` を試し、成功した buffer は `StageBufFree` が `cudaFreeHost` で解放する。要求がない場合、または pin allocation が失敗した場合は `new (std::nothrow) uint8_t[...]` で pageable buffer を確保する（同ファイル:2146-2149, 2195-2202）。stage buffer は file read の宛先になり、キャッシュへの転送に使われる（同ファイル:2361-2366, 2527-2531, 6011-6018）。

pinned source から非同期コピーをキューした場合、`note_async_read()` は event を記録し、buffer の再利用時にコピー完了を確認する。pageable buffer ではこの event 管理をせず、そのまま再利用可能とする（同ファイル:2386-2408, 2227-2239）。この変数が変えるのは stage buffer の確保方式であり、コード上で expert 選択や cache 容量を切り替える分岐はない。結果の同一性までは、この分岐から断定できない。

## ログと測定値

pin 確保に成功すると `stderr` に `FileExpertSource: the stage buffers are pinned (cudaHostAlloc)` を、その `FileExpertSource` インスタンスで一度出す。pin 要求が失敗すると `FileExpertSource: cudaHostAlloc failed for a stage buffer (%s) - pageable it is` を一度出し、pageable buffer で続行する。pin を要求しない既定・`=0` の場合は pin 状態のログを出さない（`engine/src/core/expert_source.cpp:2206-2213`, `engine/include/strata/core/expert_source.hpp:1211-1214`）。

pageable buffer 自体の `new (std::nothrow)` が失敗すると `claim_stage()` は `false` を返す。呼び出し側では blob を得られず、expert cache の hit 経路は `the expert cache could not fill a slot` として失敗を記録する（`engine/src/core/expert_source.cpp:2200-2201, 2430-2446, 6007-6016`）。生成側はこの失敗を fatal 経路または `ERR` として処理する（`engine/src/program/generate.cpp:16386, 17240-17241, 18269-18273, 20444-20446`）。pin allocation の失敗そのものはこの失敗経路にならず、pageable fallback に進む。

`docs/DETAILS.md:1263` は過去の 0.1.41 release gate で IQ3_S が 4096-token prompt 後に破損した記録と、unset では off とする説明を載せる。現行コードでも unset は `STAGE_PIN_DEFAULT 0` により off だが、明示的な非ゼロ値で opt-in できる。`docs/DETAILS.md:1718` の性能行は条件の詳細が行内にないため、性能値はここでは再掲しない。コードから token の同一性や性能の現在値は確認できない。

## 根拠

- `engine/src/core/expert_source.cpp:2141-2149` — 既定 macro、stage buffer の解放。
- `engine/src/core/expert_source.cpp:2158-2247` — 再利用判定、環境値の static cache、pin 要求、fallback、ログ。
- `engine/src/core/expert_source.cpp:2361-2408` — stage fill、非同期 read 完了の event 管理。
- `engine/src/core/expert_source.cpp:2418-2447, 2480-2531` — blob 要求と stage buffer への流入。
- `engine/src/core/expert_source.cpp:5200-5234, 6007-6018` — resident / staged / mapped 経路の選択と cache fill。
- `engine/sycl/src/core/expert_source.cpp` — `STRATA_STAGE_PIN` の読み取り参照なし（現行 checkout の完全一致検索）。
