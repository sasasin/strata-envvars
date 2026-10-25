# `STRATA_LOOKAHEAD`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

ルーティング予測 prefetch（CS-T）を ON / OFF するスイッチ。ON のとき、CPU expert pool が layer `l` の verify window を処理するたびに、別スレッド（predictor thread）が layer `l+1` の router（`ffn_gate_inp.weight`、BF16）を layer `l` の MoE input にかけて、次の layer が選びそうな expert を top-k 予測し、そのページを OS に要求する（Linux `madvise(MADV_WILLNEED)`、Windows `PrefetchVirtualMemory`）。RAM copy や GPU cache がすでに持っている expert は除かれる。

これはページを暖めるだけなので、実際に計算される expert も生成される token も変わらない。Strata の資料は「the answers are the same」と明記している（`docs/DETAILS.md:255-256`、`include/strata/core/expert_source.hpp:243-244`）。

読み取り箇所は CUDA/HIP 実装 `src/program/generate.cpp:5499` と SYCL 移植 `sycl/src/program/generate.cpp:5067` の 2 箇所だけで、Python サーバー（`serve/`）や `setup.py` はこの名前を読まない。HIP は同じ `.cpp`/`.cu` ツリーを HIP でビルドする（`CMakeLists.txt:59-64`）ので、CUDA と同じ判定になる。

## 値と判定

判定は `std::getenv` の結果の `std::atoi(v)` だけで、文字列全体を parse しない。

| 状態 | 結果 |
|---|---|
| 未設定 | ON（既定） |
| 設定済みで `atoi` が 0 以外 | ON。例: `1`, `2`, `true`（`atoi("true")` は 0 なので **OFF**） |
| 設定済みで `atoi` が 0 | OFF。例: `0`, `abc`, 空文字 |

- 空文字は「設定されている」が `atoi("")` は 0 なので OFF。
- 大文字小文字・空白・数値の妥当性は検査されない。`atoi` は先頭の数字列だけを見て、後ろを無視する（`10abc` → 10 → ON）。
- 負値（`-1`）は `atoi` が 0 以外を返すので ON。
- 判定は `main()` の起動時（expert source を開いた直後）に 1 回だけ行われ、`RouterLookahead` の起動可否として固定される。プロセス起動後に環境を変えても再評価されない。

根拠: `src/program/generate.cpp:5499`、`sycl/src/program/generate.cpp:5067`。

## 有効になる条件

`STRATA_LOOKAHEAD` が ON でも、次の条件が揃わなければ predictor thread は作られない。

CUDA/HIP（`src/program/generate.cpp:5494-5511`）:

1. `srcp != nullptr`（expert source が開かれている）。
2. 次のいずれか:
   - `srcp == &src`（`--mmap-experts` の file tier）かつ `src.warms()`。`warms()` は `(!role_ptr_.empty() || io_pf_) && direct_.empty()`（`include/strata/core/expert_source.hpp:706`）。つまり unbuffered read（`direct_`）が有効な状態では `warms()` が false になり、この経路では起動しない。
   - `STRATA_FS_SLOTS` が 0 より大きく、かつ `STRATA_FS_AHEAD` が未設定または 0 以外（Foresight swap space に予測を渡す経路。この場合 source が warm しなくてもよい）。
   - `STRATA_LOOKAHEAD_STATS` が設定済みで `atoi` が 0 以外（測定のみ。この場合も cold source を許す）。
3. 各 layer の router が `WeightKind::Bf16InF32` で、サイズが `n_expert * n_embd * 2` であること。違えば `ok` が false になり起動しない。
4. `RouterLookahead::start()` の検査: `n_embd % 8 == 0`、各 router の長さが `n_embd * n_expert`。

