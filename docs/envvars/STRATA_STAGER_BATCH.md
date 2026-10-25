# `STRATA_STAGER_BATCH`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

prompt prefill の host-side stager が、1つの worker claim で処理する連続 expert copy job 数を指定します。job は layer の expert 順に並び、stager worker は claim した各 job の host buffer へのコピーを済ませてから ready にします。GGUF shard を直接読む `FileExpertSource` では、この複数 job が `copy_blobs()` にまとめて渡され、連続した読み取り要求をまとめる経路になります。変数は GPU の expert 選択数や stager ring の深さを直接設定するものではありません。

## 値と判定

値は `std::atoi()` で変換し、まず `1..32` に clamp します。文字列全体の妥当性は検査しません。未設定時は `files` の状態に応じて初期値が異なります。

| 状態 | `want` の値 | clamp 後 |
|---|---:|---:|
| 未設定、transient source profile (`files == true`) | 8 | 8 |
| 未設定、それ以外 | 1 | 1 |
| 設定あり | `atoi(value)` | `1..32` |

`atoi()` のため、空文字や数字に変換できない文字列は通常 `0` となり、最終的に `1` です。`"5tail"` は通常 `5`、負値は `1`、32 より大きい値は `32` になります。数値変換後にはさらに `min(batch, kRing)` が適用されます。したがって ring が 4 なら、設定値が 8 や 32 でも実効 batch は 4 です。数値変換の `int` 範囲外入力の結果は保証されません。

## 有効になる条件

- stager が使われる CUDA/HIP 系の prompt prefill 経路で有効です。通常の stager は、各 layer で pinned source ではない expert を host staging buffer にコピーしてから GPU へ転送します（`src/prefill/prefill.cpp:3691-3731`）。
- 未設定時に 8 が選ばれる `files` profile は、source のどれかが `transient()` と答えた場合に候補になります。ただし `STRATA_STAGER_THREADS` が未設定なら、`STRATA_STAGER_SSD` または `cached_share(256)` の判定で RAM profile に切り替わることがあります。したがって「GGUF なら常に 8」ではありません（`src/prefill/prefill.cpp:1101-1129`）。
- 明示設定値はこの profile 判定による batch の既定値を上書きします。`STRATA_STAGER_THREADS` は threads 数と profile 判定に関係しますが、明示された `STRATA_STAGER_BATCH` の値を別途上書きしません。
- `src/prefill/prefill.cpp` に実装があり、通常の CMake 構成では `strata_prefill` に含まれます。SYCL 側の `sycl/src/prefill/prefill.cpp` にはこの変数の読み取りがありません。

## 実行時の詳細

環境変数は `Prefill::init()` 内で `m.stager` を初めて作るときに読み、stager の `batch` メンバーに保存します。同じ `Prefill` instance の後続 init/chunk では stager を再作成しないため、環境を後から変更しても batch は更新されません（`src/prefill/prefill.cpp:1096-1133`）。

worker は `claim(seen, batch, k)` で最大 `batch` 個の連続 job を一括 claim します。job のコピー先 ring buffer が前の DMA に使われている場合は、その DMA の発行と完了を待ってから次のコピーに進みます。claim 内の source-backed jobs はまとめて `ExpertSource::copy_blobs()` に渡され、stable pointer の jobs は worker が各 buffer に `memcpy()` します。完了後、claim した各 job を ready にします（`src/prefill/prefill.cpp:483-523,526-535`）。

標準 `ExpertSource::copy_blobs()` は各 blob を順にコピーします（`src/core/expert_source.cpp:1094-1098`）。`FileExpertSource` の direct-read 経路では、複数 blob が一回の `read_direct()` に渡されます。そこで失敗した場合は個別の `copy_from_files()` に fallback します（`src/core/expert_source.cpp:2497-2527`）。この batch の設定による専用ログはありません。source がコピーに失敗すると stager は `prefill: the expert source could not copy experts %d.. of layer %d` を stderr に出して abort します（`src/prefill/prefill.cpp:517-519`）。

`docs/DETAILS.md` は `STRATA_STAGER_THREADS` / `STRATA_STAGER_SSD` の profile と測定条件を記載していますが、`STRATA_STAGER_BATCH` 固有の性能測定値や既定値の説明は見つかりませんでした。そのため、この変数による速度向上の大きさは記載できません。

## 根拠

- 読み取り、既定値、clamp、profile 条件: `src/prefill/prefill.cpp:1101-1133`
- worker claim、コピー、ready 通知: `src/prefill/prefill.cpp:483-523,526-535`
- prompt prefill の job 作成と stager 利用: `src/prefill/prefill.cpp:2343-2387,3691-3731`
- file source の複数 blob 処理と fallback: `src/core/expert_source.cpp:2497-2527`
- 標準 `copy_blobs()` の逐次処理: `src/core/expert_source.cpp:1094-1098`
- build への組み込み: `CMakeLists.txt:589-595`
- 関連する profile 説明と測定条件: `docs/DETAILS.md:1562`
