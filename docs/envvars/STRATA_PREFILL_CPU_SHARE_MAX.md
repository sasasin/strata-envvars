# `STRATA_PREFILL_CPU_SHARE_MAX`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

CPU prefill share が適用される prompt chunk の上限を token 数で指定します。CPU share が有効な場合、この上限未満の chunk は routed expert を GPU へ一括 stream せず、routing 後に必要な expert を stage する経路を使います。CPU pool が取得でき、他の stage が使っていないときに限り、GPU が stream する代わりに CPU pool が一部の expert を処理します。上限以上の chunk は通常の stream-all 経路です。

この変数自体が CPU share を有効化するわけではありません。share の値は `STRATA_PREFILL_CPU_SHARE` で決まり、対象関数で `applies` が真のとき、かつ share が有効なときだけ上限が適用されます。

## 値と判定

`cpu_share_max()` は `std::getenv` の文字列を `std::atoll` で変換し、下限を 1024 に制限します。文字列全体の妥当性検査はしません。

| 状態・値 | 上限 |
|---|---:|
| 未設定 | 通常 3072。後述の「既定で share が armed」の特例では 1024 |
| `1024` 未満の整数、負数、`0` | 1024 |
| `3072` | 3072 |
| `4096` など | 指定された整数 |
| 空文字、数値に変換できない文字列 | `atoll` が 0 を返すため 1024 |
| 数字の後ろに文字が続く値（例 `2048xyz`） | 数字の prefix を変換し 2048 |

空白や符号などの扱いは `atoll` の変換に従います。上限値に上限 clamp はありません。変換結果が `int64_t` の範囲を超える入力の挙動は、このコードでは別途検査していません。

「既定で share が armed」の経路では、`STRATA_PREFILL_CPU_SHARE` が未設定で `g_share_default` が真、かつこの変数も未設定なら、内部の 3072 ではなく 1024 を返します。これは測定済みの既定動作を 1024 token 未満に限定する処理です。`STRATA_PREFILL_CPU_SHARE=auto` または数値を明示した場合はこの特例に該当せず、上限未設定なら 3072 です。`STRATA_PREFILL_CPU_SHARE_MAX` を明示すると、既定経路でもその値（最低 1024）が使われます。

## 有効になる条件

- `Prefill::arm_cpu_share(applies, ...)` で `applies` が真で、`STRATA_PREFILL_CPU_SHARE` の判定結果が 0 でないこと。上限は `applies && cpu_share_on()` の場合だけ `g_stream_min_share` に設定されます。
- `STRATA_PREFILL_CPU_SHARE` が未設定なら通常は share 無効です。既定で有効化されるのは既定対象経路が `by_default` として arm し、CPU share の適用対象があり、既定 share のメモリ条件を通る場合です。generate の既定対象は単一 GPU、CPU pool 有効、batch slots なし等の経路です。既定有効化は HIP ビルドでは行われません。
- chunk が上限未満でも、CPU pool がない、pool の同時利用を取得できない、native expert layout でない、multi-GPU peer 経路である、expert source がない、または share 用 pinned buffer の確保に失敗する場合は CPU 処理になりません。buffer 確保失敗時は stderr に `prefill: the CPU share is off for this run: ...` を出し、その実行では GPU が全 expert を処理します。
- `STRATA_PREFILL_STREAM_MIN` が設定され、`atoll` 値が 0 以上なら、その値が `stream_all_min()` の優先値になります。この場合、`STRATA_PREFILL_CPU_SHARE_MAX` が設定する境界より `STRATA_PREFILL_STREAM_MIN` が優先されます。

## 実行時の詳細

環境値から計算した値と「変数が設定されていたか」は、それぞれ `cpu_share_max()` 内の function-local `static` に初回呼び出し時に保存されます。したがって初回呼び出し後にプロセス環境を書き換えても再評価されません。既定経路の 1024 特例は `g_share_default` と `STRATA_PREFILL_CPU_SHARE` の値にも依存します。

上限は `g_stream_min_share` に入り、prompt の stream-all 判定および ring の sizing 判定で使われます。通常の既定境界も 1024 token です。share が arm されたときは、上限未満の chunk が `stream_all` でなくなり、CPU share が適用可能なら GPU が stream する非 resident expert の一部を CPU pool に回します。chunk が境界以上なら stream-all 側に入り、CPU share による staged-chunk 処理は適用されません。API コメントにも、share が適用される staged chunk はこの上限未満で、buffer sizing より前に上限を設定する必要があるとあります。

## 根拠

- `src/prefill/prefill.cpp:163-167`: `STRATA_PREFILL_STREAM_MIN` と share 上限から stream-all 境界を決める。
- `src/prefill/prefill.cpp:184-208`: `STRATA_PREFILL_CPU_SHARE` の値、CPU share 上限の変換、既定 1024 特例。
- `src/prefill/prefill.cpp:1960-1972`: HIP の既定 arm 除外と、share が有効な場合の上限設定。
- `src/prefill/prefill.cpp:1103-1105,2337-2351,3137-3148`: init 時の arm、chunk の stream-all 判定、CPU pool と buffer fallback。
- `src/program/generate.cpp:7202-7229,7281-7289,13154-13159`: 既定 share のメモリ条件、serve/generate の arm 条件。
- `include/strata/prefill/prefill.hpp:174-188`: API コメント上の適用対象、上限、chunk 境界。
- `docs/DETAILS.md:1597-1613`: 文書の説明。既定 share の上限を 1024、明示 share の標準上限を 3072 とし、1024 未満を維持する設定例を示す。コードでも既定有効経路では 1024、明示 share 時は未設定なら 3072 となる。
