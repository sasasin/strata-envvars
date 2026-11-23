# `STRATA_STOP_STAGES`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`--serve` 中の layer split で、入力 `STOP` を検知したときに後段 GPU stage の prompt 読み取りも止めるかを決める。未設定または `atoi` の結果が 0 以外なら、先頭 stage に設定した `should_stop` callback を全 `stages` の `Prefill` にコピーする。`0` なら後段にはコピーせず、先頭 stage だけが STOP を検知する。先頭 stage の callback はこの変数に関係なく設定される。単一 GPU では `stages` が空なので、この設定による後段への伝播はない。`--serve` の常駐エンジンでだけこの設定処理に入る（`engine/src/program/generate.cpp:11017-11038,11805-11828,15951-15960`）。

同じ設定を上書きする CLI 引数や別の環境変数はない。`STRATA_STOP_LAYERS` は後段への伝播の優先設定ではなく、STOP をチャンク内のレイヤー境界で確認するか、チャンク境界だけで確認するかを別に制御する（`engine/src/program/generate.cpp:15959-15960`; `engine/src/prefill/prefill.cpp:4970-4991`）。

これは prompt の各 stage に STOP の判定を伝える制御であり、生成・decode の判定方法を変えない。入力スレッドは `STOP` 行で stop flag を立て、prompt 読み取り失敗は server 側でキャンセルとして処理され、標準出力に `DONE ... cancel ...` が出る（`engine/src/program/generate.cpp:15932-15935,21487-21501,23470-23478`）。

## 値と判定

起動時の serve 初期化で `std::getenv` し、値が未設定なら有効、設定済みなら `std::atoi(v) != 0` で有効性を決める。文字列全体の検証、範囲確認、エラーや fallback のログはない（`engine/src/program/generate.cpp:15959-15960`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `--serve`、後段 stage への callback 伝播 | 有効 | `1`, `-1`, `2`, `1x`, ` 1`（`atoi` が 0 以外） | 空文字, `0`, `-0`, `0anything`, `true`, `x1`（`atoi` が 0） |

`atoi` は数値の先頭部分を読むため、後ろの文字列は検証されず、整数として読めない先頭なら 0 になる。空文字も 0 となる。コードに許容範囲や clamp はない。したがってこの変数の判定は実質「`atoi` の結果が非ゼロか」であり、`true` / `false` の文字列を真偽値として読むものではない（同上）。

## 有効になる条件

- 対象の `strata generate --serve` が layer split で動き、`stages` に後段 stage があること。単一 GPU では伝播先がない（`engine/src/program/generate.cpp:11805-11828,15959-15960`）。
- stdin で `STOP` が入力され、prompt 読み取りが進行中であること。STOP は入力スレッドが `stop_req` と `g_prompt_stop_req` を立てる（`engine/src/program/generate.cpp:15932-15935`）。
- チャンク途中のレイヤー境界でも停止を確認するかは別変数 `STRATA_STOP_LAYERS` が決める。同変数が未設定または `atoi` 非ゼロなら、各 `Prefill` はチャンク内で layer を進める際にも `should_stop` を確認する。`STRATA_STOP_LAYERS=0` ならその確認はなく、チャンク開始時の確認だけになる。後段 stage にこの確認を伝えるには、本変数も有効である必要がある（`engine/src/prefill/prefill.cpp:4379-4385,4970-4991`）。
- この分岐は `generate.cpp` の native CUDA/HIP serve 実装にある。別 backend や Python サーバーが同名を読む実装は、候補名の全参照検索では見つからなかった（直接参照は `engine/src/program/generate.cpp:15959`。同名の設定レジストリ記録は `terminal/data/settings-register.json:45792-45822`）。

## 実行時の詳細

値は常駐エンジンの serve 初期化中に一度読み、後段 stage の `sp.should_stop` に callback を代入する。その callback は先頭 stage の `stop_req` を読む関数である。リクエストごとに環境変数を読み直す処理はなく、実行中に環境を書き換えても伝播設定は変わらない（`engine/src/program/generate.cpp:15951-15960`）。

prompt の `Prefill` は各チャンク開始時に `should_stop` を確認する。`STRATA_STOP_LAYERS` が有効な場合は、チャンク内でも `LB` より後の各 layer の前に確認し、STOP を見つけると処理を止め、GPU work を同期して `err = "cancelled"` を返す。このため本変数が有効なら後段 stage も現在のチャンク内で止まれる。本変数を `0` にすると、後段 stage は callback を持たず、先頭 stage が後続チャンクを渡さなくなった後も、すでに渡されたチャンクの処理を続けうる（`engine/src/prefill/prefill.cpp:4379-4385,4970-4991`; `engine/src/program/generate.cpp:15955-15960`）。

prompt 読み取りがキャンセルされると serve は `cancelled` 状態にし、`DONE` 行の finish 欄は `cancel` になる。stderr には prompt の読取数と `(cancelled)` が出る。すでに完全に読み終えた prompt 境界があり、prompt cache が有効で checkpoint を保持できる場合は、その境界までの会話を保持する旨のログも出る（`engine/src/program/generate.cpp:21487-21501,23287-23303,23437-23478,23648-23659`）。

## ログと測定値

本変数自体の有効・無効を示すログはない。`STRATA_STOP_LAYERS` が有効なとき、STOP をチャンク途中で検出した stage は stderr に `strata prefill: stopped in the chunk from token %lld before layer %lld (STOP)` を出す。prompt 読み取りのキャンセルは stderr の `strata serve: prompt ... (cancelled)` と stdout の `DONE ... cancel ...` で観測できる（`engine/src/prefill/prefill.cpp:4977-4991`; `engine/src/program/generate.cpp:23470-23478,23648-23659`）。この変数に関する測定値は Strata の設計資料に見つからなかった。

## 根拠

- `engine/src/program/generate.cpp:11805-11828` — serve 専用の初期化範囲。
- `engine/src/program/generate.cpp:15932-15960` — STOP の受信、callback 設定、`STRATA_STOP_STAGES` の読み取りと後段への伝播。
- `engine/src/prefill/prefill.cpp:4379-4385,4970-4991` — チャンク開始・チャンク内での停止判定と停止時の同期、ログ。
- `engine/src/program/generate.cpp:21487-21501,23287-23303,23437-23478,23648-23659` — prompt キャンセル、会話保持条件、`DONE` と stderr の観測結果。
- `terminal/data/settings-register.json:45792-45822` — 候補レジストリの記録。挙動の根拠は実装コードに置いた。