SYCL（`sycl/src/program/generate.cpp:5067`）は条件 2 が `srcp == &src && src.warms()` だけで、`STRATA_FS_AHEAD`・`STRATA_LOOKAHEAD_STATS` による例外がない。SYCL の `warms()` は `!role_ptr_.empty() && direct_.empty()`（`sycl/include/strata/core/expert_source.hpp:581`）で、`io_pf_` を見ない。

`--no-pool` の場合、`drive_pool_multi`（`src/program/generate.cpp:1006-1011`）が呼ばれないので `submit()` は走らない。thread は起動するが予測は一度も実行されない。単一 token 用の `expert_pool_dispatch`（`src/core/expert_source.cpp:3477`）は `submit()` を呼ばない。`submit()` を呼ぶのは verify window 用の dispatch だけで、decode loop と prefill の pool 呼び出しがそれに当たる（`src/program/generate.cpp:13070`, `13351`）。

## 実行時の詳細

- 起動時、router 行列を device から host へ 1 回コピーする（CUDA `cudaMemcpy`、SYCL `dpct ... memcpy().wait()`）。`src/program/generate.cpp:5500-5509`。
- `k`（token あたりの予測 expert 数）は `STRATA_LOOKAHEAD_K`、既定 10。`start()` 内で `k < 1 ? 1 : k > n_expert ? n_expert : k` に clamp される（`src/core/expert_source.cpp:2192`）。`atoi` が 0 を返す値（`abc`, 空文字）は 1 になる。
- `submit()` は token を 8 個までしか使わない（`n_tok_ = std::min<int64_t>(n_tok, 8)`）。`layer + 1 >= routers_.size()`、`n_tok <= 0`、`x == nullptr` では何もしない。
- predictor thread が `busy_` または `pending_` の間に新的な submit が来ると、その layer は待たずに `skipped_` を増やして return する（`src/core/expert_source.cpp:2202-2215`）。
- `depth`（何 layer 先まで予測するか）は既定 1。`STRATA_IO_PREFETCH_DEPTH` が設定済みで `atoi > 0` ならその値、そうでなければ file tier の io prefetch が有効なとき 2。`set_depth()` は 1..4 に clamp する（`include/strata/core/expert_source.hpp:264`, `src/program/generate.cpp:5514-5517`）。SYCL には `set_depth` がない。
- 予測された expert のうち、GPU cache / RAM copy（`host_res`、`complement_ready_ && resident_blob`）が持っていないものだけを `warm()` に渡す（`src/core/expert_source.cpp:2378`, `2132-2133`）。
- `warm()` は Linux で 4096 バイト境界に丸めた範囲に `madvise(MADV_WILLNEED)` を出す。Windows では range を集めて `PrefetchVirtualMemory` を 1 回呼ぶ。`GetProcAddress` で関数を取れなかった場合は何もしない（`src/core/expert_source.cpp:2123-2154`）。
- `STRATA_IO_PREFETCH=1` で `io_pf_` が立っている file tier では、`warm()` は madvise ではなく I/O thread への `io_enqueue` になる（`src/core/expert_source.cpp:2136-2139`）。`STRATA_IO_PF_AHEAD=0` の場合は enqueue しない。
- Foresight swap space が繋がれているとき、`dj == 0`（1 层先）の予測だけを `fs->predict()` に渡す。深い予測は copy に使わない（`src/core/expert_source.cpp:2410-2411`）。
- predictor thread は `strata::aux_cpus::pin_current_thread()` を呼ぶ（`src/core/expert_source.cpp:2195-2198`）。SYCL 版は pin しない（`sycl/src/core/expert_source.cpp:1456`）。
- warm した事実は `warm_stamp_[index] = epoch_ + 1` に記録され、後でその blob が実際に読まれたとき `s != 0 && s + 3 >= epoch_ + 1` なら `warm_hits_` が増える（`src/core/expert_source.cpp:2134`, `1471-1474`）。`epoch_` は layer が変わるたびに 1 増える（`2428-2431`）。

## ログと観測できる結果

起動時（stderr）:

