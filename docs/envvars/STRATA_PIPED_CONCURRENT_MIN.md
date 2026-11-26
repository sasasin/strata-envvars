# `STRATA_PIPED_CONCURRENT_MIN`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_PIPED_CONCURRENT=1` で有効にする実験的な prompt 読み取り並行処理について、並行読み取りに切り替える最小 token 数を指定する。指定値以上の長さの読み取り区間だけ、読み取り専用 thread と pipelined slot group の実行を並行させる。しきい値未満は通常の `run()` 経路で読み、値だけでは並行処理を有効にしない（`engine/src/program/generate.cpp:21024-21054`）。

## 値と判定

`std::getenv` で値を読み、設定されていれば `std::atoll` で整数変換した後、`std::max(0LL, ...)` で負値を 0 にする。文字列全体の妥当性検査やエラー処理はなく、`atoll` が読む数値部分が使われる。したがって空文字・数値で始まらない文字列は 0、`4096tail` は 4096、`-1` は 0 になる。先頭空白や符号は `atoll` の変換規則に従う。範囲外の数値に対する明示的な処理はない（`engine/src/program/generate.cpp:21050-21053`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA / HIP の pipelined groups 読み取り | 0（全 piece がしきい値を満たす） | 正の整数 `N`。piece の長さが `N` 以上なら並行経路 | 空文字、数値で始まらない値、`0`、負値は変換後 0 となり、しきい値としては全 piece を通す。`4096tail` のように数値の後ろに文字があっても数値部分を使う |

「全 piece を通す」は、この変数が長さ条件を制限しないという意味であり、他の有効条件を無視して並行処理を強制する意味ではない。`0` は無効化値ではなく、既定どおりの長さ下限なしを表す（`engine/src/program/generate.cpp:21047-21054`）。

## 有効になる条件

- `STRATA_PIPED_CONCURRENT` が `std::atoi` で 0 以外になる必要がある。未設定・空文字・`0`・数値で始まらない文字列はオフ、数値で始まり 0 以外に変換される文字列はオンとして扱う（`engine/src/program/generate.cpp:21024-21029`）。
- `--batch` が正、`--batch-groups` が 1 より大きく、layer split の stage が存在して `n_pipe > 1` である pipelined 経路が必要（`engine/src/program/generate.cpp:17529-17533`）。また、`STRATA_PIPED_READ_PIECE` が正で、piece 読み取りループに入る必要がある。未設定または 0 では pipelined の `piece_now()` が 0 となり `run(a0, b0)` に進むため、この並行経路は呼ばれない（`engine/src/program/generate.cpp:21279-21300`, `21343-21349`）。Strata の `docs/BATCHING.md` もこの機能を layer split と `--batch-groups` > 1 の経路として説明し、CUDA/HIP 向け、SYCL 非対応と記載している（`docs/BATCHING.md:247-256`, `279-281`）。
- 並行読み取りの設定が次のいずれかに該当すると `concurrent_read_off()` が最初の理由を返し、`STRATA_PIPED_CONCURRENT` はオフ扱いになる。`STRATA_PREFILL_HELP`、`STRATA_SPLIT_MTP_BATCH`、`STRATA_FS_SLOTS` は `atoi != 0` で判定される。ほかに `--pcie-mode dma`、helper cache（`--expert-cache-device1..3`。`--remote-expert-opt` は helper cache を経由するとき）、blob を stage する source（GGUF in place / unbuffered / `STRATA_IO_PREFETCH`）、GGUF source と arena source 以外の expert source が条件になる（`engine/src/program/generate.cpp:21027-21043`; `engine/include/strata/program/batch_read.hpp:30-53`）。オフ理由は stderr に一度 `strata batch: STRATA_PIPED_CONCURRENT is off beside <理由>` と出る。
- 画像を含む prompt（`req_imgs` が空でない場合）はこの並行読み取り分岐を通らない（`engine/src/program/generate.cpp:21054`）。しきい値以上でも以上の条件が満たされなければ機能は動かない。

## 実行時の詳細

この値は `run_conc` lambda 内の関数ローカル `static const int64_t` で、同 lambda が最初に呼ばれたときに一度だけ読む。その後の request や piece では process 内の値を再利用するため、初回評価後の環境変更は反映されない。CLI 引数や設定ファイルでこの値を上書きする経路はない（`engine/src/program/generate.cpp:20902-20905`, `21047-21054`）。

比較対象は全 prompt 長ではなく、その呼び出しの `[a0, b0)` に対応する読み取り区間の長さ `b0 - a0`。`run_conc(q, r)` は piped read piece ごとに呼ばれ、piece のサイズは `STRATA_PIPED_READ_PIECE` を chunk 単位に丸めた値に基づく。そのため piece がしきい値未満なら、その piece は `run(q, r)` で逐次的に読み、以上なら prompt を reader thread で読みながら slot group を pump する（`engine/src/program/generate.cpp:21054`, `21284-21286`, `21343-21349`）。

並行経路では reader thread の終了を待って join し、pipeline を drain する。読み取り中に待機 request が `BYIELD` を要求した場合は次の chunk 境界で読み取りを止め、通常の give-way 処理へ渡す。しきい値未満の piece はこの変数によって従来の piped piece 処理へ戻るだけで、prompt の値や token の生成方法を直接変更する処理ではない（`engine/src/program/generate.cpp:21176-21216`, `21243-21275`）。

reader thread で prompt read が失敗すると、そのエラー文字列を `read_err` に渡し、`run_conc` は失敗として返す。request 側は yield/cancel でない失敗について `strata serve: <理由>` を stderr、`ERR <理由>` を stdout に出し、通常は終了コード 1 で戻る。CUDA error が残っている場合は flush 後に `_Exit(1)` する（`engine/src/program/generate.cpp:21191-21202`, `21270-21272`, `21593-21604`）。

## ログと測定値

並行経路では stderr に `strata batch: read N tokens on a thread of its own in X ms (concurrent, to Q of T); the slots decoded R rows meanwhile (S rows/s; stage k: W windows, H ms host each)` の形式で出力する。しきい値未満の場合に `STRATA_PIPED_CONCURRENT_MIN` 固有のログはなく、通常の piped piece のログが出る。無効化条件に該当した場合の理由ログは「有効になる条件」を参照（`engine/src/program/generate.cpp:21263-21269`, `21373-21387`）。

`docs/BATCHING.md:283-303` には `STRATA_PIPED_CONCURRENT=1` の測定があるが、`STRATA_PIPED_CONCURRENT_MIN` のしきい値比較を評価した測定ではないため、この変数の性能効果としては記載しない。

## 根拠

- `engine/src/program/generate.cpp:21024-21054` — 並行処理の環境値、無効理由、最小 token 数の parse と判定。
- `engine/src/program/generate.cpp:17529-17533`, `21279-21300`, `21343-21349` — piped 条件、piece 読み取り設定、piece ごとの呼び出し。
- `engine/include/strata/program/batch_read.hpp:30-53` — 並行処理を無効にする構成と理由。
- `engine/src/program/generate.cpp:21176-21275`, `21263-21269` — thread 実行、give-way、ログ。
- `engine/src/program/generate.cpp:21191-21202`, `21593-21604` — 読み取り失敗の通知と request の出力・終了処理。
- `docs/BATCHING.md:247-281` — 機能の利用条件と対応 backend の説明。
