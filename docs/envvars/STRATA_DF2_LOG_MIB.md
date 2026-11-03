# `STRATA_DF2_LOG_MIB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DFlash2 の ring log が保持する、別 lineage のログ stash の上限を指定します。CUDA/HIP 共通実装と SYCL 実装では値を MiB として解釈し、stash に保持するログの実バイト数を制限します。Metal は同じ環境変数を stash lineage 件数へ変換して使うため、単位と既定値が異なります。

この設定が使われるのは DFlash2 drafter が初期化される経路です。通常の generate では `--draft dflash2` と `--draft-model` などの開始条件を満たして drafter が load/bind される場合に関係します。serve の `--draft auto` では DFlash2 がロードされていて、リクエストが DFlash2 を選んだ場合に stash が再利用されます。環境変数が DFlash2 のロード自体を有効化したり、CLI の値で上書きされたりする処理は確認できません（`src/program/generate.cpp:987-1001,5319-5333,6769-6777,15190-15212`）。

## 値と判定

| 実装 | 未設定 | 空文字 | 設定値の変換と効果 |
|---|---|---|---|
| CUDA/HIP (`src/core`)、SYCL | 既定 `256 MiB` | 読み取り条件 `e && e[0]` を通らず既定値のまま | `atoi` の結果を `max(0, result)` で負値なら 0 にし、MiB に変換。0 は stash を無効化 |
| Metal | 既定 `4` lineage | `atoi("")` により 0 件 | `atoi(value) / 10` を整数除算した件数を上限にする。上限が 0 以下なら lineage restore は早期 return する |

標準/SYCL 実装では `atoi` を使い、文字列全体の妥当性検証はありません。先頭空白と符号は `atoi` の変換規則に従い、数値の後ろにある文字は変換結果に影響しません（例: `128MiB` は 128 として扱われます）。数値に変換できない文字列は 0 となり、stash を無効にします。負数も 0 に clamp されます。`atoi` の `int` 範囲外の入力の結果は保証されません。

Metal は未設定時だけ 4 件で、設定された場合は変換後の値を 10 で割ります。例えば `256` は 25 件、`9` や `0` は 0 件です。ここでも文字列全体の検証やエラー報告はなく、数値に変換できない文字列は 0 件になります。Metal の値は MiB 予算ではありません。

## 有効になる条件

- CUDA/HIP と SYCL では ring log が有効であることが必要です。`STRATA_DF2_RING_LOG` の先頭文字が `0` なら ring log を無効化し、この変数の budget による stash 保持も行われません（`src/core/dflash2.cpp:746-759`; `sycl/src/core/dflash2.cpp:211-224`）。
- `--draft dflash2` または DFlash2 をロードする serve 経路が選択され、DFlash2 が正常に初期化・bind されていることが必要です。失敗時に MTP fallback を使う場合、DFlash2 の stash は使われません（`src/program/generate.cpp:5319-5333,6769-6817,11161-11173`）。
- Metal では `df2_restore_lineage()` が bound 状態、fused-H、row log buffer、正の `resume` を要求します。さらに `stash_max <= 0` なら lineage restore を行いません（`metal/src/engine/dflash2.inc:877-880`）。
- コマンドライン引数や他の環境変数による数値の優先上書きは見つかりません。標準/SYCL で別変数が ring log 全体を切る場合は `STRATA_DF2_RING_LOG` です。Metal の `d.fuse_h` は `STRATA_DF2_FUSE_H` で決まり、fused-H が無効ならこの stash restore の条件を満たしません（`metal/src/engine/dflash2.inc:406-409,877-880`）。

## 実行時の詳細

CUDA/HIP 実装は `Dflash2Drafter::alloc()` から `init_ring_log()` を呼び、SYCL は `alloc()` 内で値を読みます。どちらも DFlash2 の割当て時に一度読み、その後の `begin_request()` では保存済みの `stash_budget_` を使います。プロセス実行中に環境を書き換えても、既に初期化した drafter の予算は変わりません。既定値はクラスの `stash_budget_ = 256ull << 20` です（`src/core/dflash2.cpp:245-284,746-752`; `include/strata/core/dflash2.hpp:251-255`; `sycl/src/core/dflash2.cpp:167-216`; `sycl/include/strata/core/dflash2.hpp:161-165`）。

標準/SYCL 実装は別 lineage に切り替えるとき、または分岐で古い lineage を保持するときに stash へ追加します。履歴が 128 token 未満、ログが空、ring log が OFF、または budget が 0 なら追加しません。追加後に stash の合計ログ bytes が budget を超える間、古いものから取り除きます。後続リクエストが一致する履歴を持つ stash を見つけた場合は、それを現在の lineage に戻し、利用可能な logged rows から ring を再構築します（`src/core/dflash2.cpp:783-792,902-929`; `sycl/src/core/dflash2.cpp:526-534,636-664`）。

Metal は bind 時に値を読み、`stash_max` を設定します。復元処理では、stash の lineage 数が上限を超えたとき、最も古く使われた lineage から削除します。値が 0 以下なら restore 処理全体を早期 return します（`metal/src/engine/dflash2.inc:403-410,877-880,912-929`）。

この環境変数専用のログや警告、終了経路はありません。標準/SYCL の ring 統計出力が `STRATA_DF2_RING_STATS` で有効なら、各 request の stash 数と MiB 表示が stderr に出ます（`src/core/dflash2.cpp:942-946`; `sycl/src/core/dflash2.cpp:676-680`）。Metal では復元成功時に `STRATA_DF2_STATS` が有効なら、復元行数と stash 件数を stderr に出します（`metal/src/engine/dflash2.inc:982-984`）。

## 根拠

- 候補名の実読み取りは `src/core/dflash2.cpp:751`、`sycl/src/core/dflash2.cpp:215`、`metal/src/engine/dflash2.inc:406` の3箇所です。その他の直接参照は候補一覧、実装コメント、テストの設定値でした。
- 標準/SYCL の MiB budget と stash eviction: `include/strata/core/dflash2.hpp:251-255`, `src/core/dflash2.cpp:746-792,902-929`, `sycl/include/strata/core/dflash2.hpp:161-165`, `sycl/src/core/dflash2.cpp:211-224,526-534,636-664`。
- Metal の件数変換と LRU eviction: `metal/src/engine/dflash2.inc:76-89,403-410,877-929`。
- DFlash2 の CLI 起動条件と serve での選択: `src/program/generate.cpp:987-1001,5319-5333,6769-6817,15190-15212`。
- `docs/DETAILS.md` を含む Strata の文書に、この環境変数の追加仕様や測定値は見つかりませんでした。コメントにある「default 256 MiB」は標準/SYCL の初期値と一致しますが、Metal 実装の未設定時は 4 lineage です。
