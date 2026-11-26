# `STRATA_SPLIT_MTP_BATCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

レイヤー分割時に、MTP drafter の prompt K/V を drafter 自身の逐次 pass で作る代わりに、最後の stage の prompt 処理 `Prefill::draft_kv` でバッチ計算する opt-in です。主な読み取りは `engine/src/program/generate.cpp` の chunk callback にあり、計算本体は `engine/src/prefill/prefill.cpp` にあります（`engine/src/program/generate.cpp:14763-14798`、`engine/src/prefill/prefill.cpp:2991-3000`）。

この切替は drafter の K/V 計算経路を変えます。通常の layer split では drafter 自身の pass が使われ、切替後にバッチ経路が成立すれば、その pass は省かれます。バッチ経路を試さない場合や辞退した場合は `mtp.prefill(...)` に戻ります。コードコメントは K/V の計算方式が異なるため draft 値が変わる可能性と、target の検証 token は変わらない旨を記しています（`engine/src/program/draft_kv_plan.hpp:3-7`）。

## 値と判定

主経路は `std::getenv` の結果を `split_env_on` に渡し、`value != nullptr && std::atoi(value) != 0` で判定します。数値文字列全体の検証はなく、`atoi` が読む先頭の整数部分が 0 以外なら有効です。未設定と空文字は無効、符号付き整数や先頭空白の後の非ゼロ整数は有効です。`1tail` は有効、`0tail` は無効、`true` / `false` はどちらも `atoi` が 0 を返すため無効です。`-1` も 0 以外なので有効です。整数として表現できないほど大きい値の扱いはこのコードで検査されません（`engine/include/strata/program/draft_kv_plan.hpp:16-18`）。

| 読み取り経路 | unset | 有効になる値の例 | 無効になる値の例 |
| --- | --- | --- | --- |
| MTP prompt K/V の経路選択 | 無効 | `1`, `2`, `-1`, ` 1`, `1tail`, `1.5` | 空文字, `0`, `0tail`, `true`, `false`, `off` |
| `STRATA_PIPED_CONCURRENT` の抑止判定 | 無効 | `1`, `-1`, `1tail`, `1.5` | 空文字, `0`, `true`, `off` |

後者も同じ C の `atoi(...) != 0` 型判定ですが、別の制御です。値が有効でも `STRATA_PIPED_CONCURRENT` が有効でなければ、この読み取りによる抑止は発生しません（`engine/src/program/generate.cpp:21024-21046`）。

## 有効になる条件

- prompt K/V の切替には MTP drafter が使われている必要があります。`use_mtp` が false なら plan はバッチを選びません（`engine/include/strata/program/draft_kv_plan.hpp:28-30`）。MTP は `o.mtp` が空でない場合に有効です（`engine/src/program/generate.cpp:12310-12314`）。
- 単一 GPU では、この環境変数に関係なく plan が `Prefill::draft_kv` を試します。変数が選択条件になるのは layer split の場合です（`engine/include/strata/program/draft_kv_plan.hpp:31-41`）。
- layer split では値が有効で、かつ drafter が first stage に置かれていない必要があります。`mtp_first` の場合、値を `plan` に渡す際に false にされるため、従来の drafter pass を使います（`engine/src/program/generate.cpp:14779-14780`）。
- layer split の最後の stage が token embedding を参照できる native embedding を持つ必要があります。ない場合はバッチを試さず、理由を一度 stderr に出して drafter 自身の pass に戻ります（`engine/include/strata/program/draft_kv_plan.hpp:25-41`、`engine/src/program/generate.cpp:14781-14798`）。
- `Prefill::draft_kv` が呼ばれても、`STRATA_MTP_BATCH=0`、非対応の K/V 配置（hybrid、paged/ring 以外、または `STRATA_MTP_BATCH_RING=0` の ring）、異なる device、必要 tensor や gather 可能な embedding の欠落、scratch 不足などで辞退します。辞退時は drafter 自身の pass に戻ります（`engine/src/prefill/prefill.cpp:3001-3037`、`3049-3052`）。
- Metal 実装では `Prefill::draft_kv` が即座に辞退する実装です。SYCL 側の `engine/sycl/src/program/generate.cpp` にはこの環境変数の読み取りがありません（CUDA 系と SYCL の参照比較: `engine/src/program/generate.cpp:14766`、`engine/sycl/src/program/generate.cpp:8626`、`13369`）。
- `STRATA_PIPED_CONCURRENT` が非ゼロで有効な場合、この変数も非ゼロなら pipelined concurrent read を使わず、「`STRATA_SPLIT_MTP_BATCH` が理由」と一度 stderr に出します。これは prompt K/V バッチ経路そのものの選択とは別の抑止条件です（`engine/src/program/generate.cpp:21024-21046`）。

