# `STRATA_DF2_LOG_MIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

DFlash2 drafter が会話の切替・再開用に保持する、現行 lineage 以外の過去 lineage（token history と activation row log）の退避上限を設定する。CUDA/HIP と SYCL は退避 log の合計サイズを MiB 単位で制限する。Metal は値を 10 で割った整数を退避 lineage の最大件数として使うため、同じ値でも意味と容量は backend ごとに異なる。現行 lineage の log や DFlash2 自体の有効化、draft 数を設定する変数ではない。読み取りは CUDA/HIP・SYCL の `Dflash2Drafter::init_ring_log` / `alloc` と Metal の `Window::df2_bind` 内で行う。ソース上の呼び出し経路は DFlash2 drafter の割当・bind 時であり、通常のサーバー／CLI 実行でも DFlash2 が選択・生成された場合に限られる（`engine/src/core/dflash2.cpp:305-344`; `engine/sycl/src/core/dflash2.cpp:168-224`; `engine/metal/src/engine/dflash2.inc:284-415`）。

## 値と判定

| 実装経路 | 未設定 | 設定時の変換・既定 | 例 |
|---|---|---|---|
| CUDA/HIP (`engine/src/core/dflash2.cpp`) と SYCL (`engine/sycl/src/core/dflash2.cpp`) | メンバー初期値の `256 MiB` | 値が空でなければ `atoi` の結果を `max(0, 値)` で下限 0 にし、`<< 20` して bytes にする | `1` → 1 MiB、`0` / `-1` / `abc` / `0anything` → 0 MiB、`12tail` → 12 MiB |
| Metal (`engine/metal/src/engine/dflash2.inc`) | `stash_max = 4` lineage | 値が設定されていれば `atoi(value) / 10` を整数件数として使用 | `256` → 25 lineage、`9` / `0` / `-10` / `abc` / 空文字 → 0 lineage、`35tail` → 3 lineage |

いずれも文字列全体の数値検証はせず、C/C++ `atoi` が読む先頭の符号付き十進整数部分を使い、後続の非数値文字は無視する。先頭の空白と符号は `atoi` の規則に従う。数値変換に失敗すると 0 になる。CUDA/HIP と SYCL は `e && e[0]` を条件にするので、明示的な空文字は未設定同様の既定値を保つ。Metal はポインタの有無だけを見るので、空文字は 0 件になる。Metal の整数除算は 10 未満を 0 件にする。`atoi` の表現可能範囲を超える入力の結果はコードで定義されていない。根拠: `engine/include/strata/core/dflash2.hpp:255`; `engine/sycl/include/strata/core/dflash2.hpp:168`; `engine/src/core/dflash2.cpp:825-828`; `engine/sycl/src/core/dflash2.cpp:215-216`; `engine/metal/src/engine/dflash2.inc:75-87,408`。

## 有効になる条件

- DFlash2 drafter が使われ、その backend の割当（CUDA/HIP、SYCL）または bind（Metal）まで進む必要がある。別の drafter や DFlash2 を使わない実行では読み取られない。
- CUDA/HIP と SYCL では `STRATA_DF2_RING_LOG` の先頭文字が `0` の場合、ring log を無効化する。CUDA/HIP はこの判定で初期化関数から戻るため `STRATA_DF2_LOG_MIB` も読み取らない。SYCL は `STRATA_DF2_LOG_MIB` を読むが、無効化された log では退避・再構築に使われない。空文字や `false` はこの条件を満たさない。Metal 実装では `STRATA_DF2_RING_LOG` を参照せず、Metal 側の lineage 復元には `STRATA_DF2_FUSE_H` の先頭文字 `0`、未 bind、未割当 row log、または `resume <= 0` という抑止条件がある（`engine/src/core/dflash2.cpp:822-830`; `engine/sycl/src/core/dflash2.cpp:215-224`; `engine/metal/src/engine/dflash2.inc:408-410,879-882`）。
- CUDA/HIP と SYCL では ring log 用 pinned host staging の確保が失敗すると log が無効になり、stderr に `strata dflash2: the ring log's staging does not fit in pinned memory: the log is off`（CUDA/HIP）または `strata dflash2: the ring log's staging does not fit in host memory: the log is off`（SYCL）を出す。この場合、値にかかわらず退避 log は使えない（`engine/src/core/dflash2.cpp:828-834`; `engine/sycl/src/core/dflash2.cpp:217-225`）。
- CUDA/HIP と SYCL で stash に入れる lineage は `log_on_` が真、上限が 0 以外、history が 128 token 以上、かつ log chunks がある場合に限られる。挿入後は最古の lineage から削除し、stash の合計 bytes が指定上限以下になるまで退避する。1 件だけでも上限を超える lineage は直ちに取り除かれ得る（`engine/src/core/dflash2.cpp:859-868`; `engine/sycl/src/core/dflash2.cpp:546-555`）。
- Metal は `stash_max <= 0` のとき lineage 復元処理を始めず、正数では過去 lineage の個数を上限とする。件数超過時は最も古く使われた stash を削除する。Metal の row log は `DF2_RING * N * 2` bytes のバッファである（`engine/metal/src/engine/dflash2.inc:75-87,879-882,914-930`）。

