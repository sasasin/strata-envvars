# `strata` `--spec-corrupt`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの root 引数） |
| オプション | `--spec-corrupt` |
| 別名 | なし |
| 値 | 整数として `std::atoi` で変換される値。正数で改変を有効化 |

## 役割

speculative decoding の verify window に入れる draft token を一定間隔で意図的に別 token に置き換える、診断・検証向けのオプションです。通常の生成品質を調整する設定ではなく、draft が誤った場合の検証・受理経路を確認する用途です。対象 parser は通常の `engine/src/program/generate.cpp` と SYCL 用 `engine/sycl/src/program/generate.cpp` にあります。

## 使い方

```sh
# speculative decoding を有効にした上で、処理対象 draft の 3 個ごとに 1 個を改変する
strata --spec 4 --spec-corrupt 3
```

この例はエンジンの通常のモデル・入力指定と併用します。`--spec` が指定されていない場合の既定値はビルド条件で異なり、Metal では既定値 2、それ以外の通常 parser では 0 です（`engine/src/program/generate.cpp:1010-1017`）。

## 値と既定値

- 省略時は `spec_corrupt` の初期値 0 で、改変条件は働きません（`engine/src/program/generate.cpp:1028-1029`、SYCL: `engine/sycl/src/program/generate.cpp:675-676`）。
- 値は `std::atoi` で `int` に変換されます。Strata 側に正数範囲の validation や専用の不正値エラーはありません（`engine/src/program/generate.cpp:4052`、SYCL: `engine/sycl/src/program/generate.cpp:2046`）。実行時の条件は `spec_corrupt > 0` なので、0 以下なら改変しません（`engine/src/program/generate.cpp:25093`、SYCL: `engine/sycl/src/program/generate.cpp:14103`）。
- 値引数が欠けると parser の `next()` が stderr に `--spec-corrupt needs a value` を出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3847`、SYCL: `engine/sycl/src/program/generate.cpp:1884-1887`）。
- 同じ引数を複数回指定した場合の重複拒否処理はありません。parser は各指定を順に同じフィールドへ代入します（`engine/src/program/generate.cpp:4052`）。

## 実行時の動作

speculative verify window の各 draft 位置で、値が正なら共有カウンターを 1 増やします。カウンターが指定値で割り切れる位置では、その draft token ID を `(d + 1) % n_vocab` に置き換えてから window に格納します。たとえば `3` は、対象となる draft 3 個ごとに 1 個を改変します。カウンターは speculative generation の処理内で 0 から始まります（`engine/src/program/generate.cpp:24866-24868,25088-25094`、SYCL: `engine/sycl/src/program/generate.cpp:13989-13990,14098-14104`）。

このオプションが正数の場合、MTP の補助確率 `q` を verifier に渡す分岐も無効になります（通常実装: `engine/src/program/generate.cpp:25125-25128`）。また、`STRATA_SPEC_PROB=1` かつ既定の pick gate を使う条件で gated proposal の適用可否を調べる際、この option は「独自の window rule」として扱われます。その経路では gated proposal を使わず、条件に応じて stderr に従来の受理規則を使う旨の警告を出します（`engine/src/program/generate.cpp:3543-3558,24842-24845`）。

## 適用条件と副作用

- 実際の改変は speculative verify window の draft 位置を処理するときだけです。値が正でも、実行経路で speculative window が使われなければ改変されません（`engine/src/program/generate.cpp:24456,25088-25094`、SYCL: `engine/sycl/src/program/generate.cpp:13709,14098-14104`）。
- draft token を意図的に変えるため、通常の draft と verifier の一致・受理状況が変わります。生成出力や受理統計の診断に影響する実験用設定として扱ってください（改変位置: `engine/src/program/generate.cpp:25090-25094`）。
- 正数指定は上記の gated proposal の条件にも影響し、MTP の補助確率を使う分岐を抑止します。その他の option、環境変数、build/backend との組み合わせを網羅した実行検証はしていません。

## 根拠

- `engine/src/program/generate.cpp:1010-1017,1028-1029` — 通常実装の speculative 設定と既定値。
- `engine/src/program/generate.cpp:3844-3847,4052` — parser の値取得、変換、欠落値エラー。
- `engine/src/program/generate.cpp:24842-24845,25088-25094,25125-25128` — gated proposal 判定、draft 改変、MTP 補助確率との相互作用。
- `engine/src/program/generate.cpp:3543-3558` — gated proposal が利用できない場合の理由と警告。
- `engine/sycl/src/program/generate.cpp:1884-1887,2046,13989-13990,14100-14104` — SYCL parser と同じ改変処理。
- 配置と scope は `docs/cli/README.md:1036-1040,1204-1207` および `docs/cli/000_cli_tools.md:7-10` で照合。

調査範囲はこの revision の Strata 所有ソースにおける parser と参照箇所です。値変換は `std::atoi` に委ねられており、Strata 独自の整数形式・境界 validation は確認できません。実行バイナリでの挙動確認は行っていません。