## 実行時の詳細

prompt K/V 経路の値は `generate.cpp` の関数内 `static const bool` に初期化されるため、その static 初期化に到達したプロセスで一度読み取られます。同じ変数を concurrent-read の判定でも別途 `static const bool` 初期化内から読みます。したがって、各読み取りの初期化後にプロセス環境を変更しても、その読み取り結果には反映されません（`engine/src/program/generate.cpp:14763-14780`、`21024-21046`）。

各 chunk で `draft_kv::plan` が経路を決め、バッチを試す場合は layer split の `stages.back()->sp`（drafter の stage）の `draft_kv` を呼びます。成功時はその chunk の K/V をバッチ経路で作り、`mtp.prefill` は呼びません。試さない、または `draft_kv` が辞退した場合は `mtp.prefill` が使われます。いずれかでエラー文字列が立つと callback は false を返し、prompt 処理を続けません（`engine/src/program/generate.cpp:14775-14798`）。

バッチ計算側では、`STRATA_MTP_BATCH=0` なら辞退します。K/V は paged (`kv_mode == 0`) または許可された ring (`kv_mode == 2` かつ `STRATA_MTP_BATCH_RING` が `0` で始まらない) であること、hybrid でないこと、drafter と prefill が同じ device であることなどを確認します（`engine/src/prefill/prefill.cpp:3001-3037`）。リングでは slot 共有を避けるためバッチ行数にも上限を設け、scratch から得られる batch が 64 行未満なら辞退します（同 `:3047-3052`）。

バッチ処理中の upload 失敗や最終 stream 同期失敗は `err` に理由を設定して false を返します。この場合は通常の辞退時のように drafter pass へ fallback せず、chunk callback が false を返します（`engine/src/prefill/prefill.cpp:3105-3114`、`3161-3170`、`engine/src/program/generate.cpp:14784-14798`）。

## ログと測定値

layer split では、バッチ成功または理由付き辞退のどちらかをプロセス中一度だけ stderr に出します。成功時の書式は `strata serve: draft layer prompt K/V batched on CUDA%d (E-9 on the layer split, K/V mode %d)`、辞退時は `strata serve: STRATA_SPLIT_MTP_BATCH=1 declined, the drafter's own pass runs: %s` です。値が未設定/無効で通常 pass を選んだだけの場合、この箇所からはログを出しません（`engine/src/program/generate.cpp:14785-14795`）。

`docs/MULTI_GPU.md:149` は native pack と paged/ring K/V を条件として記載しており、ソースの条件と整合します。同ページ `:295` には 2x RTX 3080 20 GB、Xeon E5-2696 v4、UD-Q4_K_XL、`--layer-split 23` での prompt read の測定が記載されていますが、この文書ではその性能値を別環境へ一般化しません。`docs/BATCHING.md:273-277` も `STRATA_SPLIT_MTP_BATCH=1` のとき piped concurrent read を抑止する説明を含み、ソース分岐と整合します。

## 根拠

- `engine/include/strata/program/draft_kv_plan.hpp:16-41`
- `engine/src/program/generate.cpp:14763-14798`
- `engine/src/program/generate.cpp:21018-21046`
- `engine/src/prefill/prefill.cpp:2991-3037`
- `engine/src/prefill/prefill.cpp:3047-3052`
- `engine/src/prefill/prefill.cpp:3105-3114`
- `engine/src/prefill/prefill.cpp:3161-3170`
- `engine/sycl/src/program/generate.cpp:8626,13369`
- `docs/MULTI_GPU.md:149,295`; `docs/BATCHING.md:273-277`
