# `STRATA_FILL_AHEAD`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--expert-profile` の順位に沿って GPU expert cache を埋めるとき、mapped file source から読む expert pair を何組先に OS へ読み込み要求するかを指定する。値を変えるのはファイル読み込みの先行 advisory だけで、profile の順位、cache slot への割当て、expert のデータや生成内容を選ぶ処理は変えない。CUDA/HIP 実装と SYCL 実装に同じ分岐がある（`engine/src/program/generate.cpp:9758-9798`、`engine/sycl/src/program/generate.cpp:5257-5263,5375-5396`）。

## 値と判定

両 backend とも `std::getenv` の結果を `std::atoi` で変換し、設定値は `std::max(0, ...)` で負数を 0 にする。未設定だけが既定値 256 で、空文字は設定済みとして `atoi("") == 0` になる。文字列全体の妥当性は検査しない。したがって `12tail` は 12、`0anything`・`true`・数値で始まらない文字列は 0 となる。`atoi` が読む先頭の空白や符号も通常どおり扱われる。明示的な上限 clamp や変換エラー検査はなく、整数範囲を超える入力の結果はこのコードでは保証されない。読み取った正数は初回 advisory の pair 数として `want` 以下に制限されるが、ログ上の値自体は `want` に合わせて clamp されない（`engine/src/program/generate.cpp:9767-9774`、`engine/sycl/src/program/generate.cpp:5375-5382`）。

| 条件 | unset | 設定時に advisory が要求される値 | 0 として扱われる値 |
|---|---:|---|---|
| CUDA/HIP または SYCL の mapped source・通常の cache fill | 256 | `atoi` の結果が正ならその数（例: `1`, `12tail`） | 空文字、`0`, `0anything`, `true`, 数値で始まらない文字列、負数（例: `-1`） |
| Windows、または `STRATA_READ_AHEAD` によって OS read-ahead が無効 | 256 を選ぶが、source が advisory を拒否するため実効値は 0 | 同左。OS read-ahead が無効なら実効値は 0 | 0 |

`STRATA_READ_AHEAD` は `engine/src/platform/memory.cpp:205-211` で別途評価され、未設定なら read-ahead を有効、`atoi` の結果が 0 なら無効にする。これは関数内 `static` に一度だけ保存される。Windows 実装は常に `read_ahead_enabled() == false`（同ファイル `:160-162`）。

## 有効になる条件

- 読み込んだ profile が空でなく、expert source が存在し、cache fill が実行されること。profile は `--expert-profile` で指定する（例: `engine/src/program/generate.cpp:4211`、profile 読み込みと fill の条件: 同 `:9758-9763`）。
- fill が per-layer admission でなく、source が mapped file source `src` で、unbuffered でないこと。この条件を満たさない場合、この変数は読み取られない（`engine/src/program/generate.cpp:9761-9772`、`engine/sycl/src/program/generate.cpp:5260-5263,5375-5382`）。
- `--mmap-experts` は mapped file source を選ぶ経路。通常の resident arena source には適用されない（`engine/src/program/generate.cpp:8621-8647,8745-8747`、`engine/sycl/src/program/generate.cpp:4726-4758`）。
- SYCL の `--stream-experts` は GGUF source `gguf_src` を使い、既定では pipelined fill となるため対象外。`STRATA_FILL_SERIAL` が設定されて serial fill に切り替わっても source は `src` ではないので対象外（`engine/sycl/src/program/generate.cpp:4711-4725,5270-5271,5377-5382`）。
- `--expert-cache-per-layer` が有効な場合は `per_layer` が true となり、この変数の読み取り分岐を通らない（`engine/src/program/generate.cpp:9761-9772`、`engine/sycl/src/program/generate.cpp:5260,5377-5382`）。
- OS の read-ahead advisory が利用可能であること。Windows は常に無効。POSIX 側では `STRATA_READ_AHEAD=0`（または `atoi` が 0 となる値）でも無効になる（`engine/src/platform/memory.cpp:160-162,205-219`）。

## 実行時の詳細

この値は cache の profile fill に入ったときに読み取られ、関数内 static には保存されない。最初に `min(fill_ahead, want)` 組を `FileExpertSource::advise_pairs` に渡し、その後 fill loop の各 pair で、`i + fill_ahead < want` の間、次の対象 pair 1 組を追加で要求する（`engine/src/program/generate.cpp:9767-9793`、`engine/sycl/src/program/generate.cpp:5375-5391`）。従って値は pair の距離であり、bytes 数や秒数ではない。unset の 256 は初回要求を `want` 組以内にする一方、逐次要求の距離としても使われる。

`advise_pairs` は mapped source があり、unmapped/unbuffered でなく、`read_ahead_enabled()` が true のときに限って成功扱いとなる。`experts.bin` なら pair の blob 範囲、GGUF shard mapping ならその expert の3 tensor範囲を OS advisory に渡す（`engine/src/core/expert_source.cpp:2675-2689`、SYCL: `engine/sycl/src/core/expert_source.cpp:962-976`）。OS advisory の実行自体は待たず、コードはその完了や実際の I/O を確認しない。初回の `advise_pairs` が false を返すと `fill_ahead` を 0 にし、その後の先行要求も止める。fill loop の後続 advisory の戻り値は無視される。

`STRATA_FILL_AHEAD` 自体は fill ごとに読み直す。通常の一回の `strata generate` 起動では profile fill は startup 中に一度行われるため、その後の生成リクエストでは再評価されない。サーバーでも同じ初期 fill の位置で評価される。`STRATA_READ_AHEAD` の方は `read_ahead_enabled()` 初回呼び出し時の static cache であり、その後の環境変更は反映されない（`engine/src/platform/memory.cpp:205-211`）。

## ログと測定値

対象分岐が実行されると stderr に次の形式で値を出す。初回 advisory が使えない場合は `0` と表示する。

```text
strata generate: the profile fill asks for N pairs ahead (STRATA_FILL_AHEAD)
```

このログは per-layer、unbuffered、非 mapped、profile fill がない経路では出ない（`engine/src/program/generate.cpp:9767-9774`、`engine/sycl/src/program/generate.cpp:5375-5382`）。本変数による性能測定値は、調査対象コードと参照した `docs/DETAILS.md` に条件付きの測定値がないため記載しない。`docs/DETAILS.md:320-322` は既定値 256 と先行要求の説明を記すが、値変換・適用条件は上記実装に従う。

## 根拠

- 値の変換、初回・逐次 advisory、ログ: `engine/src/program/generate.cpp:9758-9798`、`engine/sycl/src/program/generate.cpp:5257-5263,5375-5396`
- source 選択と mapped/unbuffered 条件: `engine/src/program/generate.cpp:8621-8647,8745-8747`、`engine/sycl/src/program/generate.cpp:4711-4758`
- advisory の受付条件と pair の範囲: `engine/src/core/expert_source.cpp:2675-2689`、`engine/sycl/src/core/expert_source.cpp:962-976`
- OS / `STRATA_READ_AHEAD` 条件: `engine/src/platform/memory.cpp:160-162,205-230`
- 既定値の概要: `docs/DETAILS.md:320-322`
