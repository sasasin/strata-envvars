# `STRATA_IQ3S_MT1`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU の native expert 経路で、IQ3_S の gate/up 行が 1 token だけを処理するときにも AVX2 の multi-token 行 kernel を使うための opt-in です。対象の IQ3_S は `gu_type == 21` で識別されます。通常は `STRATA_IQ_MT_MIN` 未設定時に 2 token 以上で multi-token kernel を選び、1 token は ggml-cpu の dot に進みます。この変数が条件を満たすと IQ3_S の閾値だけを 1 にし、1 token も `iq256_gu_rows` に送ります。コメントはこの変更で単独 token の丸めが変わると説明しています。CPU native expert を通らない GPU 専用処理や Q2_0 専用行処理には作用しません。読み取りと閾値決定は `native_gu_mt_min()`、行 kernel の選択は `native_gu_rows_impl()` です（`engine/src/kernels/cpu/native_expert.cpp:540-556,654-704`）。

## 値と判定

この変数自身は `std::getenv(...) != nullptr` の有無判定だけで、値の文字列や数値を parse しません。unset だけが無効で、空文字、`0`、`1`、`true`、`false`、`0anything` を含む設定済み文字列はすべて opt-in 判定を通ります。ただし次の実行条件も必要です（`engine/src/kernels/cpu/native_expert.cpp:545-556`）。

| 条件 | `STRATA_IQ3S_MT1` unset | 設定済み（例） | 機能が無効になる例 |
|---|---|---|---|
| `STRATA_IQ_MT_MIN` も unset、AVX2 対応、AVX-512 なし、gather 条件成立 | IQ3_S の閾値は既定の 2 | 空文字、`0`、`1`、`true` など値を問わず閾値 1 | この列の条件のどれかが不成立なら既定の閾値 2 |
| `STRATA_IQ_MT_MIN` が設定済み | その変数の `atoi` 結果を閾値に使用 | 本変数を設定しても本変数による上書きはない | `STRATA_IQ_MT_MIN` の設定が優先（空文字や非数値なら `atoi` の結果は 0） |

`STRATA_IQ_MT_MIN` の値は `atoi` で変換され、未設定なら 2 です。存在すれば値が何であっても `STRATA_IQ3S_MT1` 側の特例を止めます。gather 判定に使う `STRATA_IQ256_GATHER` は unset または空文字なら自動判定値 `-1`、それ以外は `atoi(v) != 0` により 1/0 になります。そのため非空の無効文字列も 0 となって gather 条件を満たしません（`engine/src/kernels/cpu/native_expert.cpp:545-556`; `engine/src/kernels/cpu/expert_layout.cpp:310-316`）。

## 有効になる条件

- Strata が native expert CPU kernel を含むビルドであること。x86 では `native_expert.cpp` と AVX2 IQ kernel が native-experts 構成に追加されます。native experts を含まない構成の stub は閾値 2 を返します（`engine/cmake/backends/cpu.cmake:303-317`; `engine/src/kernels/cpu/expert_layout.cpp:490-498`）。
- `STRATA_IQ_MT_MIN` が未設定であること。本変数を設定すると IQ3_S 特例より優先されます（`engine/src/kernels/cpu/native_expert.cpp:545-556`）。
- x86 CPU/OS が `cpu_avx2_ok()` を満たすこと（AVX2、FMA、AVX、F16C と OS の AVX 状態保存）かつ `STRATA_NO_IQ256` が未設定であること（`engine/src/kernels/cpu/expert_layout.cpp:206-238`; `engine/src/kernels/cpu/native_expert.cpp:554-555`）。
- `cpu_avx512_ok()` が false であること。AVX-512 対応 CPU には本特例を適用しません（`engine/src/kernels/cpu/native_expert.cpp:554-555`）。
- `STRATA_IQ256_GATHER` が `0` 相当でなく、`cpu_gather_fast()` が true であること。自動判定では ISA cap が AVX-512 tier 以上で、Intel CPU が AVX-VNNI を報告し、列挙された E-core-only 型番でないことを要求します。明示的に `STRATA_IQ256_GATHER` を非ゼロにしても `cpu_gather_fast()` 条件は省略されません（`engine/src/kernels/cpu/expert_layout.cpp:310-338`; `engine/src/kernels/cpu/native_expert.cpp:554-555`）。
- 対象の native expert の gate/up 量子化型が IQ3_S（`gu_type == 21`）であること。閾値 1 に変えるのはこの型だけです（`engine/src/kernels/cpu/native_expert.cpp:554-556`）。
- 対象の gate/up 呼び出しで `nt == 1` であることが今回の opt-in の差分です。複数 token の呼び出しでは既定の閾値 2 と同じく条件を満たし、multi-token kernel に進みます（`engine/src/kernels/cpu/native_expert.cpp:654-655,685-703`）。

## 実行時の詳細

CPU pool の gate/up 行処理は `native_gu_rows()` または window-invariant 版から `native_gu_rows_impl()` に入り、`native_gu_mt_min(f.gu_type)` で閾値を取得します（`engine/src/kernels/cpu/pool.cpp:1290-1296`; `engine/src/kernels/cpu/native_expert.cpp:898-910`）。閾値が 1 になった IQ3_S は `nt >= mt_min` を満たし、AVX2 が有効なら `iq256_gu_rows()` に進みます。ここでは `STRATA_NO_IQ256` が未設定であることも dispatch 側で確認されます（`engine/src/kernels/cpu/native_expert.cpp:685-703`）。これは gate/up の行計算経路の選択です。down 行を同様に変更する分岐はありません。

`STRATA_IQ_MT_MIN`、この変数、CPU 判定値、gather 判定は関数内 static に保存されます。初回の `native_gu_mt_min()` 評価以降にプロセス環境を変更しても再評価されません（`engine/src/kernels/cpu/native_expert.cpp:545-555`; `engine/src/kernels/cpu/expert_layout.cpp:310-338`）。CLI 引数による上書きはこの関数にありません。IQ3_S の 1-token 丸めが変わる点はコメントと DETAILS に記されていますが、当該分岐に有効化ログ、警告、変数固有のエラーまたは終了経路はありません（`engine/src/kernels/cpu/native_expert.cpp:553-556`; `docs/DETAILS.md:1281`）。

## ログと測定値

この設定分岐はログを出しません。`docs/DETAILS.md` は `STRATA_IQ3S_MT1=1` を「AVX-512 なしの Alder Lake 以降で IQ3_S に 1 token 用 multi-token kernel を使う」と記載します。ソースの CPU probe は Intel AVX-VNNI と CPU 型などを判定するため、実際の適用条件は単なる世代名より上記の条件が優先です。ここでは変数固有の測定値を新たに記載しません（`docs/DETAILS.md:1281`; `engine/src/kernels/cpu/expert_layout.cpp:320-338`）。

## 根拠

- `engine/src/kernels/cpu/native_expert.cpp:540-556` — 閾値、優先順位、変数の設定有無、CPU・他変数条件。
- `engine/src/kernels/cpu/native_expert.cpp:654-705` — token 数と量子化型による行 kernel dispatch。
- `engine/src/kernels/cpu/pool.cpp:1290-1296` — CPU pool の gate/up 行処理から native kernel への呼び出し。
- `engine/src/kernels/cpu/expert_layout.cpp:206-238,310-338,490-498` — CPU ISA 判定、gather 設定・自動判定、native-experts 無効時の stub。
- `engine/cmake/backends/cpu.cmake:303-317` — native expert ソースと x86 ISA kernel の build 登録。
- `docs/DETAILS.md:1281` — Strata の設定資料との照合。