- 起動成功: `strata generate: routing-aware prefetch on (the next layer's router, file tier)`、Foresight 経路では `..., feeding the Foresight swap space)`（`src/program/generate.cpp:5518-5519`）。SYCL は `routing-aware prefetch of the file tier on (the next layer's router)`（`sycl/src/program/generate.cpp:5084`）。
- 起動失敗: `strata generate: routing-aware prefetch off (<理由>)`。理由は `start()` のエラー文字列（`RouterLookahead: the expert source does not warm` / `n_embd is not a multiple of 8` / `a router of another shape`）または `ok` が false のときの `the routers are not BF16 in the arena`（`src/program/generate.cpp:5520-5524`）。
- `STRATA_LOOKAHEAD=0` で OFF の場合、このログは出ない。判定が false だとブロック全体を通らない（`src/program/generate.cpp:5499`）。

終了時のレポート（stdout）: `srcp == &src` のとき、decode loop が走った後に `routing prefetch` 行が出る。

```
routing prefetch   <warmed> experts warmed, <hits> of the file tier's <reads> blob reads had been warmed (<pct>%); predictor <ms> ms/round on its thread, <skipped> layers skipped (still busy)
```

（`src/program/generate.cpp:13213,13233-13239`）。この行は `--stats` の判定ではなく、speculative decode ブロック（`src/program/generate.cpp:12768`）の末尾にある。`docs/DETAILS.md:288-290` は「with `--stats` the engine prints the tiers of the decode … `routing prefetch`」と説明しているが、コード上は `o.stats` の分岐（`src/program/generate.cpp:13335`）とは別に、file tier で decode が実行されれば print される。資料とコードのこの点は一致していない。

`STRATA_LOOKAHEAD_STATS=1` のとき、100 window ごとに stderr へ `strata lookahead stats:` 行（`src/core/expert_source.cpp:2285-2309`）。これは測定専用で、`warm()` の動作は変えない。

## 関連する環境変数

- `STRATA_LOOKAHEAD_K`: token あたりの top-k（既定 10、1..n_expert に clamp）。
- `STRATA_LOOKAHEAD_STATS`: 測定のみ（既定 OFF）。
- `STRATA_IO_PREFETCH_DEPTH`: 予測の深さ（既定 1、1..4）。
- `STRATA_FS_SLOTS` / `STRATA_FS_AHEAD`: Foresight swap space へ予測を渡す経路。
- `STRATA_IO_PREFETCH` / `STRATA_IO_PF_AHEAD`: warm の実体を madvise から I/O thread への enqueue に変える。
- `STRATA_UNBUFFERED_LOAD`・`--resident-budget-gib`: `direct_` を立てて `warms()` を false にし、file tier 経路の起動を止める。

## 資料にある測定値

`docs/UNSLOTH_Q4.md:232` は、このモード（Unsloth UD-Q4_K_XL の file tier）で既定 ON、SSD read の約半分が予測でき、平均 +14%（6.9 → 7.9 tok/s）と記載している。これは同資料に書かれた条件での測定値で、他の機種・量子化での性能を保証するものではない。`docs/DETAILS.md:226-228` は Linux の I/O path における `STRATA_LOOKAHEAD_K` と depth の関係だけを説明し、この変数自身の A/B 数値は載せていない。

## 確認できなかった点

- `000_envvers.md` の候補名から実際に環境を読むコードを 2 箇所（CUDA/HIP 共用の `src/program/generate.cpp` と SYCL 移植）で確認した。Python 側・テストコードには読み取り箇所がない。
- SYCL 移植は `docs/INTEL_ARC.md` で experimental として分離されている（`CMakeLists.txt:12-20`）。SYCL 版には stats・depth・Foresight への接続がない。この差分はコードから確認できるが、SYCL ビルド自体はこの調査ではビルドしていない。
- 性能数値は Strata の資料に記載された条件の値としてのみ示した。この調査で新たに測定はしていない。