## 実行時の詳細

CUDA/HIP は `alloc()` から `init_ring_log()` を呼び、そこで環境変数を読み stash 上限を drafter インスタンスに保存する。SYCL は `alloc()` 中に同じ方法で読み取る。Metal は `df2_bind()` の bind 処理中に `stash_max` を設定する。したがって値はリクエストごとではなく、各 drafter の割当／bind 時に評価される。CUDA/HIP の batch slot clone も `clone_alloc()` から `alloc()` に進むため、その clone の初期化時に読み取る。実行中にプロセス環境を変更しても既存インスタンスの上限は再読込されない（`engine/src/core/dflash2.cpp:305-344,658-667,822-828`; `engine/sycl/src/core/dflash2.cpp:168-224`; `engine/metal/src/engine/dflash2.inc:284-415`）。

CUDA/HIP と SYCL では別の会話を再開するとき、現在の lineage を条件付きで stash に移し、要求の prefix と一致する退避 lineage があれば ring の不足行を log から再構築する。一致する lineage がない、stash 上限が 0、または上限超過で lineage が追い出されていれば、ring は新しい会話用に始まり、要求 window 内で欠けた行は cold として記録される。ring log が無効な場合は従来の prefix 判定経路を使う。再構築 scratch の確保失敗時は stderr に `strata dflash2: <error>: the ring starts over for this request` を出して ring を無効化し、その要求では全対象行を missing とする（`engine/src/core/dflash2.cpp:970-1034`; SYCL の対応処理 `engine/sycl/src/core/dflash2.cpp:648-710`）。

Metal では `df2_restore_lineage()` が条件に合う会話を stash から選び、行 log を用いて ring を復元する。選択した lineage は `resume` までの token history が一致し、row log が必要な window を覆う必要がある。上限は概数 MiB ではなく lineage 数として適用される（`engine/metal/src/engine/dflash2.inc:879-935`）。この変数が生成 token や候補選択を直接変更する処理は見つからず、変えるのは後続会話再開時に使える退避 lineage の保持量／件数である。

CLI 引数、設定ファイル、別の環境変数からこの上限を上書きする経路は見つからない。CUDA/HIP と SYCL では `STRATA_DF2_RING_LOG` が log 自体を無効にするため、実質的に本変数より先に適用される条件である。

## ログと測定値

`STRATA_DF2_LOG_MIB` の値や算出した上限を直接表示するログは見つからない。CUDA/HIP と SYCL では別途 `STRATA_DF2_RING_STATS` が設定されていれば request ごとに live log、parked lineage 数・bytes、再構築行・missing 行を stderr に出す。これは stash 上限の読み取りを確認するログではない（CUDA/HIP: `engine/src/core/dflash2.cpp:1018-1022`; SYCL: `engine/sycl/src/core/dflash2.cpp:696-700`）。Metal は `STRATA_DF2_STATS` が設定されていると復元時に `strata metal: DFlash2 lineage restored from the row log: ...` を stderr に出す。これも上限値を表示しない（`engine/metal/src/engine/dflash2.inc:984-986`）。本変数の効果に関する測定値は、調査対象のコード／設計資料から確認できなかった。

## 根拠

- CUDA/HIP の初期値、読み取り、log の有効化と stash 制御: `engine/include/strata/core/dflash2.hpp:255`; `engine/src/core/dflash2.cpp:305-344,822-868`。
- SYCL の初期値、読み取り、stash 制御と統計ログ: `engine/sycl/include/strata/core/dflash2.hpp:168`; `engine/sycl/src/core/dflash2.cpp:168-224,546-555,648-710`。
- Metal の件数変換と stash 上限・適用条件: `engine/metal/src/engine/dflash2.inc:75-90,284-415,879-935`。
- CUDA/HIP ring log と再開・cold 判定の説明: `engine/include/strata/core/dflash2.hpp:94-125`; 実装 `engine/src/core/dflash2.cpp:970-1034`。
