# `STRATA_ADAPT_SIGNAL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata serve` の adaptive overlap が、各レイヤーの適応コピー完了を verify window に知らせる方法を選ぶ。`copy` 系は stream 上の device-to-host コピーで pinned host memory にレイヤー番号を書き、`host` 系は stream 上の host function で完了番号を更新する。overlap 自体を有効化する変数ではなく、その有効化は `STRATA_ADAPT_OVERLAP` が担う。選択は `engine/src/program/generate.cpp:15113-15159` にある。

`docs/DETAILS.md:1214` の表は適用先を CUDA と記す一方、現行ソースの読み取り・方式選択部分に CUDA/HIP を分ける build guard はなく、OS (`_WIN32`) によって分岐する。Windows HIP では別途 overlap 自体が拒否される場合がある（`engine/src/program/generate.cpp:15148-15153,2259-2285`）。

通知はコピー完了をレイヤー単位でゲートに伝え、コピーが届く前に次の verify window が当該レイヤーの swap 済み expert を読むのを待たせる。overlap 中もソースコメントは通常時と同じ token と説明している（`engine/src/program/generate.cpp:2253-2258`）。

## 値と判定

`std::getenv` の結果を文字列全体や真偽値として parse せず、OS ごとに先頭文字だけを小文字 `c` / `h` と比較する（`engine/src/program/generate.cpp:15148-15153`）。

| ビルド／OS | unset | copy 通知になる値の例 | host function になる値の例 |
|---|---|---|---|
| Windows (`_WIN32`) | host function | `copy`, `c`, `copy-extra`（先頭が `c`） | 空文字、`host`, `h`, `1`, `true`（先頭が `c` ではない） |
| Windows 以外 | copy 通知 | unset、空文字、`copy`, `c`, `1`, `true`（設定値の先頭が `h` ではない） | `host`, `h`, `hello`（先頭が `h`） |

大文字小文字は区別される。空白の trim、文字列全体の一致、`0` / `1` の数値判定はしない。そのため、例えば `Copy` は Windows で copy にならず、` host` は Windows 以外で host にならない。`0` と `false` は Windows では host、Windows 以外では copy を選ぶ（同上）。

## 有効になる条件

- `STRATA_ADAPT_OVERLAP` が `adapt_overlap()` によって要求されていること。同関数は `STRATA_ADAPT_OVERLAP` の先頭文字が `1` かで opt-in を判定し、結果を関数内 `static` に保持する（`engine/src/program/generate.cpp:2269-2288`）。この変数の値は overlap を要求しない。
- サーバー側で adaptive tier が動作し、レイヤー分割、`--remote-expert-opt`、`--adapt-async`、`--pipeline-windows`、page-locked swap source、非ゼロの `STRATA_DMA_BATCH`、`STRATA_ADAPT_LAG` が 1 以外、または有効な `STRATA_ADAPT_NOWAIT` によって overlap が妨げられていないこと（`engine/src/program/generate.cpp:15122-15136`）。妨げられる場合は `STRATA_ADAPT_SIGNAL` による方式選択は実行上使われない。
- resident RAM mode では `STRATA_ADAPT_OVERLAP_RESIDENT` の先頭文字が `1` であること（同上）。
- `Verifier::set_adapt_gate` が成功し、device-planned layers（`STRATA_VERIFY_DEVICE_PLAN`）が有効でないこと（`engine/src/program/generate.cpp:15137-15144`、`engine/include/strata/core/verify.hpp:356-361`）。この検査に失敗した場合も通知方式はログ・セットアップに使われない。
- Windows HIP では `STRATA_ADAPT_OVERLAP=1` 自体が `STRATA_WIN_HIP_RISKY` の判定で拒否される場合がある。拒否時は overlap が無効なので、本変数の通知方式も適用されない（`engine/src/program/generate.cpp:2259-2285`）。

## 実行時の詳細

通知方式はサーバー起動時の adaptive overlap gate 設定時に読み取られ、その後のリクエストごとには読み直さない。関数内キャッシュはなく、読み取り元はプロセス環境の `getenv`。このためコード上、起動後の環境変更を反映する再読込経路はない（`engine/src/program/generate.cpp:15137-15153`）。CLI 引数による同等の上書きはこの箇所にはない。

copy 方式では、レイヤー番号の device 配列と pinned host 領域を確保し、各レイヤーの適応コピーの後ろに 4 byte の device-to-host copy を enqueue する。peer tier がある場合は同じ `sig_copy` を `PeerExperts::set_overlap_gate` に渡す。`cudaMalloc` / 初期化コピー / `cudaHostAlloc` のいずれかが失敗すると、この箇所は CUDA error を消費して主 device の `hland` を設定せず、レイヤーごとの通知は host function 側にフォールバックする。peer 側も同様に copy signal の確保に失敗すると host function を使う（`engine/src/program/generate.cpp:15157-15174`、`engine/src/core/peer_experts.cpp:495-519`）。

主 device のレイヤー通知 enqueue が失敗した場合、コードは CUDA error を消費して適応 stream を同期し、`agate.landed` を全レイヤー完了相当の値に進める。別の診断ログや終了処理はこの失敗分岐にはない。copy signal が有効で swap があるときは、その後 `cudaStreamQuery(adapt_stream)` も呼ぶが戻り値は無視する（`engine/src/program/generate.cpp:15471-15482,15495-15499`）。

## ログと測定値

gate を設定できる場合、host 方式は `strata serve: adaptive overlap signal: host functions` を stderr に出す。Windows で本変数が unset の場合は続けて ` (the Windows default, #2188; STRATA_ADAPT_SIGNAL=copy: a stream-ordered copy)` が付く。copy signal の確保成功時は `strata serve: adaptive overlap signal: stream-ordered copies (STRATA_ADAPT_SIGNAL=host: a host function)` を出す（`engine/src/program/generate.cpp:15154-15170`）。copy signal の確保失敗時はこの copy 方式ログは出ず、host 方式へのフォールバックもこの分岐では個別にログされない。

overlap が実際に有効なら、別途 `strata serve: adaptive overlap (STRATA_ADAPT_OVERLAP=0 turns it off): ...` の行が出る。要求された overlap が条件を満たさない場合は `strata serve: STRATA_ADAPT_OVERLAP=1 is off: <理由>`、要求されていない場合は `strata serve: adaptive overlap: off...` が出る（`engine/src/program/generate.cpp:15176-15186`）。この変数自体に関する測定値は、調査した現行ソースと `docs/DETAILS.md` に記載がないため記載しない。

## 根拠

- `engine/src/program/generate.cpp:15113-15159` — adaptive overlap gate、条件、対象変数の読み取りと値判定。
- `engine/src/program/generate.cpp:15160-15181` — copy signal の確保、peer tier への方式伝達、方式ログ。
- `engine/src/program/generate.cpp:15471-15499` — レイヤー通知の enqueue、失敗時の同期と gate 更新、stream query。
- `engine/src/core/peer_experts.cpp:495-519` — peer tier の copy signal 確保と host function への fallback。
- `engine/src/program/generate.cpp:2253-2288`、`engine/include/strata/core/verify.hpp:356-361` — overlap の opt-in と device-planned layers による gate 拒否。
