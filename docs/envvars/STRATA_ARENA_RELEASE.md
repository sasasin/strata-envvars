# `STRATA_ARENA_RELEASE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は、CUDA/HIP 系または SYCL 系エンジンがトークングラフ用の expert residency table を作る経路で、GPU キャッシュに載った expert の元データを `ExpertSource::release()` に渡すかを切り替える。値が `0` で始まると呼び出しを抑止し、それ以外（未設定を含む）では呼び出す。`release()` が処理するデータはソース種別と OS によって異なるため、設定しただけで必ずページが解放されるわけではない。CUDA/HIP 側は `engine/src/program/generate.cpp:10997-11033`、SYCL 側は `engine/sycl/src/program/generate.cpp:6483-6516`。

## 値と判定

両実装とも `std::getenv()` の結果が非 null で、かつ先頭 1 文字が `'0'` の場合だけ `keep=true` とする。文字列全体の比較や数値変換はしない。空文字は設定済みでも先頭が NUL なので `keep=false`。大文字小文字・空白・数値としての妥当性も検査しない。

| 条件（実装） | unset | 設定時に release を抑止する値 | release を試みる値 |
|---|---|---|---|
| CUDA/HIP 系、SYCL 系の共通判定 | `keep=false` | 先頭が `0` の文字列（`0`、`0anything`、`01`） | 空文字、`1`、`true`、`false`、` 0`、その他先頭が `0` でない値 |

判定結果はブロック内の `static const bool keep` に保存される。最初にこの経路へ入った時の値がプロセス内で使われ続け、実行中に環境を変更しても再評価されない（`engine/src/program/generate.cpp:11026-11033`、`engine/sycl/src/program/generate.cpp:6509-6516`）。

## 有効になる条件

- CUDA/HIP 系では `profile` が空でなく、`--no-pool` が無効で、`hit_fn` があるか、native pack で expert cache が 0 の `zero_slot_res` 経路であり、さらに `--no-capture`・`--no-token-graph` が無効で、layer dump / half dump を使わないことが条件（`engine/src/program/generate.cpp:10997-11000`）。
- SYCL 系では `hit_fn` があり、`profile` が空でなく、`--no-pool`・`--no-capture`・`--no-token-graph` が無効で、layer dump / half dump を使わないことが条件（`engine/sycl/src/program/generate.cpp:6483-6485`）。
- 条件を満たすと、resident table で GPU に載っていると判定された expert だけを `srcp->release(layer, expert)` に渡す。`STRATA_ARENA_RELEASE=0` 相当の先頭 `0` ならこの呼び出しを飛ばす。GPU に載っていない expert への `prefetch()` は、どちらの分岐でも続けて行う（`engine/src/program/generate.cpp:11029-11045`、`engine/sycl/src/program/generate.cpp:6512-6528`）。
- `srcp` が `ArenaExpertSource` の場合、Windows では `release()` は常に 0 を返す。Windows 以外では、マッピングがあり index が有効で、blob 内に 4 KiB 単位で丸めた対象ページがある場合に `madvise(..., MADV_DONTNEED)` を試す（失敗時は 0、成功時は対象バイト数を返す）。従って Windows 以外の arena-backed source で実際の処理が可能（`engine/src/core/expert_source.cpp:6974-6992`、SYCL 用の同実装は `engine/sycl/src/core/expert_source.cpp:3600-3618`）。
- `srcp` が `FileExpertSource` の場合、Windows 以外では `release()` は 0 を返す。Windows では別変数 `STRATA_FILE_RELEASE` が文字列全体で `1` と一致しなければ何もしないため、`STRATA_ARENA_RELEASE` だけでは mapped file のページを解放しない（`engine/src/core/expert_source.cpp:3933-3940,3978-3982`、SYCL 用の同実装は `engine/sycl/src/core/expert_source.cpp:1609-1616` および `engine/sycl/src/core/expert_source.cpp:1643-1645`）。

## 実行時の詳細

トークングラフ用の residency table を構築して device 側へ転送した後、`keep` を判定し、解放を許可する場合は table 上で resident の各 expert を `srcp->release()` に渡す。返されたバイト数の合計が正の場合に限り、stderr に合計を GiB 表示する。その後、non-resident の expert ごとに `srcp->prefetch()` を呼び、処理を続ける。resident table や GPU cache の slot をこの分岐で変更する処理はない（`engine/src/program/generate.cpp:11010-11045`、`engine/sycl/src/program/generate.cpp:6494-6528`）。

環境値を読むのは上記ブロックに初めて到達した時で、`static` 判定はプロセス内でキャッシュされる。CLI 引数から値を上書きする処理や、別プロセスへ値を渡す処理はこの経路にはない。解放に失敗して `release()` が 0 を返しても、このブロックはエラー終了せず、別の方法へ fallback もしない。`ArenaExpertSource` の `madvise` 失敗は 0 を返し、呼び出し元は合計値に加えない（`engine/src/core/expert_source.cpp:6980-6991`）。

## ログと測定値

解放 API の戻り値の合計が正の場合、stderr に次の形式で出力する。合計が 0（先頭 `0` による抑止、対象外 source / OS、解放失敗を含む）の場合、この行は出ない。

```text
strata generate: expert arena: %.2f GiB of VRAM-held experts handed back to the OS
```

`STRATA_RSS_TRACE` が設定されていれば、処理前後に `strata rss: before the release: RssFile %.2f GiB`、`strata rss: after the release: RssFile %.2f GiB` の形式で stderr に `RssFile` を出す。設定有無は `rss_probe()` の初回呼び出し時に static cache される（`engine/src/program/generate.cpp:659-672,11028-11037`、`engine/sycl/src/program/generate.cpp:303-316,6511-6520`）。この測定値はこの変数自身の効果を保証する値ではない。

`docs/bench-results/2026-10-04-windows-mapped-release/README.md:104-107` は、測定時の prototype 名を `STRATA_ARENA_RELEASE` とし、その後の Windows mapped-file 実装名を `STRATA_FILE_RELEASE` と説明している。これは現行コードで `STRATA_ARENA_RELEASE` が `ArenaExpertSource` の処理を選ぶこととは別の経路であり、ここでは測定値を現行変数の性能効果として扱わない。

## 根拠

- 候補名の実読み取り箇所は `engine/src/program/generate.cpp:11027` と `engine/sycl/src/program/generate.cpp:6510`。
- 値判定、キャッシュ、release / prefetch 呼び出し、ログは `engine/src/program/generate.cpp:11026-11045` と `engine/sycl/src/program/generate.cpp:6509-6528`。
- CUDA/HIP 系の gate は `engine/src/program/generate.cpp:10997-11000`、SYCL 系の gate は `engine/sycl/src/program/generate.cpp:6483-6485`。
- arena-backed source の解放実装は `engine/src/core/expert_source.cpp:6980-6992`、`engine/sycl/src/core/expert_source.cpp:3606-3618`。
- Windows の file-backed source にある別設定と非 Windows の no-op は `engine/src/core/expert_source.cpp:3933-3982`、`engine/sycl/src/core/expert_source.cpp:1609-1645`。
- `STRATA_RSS_TRACE` の観測ログは `engine/src/program/generate.cpp:659-672`、`engine/sycl/src/program/generate.cpp:303-316`。
