# `STRATA_DEFERRED_REGISTER`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Windows の SYCL エンジンで、expert arena の layer ごとの host registration を expert データの読み込みと並行させる経路を選ぶ環境変数。対象は通常の resident arena を使う経路で、`--stream-experts` と `--mmap-experts` の経路ではない。

ただし、この HEAD の SYCL 移植コードでは registration API の呼び出しが DPCT により定数条件へ置換されている。したがって、下記の「deferred」経路は構成上選べるものの、このコードから GPU driver に layer ごとの host registration が行われるとは確認できない。実行ログの `slices pinned` という表現も、実際の driver registration 成功を証明しない。

## 値と判定

`ArenaExpertSource::open()` の Windows 分岐で `std::getenv("STRATA_DEFERRED_REGISTER")` を呼び、未設定でなく、値が空でなく、先頭文字が `'0'` でなければ真とする。文字列全体の比較や数値変換はしない（`sycl/src/core/expert_source.cpp:3440-3445`）。

| 値 | `defer_env` による判定 |
|---|---|
| 未設定 | false |
| 空文字 `""` | false |
| `"0"`、`"00"`、`"0anything"` | false |
| `"1"`、`"2"`、`"true"`、`"false"`、`" 0"` | true |

環境値だけで経路が決まるわけではない。さらに `max_pinned_bytes == 0`、`arena_pin_cap_gib() == -1`、`shared_arena_file.empty()` のすべてが必要（同 3441-3443）。

## 有効になる条件

- ソース上の環境変数判定は `_WIN32` 内にだけある。Linux では `deferred` は常に false（`sycl/src/core/expert_source.cpp:3440-3445`）。
- 呼び出し元は `--stream-experts` と `--mmap-experts` 以外の resident arena 経路で `ArenaExpertSource::open()` を呼ぶ（`sycl/src/program/generate.cpp:4150-4167,4201-4218`）。
- multi-GPU under WDDM（または remote experts）では呼び出し元が `pin_limit` を最大 8 GiB に設定するため、通常 `max_pinned_bytes == 0` 条件を満たさず、この変数の deferred 経路には入らない（`sycl/src/program/generate.cpp:4203-4218`）。明示的な `STRATA_ARENA_PIN_GIB` 設定も `arena_pin_cap_gib() == -1` 条件を外す。
- `STRATA_ARENA_MMAP=1` で既存の `experts.bin` を mmap できた場合、`ArenaExpertSource::open()` は mmap の成功時点で戻るため、この判定箇所に到達しない（`sycl/src/core/expert_source.cpp:3350-3387`）。
- shared arena を指定した場合も `shared_arena_file.empty()` 条件を満たさない。

## 実行時の詳細

有効判定時には `PinnedArena::Deferred` コンストラクターを選び、layer 境界と arena の領域を渡す。別スレッドで `register_slices(ready)` を開始し、その一方で GGUF または pack file から expert を読み込む。loader は layer `l` を書く前に `ready > l + 1` まで待ち、次 layer の slice 登録が進むのを待つ。読み込み終了後に登録スレッドを join する（`sycl/src/core/expert_source.cpp:3425-3432,3447-3449,3474-3496`; loader gate は同 3146-3153 および 3181-3184）。

`register_slices()` は slice ごとに `ready` を進め、完了後 `INT_MAX` にする。未処理 slice が残る場合は、`STRATA_ARENA_LOCK` が未設定または値が文字列 `"0"` と完全一致しないなら remainder を resident lock する（`sycl/src/core/pinned.dp.cpp:524-562`）。これは関連する別変数の処理である。

この HEAD では通常 constructor 内の registration 判定が `0`（`sycl/src/core/pinned.dp.cpp:384-396`）、slice ごとの registration 判定も `0 != 0`（同 524-546）であり、実際の登録処理は実行されない。deferred constructor は arena を確保し slice 分割状態を設定し（同 513-522）、並行読み込みの `ready` ゲートと後続コードの bookkeeping を行う。完了時には `note` に `cudaHostRegister per layer, pipelined with the load: ... slices pinned` を付ける（同 548-561）が、この文言はソース上の no-op 化と食い違い、実登録を示す証拠として扱えない。

ソースコメントは Windows/RTX 5070 で layer 登録を先に済ませてから読み込む方式が旧方式より decode を約10%遅くしたと述べる（`sycl/src/core/expert_source.cpp:3434-3439`）。しかし機種・OS/driver・モデル・設定などの測定条件はここに十分記載されておらず、コードコメント上の説明としてのみ記録する。`docs/DETAILS.md` を含む `docs/` にこの環境変数の説明は見つからなかった。

## 根拠

- 唯一の環境変数読み取り、値条件、Windows 分岐: `sycl/src/core/expert_source.cpp:3434-3449`
- open 経路と `--stream-experts` / `--mmap-experts` 分岐: `sycl/src/program/generate.cpp:4150-4183,4201-4218`
- WDDM / multi-GPU pin 上限と `STRATA_ARENA_PIN_GIB`: `sycl/src/program/generate.cpp:4203-4218`
- deferred スレッド、loader との同期、起動時 note: `sycl/src/core/expert_source.cpp:3474-3497,3537-3565`
- layer ごとの loader wait: `sycl/src/core/expert_source.cpp:3146-3153,3181-3184`
- deferred constructor と slice bookkeeping、registration no-op、およびログ文言: `sycl/src/core/pinned.dp.cpp:384-396,513-562`
