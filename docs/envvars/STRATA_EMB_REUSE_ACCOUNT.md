# `STRATA_EMB_REUSE_ACCOUNT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prompt 用 device buffer の必要量を見積もる `Prefill::bytes_needed_impl` で、実際の `carve` では embedding buffer `emb` と同じアドレスを使う half-output buffer `bo` の分を見積もりから差し引くかを切り替える。未設定時は `bo` 分を余分に数える互換動作で、`STRATA_EMB_REUSE_ACCOUNT=1` ならその重複分を数えない。実 buffer の配置を変える設定ではなく、実際の配置では `bo` は常に `emb` を指す。見積もりを使う chunk 選択や expert-cache loan 計算が変わり得るため、結果として prompt chunk や prompt path に借りる cache slot 数が変わることがある。`engine/src/prefill/prefill.cpp:825-831, 3729-3747, 2776-2779`。

変数名を読む Strata 所有ソースは `engine/src/prefill/prefill.cpp` の `emb_reuse_account()` だけで、同関数の戻り値は `bytes_needed_impl` から参照される。`generate.cpp` は変数を直接読まず、`Prefill::bytes_needed` の値を slot 換算や chunk が収まるかの判定に使う（例: `engine/src/program/generate.cpp:11133-11156, 11373-11397`）。

## 値と判定

`std::getenv` が返す値の先頭 1 文字だけを検査し、先頭が文字 `1` なら有効。それ以外は無効。数値 parse、文字列全体の比較、空白除去、大文字小文字変換はしない。`bytes_needed_impl` を最初に呼んだ時点で関数内 `static const bool` に保存され、同じプロセスで環境を後から変更しても再評価されない。`engine/src/prefill/prefill.cpp:829-831`。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| `emb_reuse_account()` の評価 | `bo` 分を見積もりに加算 | `1`, `1anything`, `11`, `1 `（先頭が `1`） | 空文字、`0`, `true`, `TRUE`, ` 1`, `01` |

したがって境界は数値の 1 ではなく先頭文字である。`11` は有効、`-1` は無効。無効値専用の警告や fallback はなく、未設定と同じ見積もりになる。値の判定は `engine/src/prefill/prefill.cpp:829-831`。

## 有効になる条件

- engine が `Prefill::bytes_needed_impl` を呼び、その返す必要量を使う場合にだけ見積もりへ反映される。`bytes_needed` と `bytes_needed_owned` はどちらも同じ実装へ進む（`engine/src/prefill/prefill.cpp:3707-3729`）。
- 通常の `--prefill auto` では、VRAM に収まる chunk と cache loan を走査する計算にこの見積もりが使われる。例えば serve の slot 換算は `bytes_needed` を受け、chunk scan はその値から ring/cache に必要な slot 数を判定する（`engine/src/program/generate.cpp:11133-11156, 11373-11397`）。別経路でも `bytes_needed` / `bytes_needed_owned` が使われるため、自動 chunk 選択に限った設定ではない。
- `--prefill N` など明示 chunk の値そのものをこの環境変数が上書きする処理はない。ただし、その chunk の buffer fit、loan、cache 予算を `bytes_needed` で調べる経路では見積もりに影響し得る（例: `engine/src/program/generate.cpp:12779-12789`）。他の条件や予算が上限なら、見積もりを減らしても選択結果が変わらない場合がある。
- `bytes_needed_impl` のこの分岐自体には OS/backend の `#if` ガードがない。prompt buffer を CUDA 系 allocator で確保する共通 prefill 経路で使われる。`Prefill::init` が Metal 用に早期 return する分岐もあるため、Metal でこの見積もりが呼ばれる経路への適用は、この分岐だけからは断定できない（`engine/src/prefill/prefill.cpp:2443-2456, 3718-3747`）。

## 実行時の詳細

`Prefill::bytes_needed` は chunk サイズ `T` ごとに scratch、prompt 中間 buffer、各種表、ring などの byte 数を `Alloc` の count-only モードで積算する。`bo` は carve 時に `m.bo = m.emb` と alias されるが、見積もりは既定で `f(T * N)` をもう一度加算する。環境変数が有効ならその加算を省く。このため byte 見積もりは最大で当該 chunk の `T * N * sizeof(float)` 相当だけ小さくなり、256-token 単位の chunk 候補や借りる cache slot 数を変え得る。実 allocation は引き続き `carve` の既存レイアウトで行われる（`engine/src/prefill/prefill.cpp:2776-2779, 3718-3747`）。

値は `bytes_needed_impl` の最初の呼び出しで初期化される関数内 static にキャッシュされる。main 起動時に必ず読むわけではなく、最初に見積もりが必要になった時に読み、プロセス中の変更は反映されない（`engine/src/prefill/prefill.cpp:829-831`）。

これはメモリ見積もりの設定で、生成 token の計算式を直接切り替えない。一方、見積もりから選ばれた chunk が変われば prompt の分割・丸めが変わり得る。Strata の資料は RTX 3060 / IQ3_XXS の例として chunk 6400→6656、借用 slot 1652→1670、prompt 約 +3.9% と記しているが、測定値はこの構成の資料上の値であり、他環境での効果を保証しない。また資料自身が KL 測定なしとしている（`docs/DETAILS.md:1269, 1723`）。

この変数専用のログ、警告はない。serve の自動 chunk ログ（`strata serve: prompt chunk auto: ...`）や借用 slot のログは、選ばれた値を間接的に観測できる（`engine/src/program/generate.cpp:12747-12764, 12924-12932`）。見積もりが実 allocation を保証するものではなく、実際に chunk buffer の carve が失敗すれば `Prefill::init` が error 文字列 `prefill: device buffers for a chunk of ... tokens do not fit (...)` を設定して `false` を返す。serve はこの種の失敗時に小さい chunk で再試行し、再試行できない場合は stderr に `strata serve: <error>` を出して終了コード 1 を返す（`engine/src/prefill/prefill.cpp:2738-2746`, `engine/src/program/generate.cpp:13039-13041, 13102-13140`）。

## 根拠

- `engine/src/prefill/prefill.cpp:825-831` — 設計コメントと getenv / static cache。
- `engine/src/prefill/prefill.cpp:2776-2779` — `bo` が `emb` を alias。
- `engine/src/prefill/prefill.cpp:3707-3747` — 見積もり API と `bo` 分の加算条件。
- `engine/src/program/generate.cpp:11133-11156, 11373-11397` — byte 見積もりから slot 数・chunk scan を計算。
- `engine/src/program/generate.cpp:12747-12764, 12924-12932` — serve の間接観測ログ。
- `engine/src/prefill/prefill.cpp:2738-2746`, `engine/src/program/generate.cpp:13039-13041, 13102-13140` — buffer carve 失敗時の error、serve の再試行・stderr・終了経路。
- `docs/DETAILS.md:1269, 1723` — 条件付きの既存測定記録（コードから測定を再現・検証したものではない）。
