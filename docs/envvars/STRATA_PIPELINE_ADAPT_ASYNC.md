# `STRATA_PIPELINE_ADAPT_ASYNC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は非同期 adaptive tier を起動する設定ではなく、`--adapt-async 1` が要求されているとき、`--pipeline-windows 2` と併用できるかを止めるゲートである。値がゼロに変換されると、pipeline windows 2 の場合に `--adapt-async` を無効化し、blocking adaptive tier を残す。それ以外の値ではこの組み合わせを許す。環境変数を読んでいるのは `engine/src/program/generate.cpp` の `generate` 処理である（`engine/src/program/generate.cpp:11796-11811`）。

この変数単独では pipeline windows、adaptive tier、または非同期処理を有効にしない。`--adapt-async` の既定値は 0 であり、これを有効にするには通常 `--adapt-async 1` が必要である（`engine/src/program/generate.cpp:1060-1062,4061`）。

## 値と判定

関数内 `static const bool` の初期化で `std::getenv` を呼び、未設定なら `true`、設定済みなら `std::atoi(v) != 0` を使う。文字列全体の検証はなく、`atoi` が先頭から変換できる整数部分で判定する。したがって空文字・数字で始まらない文字列は 0 になり、整数として 0 以外に変換される値は許可になる（`engine/src/program/generate.cpp:11796-11800`）。

| 条件 | unset | 許可になる値の例 | ゲートを閉じる値の例 |
| --- | --- | --- | --- |
| 共通 | 許可 | `1`, `2`, `-1`, `1junk`, ` 1` | `0`, `00`, `0junk`, 空文字, `true`, `junk`, ` 0` |

符号付き整数の範囲外入力について `atoi` の安全な範囲判定はありません。大文字小文字の扱いは数値変換に関係せず、`TRUE` も `true` と同様に数値変換できず 0 になる。小数点以降を含む `1.5` は整数部分の 1 として扱われる。読み取り結果は関数ローカル static に保持されるため、プロセス内の最初の該当初期化後に環境を書き換えても再評価されない。

## 有効になる条件

- `--adapt-async` が非ゼロであること。この環境変数は `o.adapt_async` が真の分岐でのみ読み取られる。未指定時の `o.adapt_async` は 0（`engine/src/program/generate.cpp:1060-1062,11796-11800`）。
- `--pipeline-windows` が 2 以上であること。1 以下ではこの値による判定・無効化はない（`engine/src/program/generate.cpp:11801-11811`）。
- pipeline windows と非同期 adaptive tier の他の成立条件も満たすこと。pipeline windows は serve、別々の GPU に置いた複数 stage、MTP drafter と `--spec` 2 以上などを必要とし、明示指定でも不成立なら無効化される（`engine/src/program/generate.cpp:6584-6601`）。非同期 tier は `--serve`、`--adapt-every` と正の swap 数、resident RAM mode（`--resident-experts` 等）または arena、非 arena の layer split、`--batch-groups`、peer device、remote expert optimizer などの制約を受ける（`engine/src/program/generate.cpp:11801-11811`）。
- 非同期 tier と `--pipeline-windows 2` の併用は、3 stage 以上では pipeline 側が先に `--adapt-async` と競合して無効化される。したがってこのゲートが両者の併用を許すのは、他条件も満たした 2-stage split の経路である（`engine/src/program/generate.cpp:6584-6592`）。
- 自動 pipeline 選択は `o.adapt_async` が真なら候補から外れる。非同期 adaptive tier と組み合わせる場合は `--pipeline-windows 2` の明示指定が必要（`engine/src/program/generate.cpp:6560-6579`）。自動 pipeline の既定選択自体も HIP build でのみ有効（`engine/src/program/generate.cpp:6567-6571`）。
- `STRATA_ADAPT_ASYNC` は `--adapt-async` が未指定の場合の自動選択に使われる別変数であり、この変数の値を代替しない。`--adapt-async` が明示されると自動選択判定を行わないため、この環境変数が target gate の結果を上書きする経路はない（`engine/src/program/generate.cpp:11774-11794`）。
- Windows 上の AMD/HIP では別途 `STRATA_WIN_HIP_RISKY` の判定が先に非同期 tier を拒否することがある。その場合、この変数が許可値でも非同期 tier は有効にならない（`engine/src/program/generate.cpp:11761-11768`）。

## 実行時の詳細

CLI 解析では `--adapt-async` の引数を `atoi` して 0/非ゼロに正規化する。後続の async tier 判定では、serve 外、adaptive tier 無効、resident RAM mode 未成立、arena の layer split、batch groups、peer device、remote optimizer の順に不成立理由を調べ、その後に `pipeline_windows >= 2 && !pl_async` を確認する。前段の理由があればその理由が採用され、この環境変数を理由とする表示にはならない（`engine/src/program/generate.cpp:4061,11801-11811`）。

変数が未設定または `atoi` 結果が非ゼロなら、pipeline windows 2 が有効な経路では非同期 tier が継続する。値が 0 なら `adapt_async_off` が `o.adapt_async` を 0 に戻し、その後の tier 選択は blocking 側になる（`engine/src/program/generate.cpp:11770-11772,11809-11811,15605-15613`）。blocking tier は window 間で動作し、pipeline loop 中の非同期 tier は各 stage の window がない gap にコピーを送り、対象 window が読み得る slot の上書きを fence する構成である（`engine/src/program/generate.cpp:15411-15424,15535-15554,15767-15779`）。この変数による差は tier の実行方法であり、ここから生成 token の同一性を保証する記述はできない。

読み取りは `o.adapt_async` が真の経路で `pl_async` を初期化する際に一度行われる。`static` に保存されるため、後続の同一プロセス内の生成で環境変更を再読込しない（`engine/src/program/generate.cpp:11796-11800`）。

## ログと測定値

環境変数が 0 扱いで、他の先行条件に引っかからず、`--pipeline-windows 2` のときは stderr に次の行が出る（`engine/src/program/generate.cpp:11809-11811,11770-11772`）。

```text
strata generate: --adapt-async 1 is off (not with --pipeline-windows 2 (STRATA_PIPELINE_ADAPT_ASYNC=0)): the blocking adaptive tier
```

値が未設定または非ゼロなら、この変数専用のログは出ない。値が 0 扱いでも `--adapt-async` が未指定/0、pipeline windows が 2 未満、または前段の不成立理由があると上記理由のログは出ない。資料にはこの変数単独の性能測定値はない。

## 根拠

- `engine/src/program/generate.cpp:1060-1062,4061` — `--adapt-async` の既定値と CLI 変換。
- `engine/src/program/generate.cpp:6560-6579,6584-6601` — pipeline の自動選択と成立条件。
- `engine/src/program/generate.cpp:11754-11811` — tier の役割、OS/backend 上の別判定、環境変数読取、無効化理由。
- `engine/src/program/generate.cpp:12166-12180,12257-12258` — resident RAM/exchange buffer 条件による無効化。
- `engine/src/program/generate.cpp:15411-15424,15535-15554,15605-15613,15767-15779` — blocking/async tier の動作と pipeline 中の同期。
- `docs/DETAILS.md:274-276` — `--adapt-async` の一般説明。現行コードではこの変数が pipeline windows 2 との併用ゲートを追加する。
