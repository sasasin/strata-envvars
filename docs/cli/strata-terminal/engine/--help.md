# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（CMake 製のネイティブ推論エンジン） |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない |

## 役割

通常のエンジン parser が認識するオプション概要を usage として表示し、生成処理を始めずに終了します。表示内容は `src/program/generate.cpp` の `usage()` に固定文字列で定義されています。見出しは `strata generate --pack DIR --tokens "1,2,3" [options]` です（`src/program/generate.cpp:806-812`）。

## 使い方

```sh
strata --help
strata -h
```

ここでの `strata` は Terminal CLI の Python wrapper ではなく、CMake ターゲット `strata` が生成するネイティブ実行ファイルです（`CMakeLists.txt:759-762`）。

## 値と既定値

値は不要です。通常 parser の引数走査中に `--help` または `-h` を認識すると、usage を出力して直ちに `0` を返します（`src/program/generate.cpp:2416-2424`）。既定値や値の validation はありません。最初に到達した help が処理を終えるため、通常 parser では複数回指定しても usage を複数回表示しません。

help は独立した先行 parser ではなく通常の引数走査にあります。そのため、help より前に置いた引数は先に処理され、そこで不正値・値不足・重複入力などのエラーになると usage 表示まで到達しません。help より後ろの引数は通常 parser では処理されません（`src/program/generate.cpp:2416-2430`, `2787-2793`）。また、`main()` の早期処理で `--version` / `-V` が argv の先頭 2 引数内にあれば help より先に version を出して終了します（`src/program/generate.cpp:2331-2345`）。

## 実行時の動作

usage は `std::fprintf(stderr, ...)` で stderr に出力されます。成功経路は usage 表示の直後に `return 0` し、必須の `--tokens` 検査やモデル処理へ進みません（`src/program/generate.cpp:806-808`, `2423-2424`, `3173-3179`）。

usage は parser 全体の完全な一覧とは限りません。索引が注記するように、parser では受理されても usage に掲載されない option があります（例: `--no-kv-grow`）。`--help` 自身も usage の掲載項目にはありません。表示は実行時の build 条件によって動的に組み立てられるものではありません（`docs/cli/README.md:1130-1133`; parser は `src/program/generate.cpp:2422-2425`, `2780-2787`）。

## 適用条件と副作用

- この文書の成功経路は `src/program/generate.cpp` の通常 parser に到達した場合です。Qwen3.5 family を含む build では、`--native` / `--model` が指す GGUF の family を先に調べ、該当時は `src/qwen35/q36_engine.cu` の別 parser に argv 全体を渡します（`src/program/generate.cpp:2393-2407`）。その parser には `--help` / `-h` の分岐がありません。したがって、その経路で help を渡すと不明引数扱いとなり、Qwen 用 usage を stderr に出して `2` で終了します（`src/qwen35/q36_engine.cu:3735-3754`, `3782-3795`）。索引でも Qwen 用 parser は別 scope です（`docs/cli/README.md:1320-1325`）。
- 通常 parser に入る前に、未設定なら `CUDA_MODULE_LOADING=EAGER` を process 環境へ設定します（`src/program/generate.cpp:2356-2365`）。さらに argv に `--gpu LIST` があると、通常 parser が help に到達する前に `CUDA_VISIBLE_DEVICES`（HIP build では `HIP_VISIBLE_DEVICES`）と `CUDA_DEVICE_ORDER=PCI_BUS_ID` を設定し、既存値と異なる場合は stderr に警告します（`src/program/generate.cpp:2370-2391`）。この値の検証・通常 parser による消費より先に起きるため、`--gpu` と help の併用も環境変数設定の副作用を伴います。
- HIP build（`STRATA_USE_HIP`、gfx906 を除く）では parser より前に `prime_hw_queues()` が呼ばれます。条件により GPU 数・属性を照会し、GPU メモリを一時確保して stream を作成・同期・破棄します。対象 GPU/環境変数の条件を満たす場合は stderr に queue 数も出します（`src/program/generate.cpp:2244-2306`, `2410-2412`）。したがって `--help` は全 build で GPU に触れないとは限りません。
- Qwen family 判定時には、該当する `--native` / `--model` の GGUF header を読みます（`src/program/generate.cpp:2393-2407`）。このため、help の前処理には argv と build/family に依存する処理があります。

## 出力とエラー

通常 parser では usage を stderr に出し、終了コード `0` です。実際の表示文字列は `usage()` の定義（`src/program/generate.cpp:806-1077`）を参照してください。Qwen family の別 parser に渡った場合は前述のとおり usage と終了コード `2` です（`src/qwen35/q36_engine.cu:3789-3795`）。

## 根拠

- `CMakeLists.txt:759-762` — ネイティブ `strata` 実行ファイルの定義。
- `src/program/generate.cpp:806-1077` — usage 本文と出力先 stderr。
- `src/program/generate.cpp:2331-2345` — help より前に行う version / families の早期終了。
- `src/program/generate.cpp:2356-2391` — 起動前の環境変数設定と `--gpu` 処理。
- `src/program/generate.cpp:2393-2424` — family 判定、HIP queue 初期化、通常 parser の help 分岐。
- `src/program/generate.cpp:2787-2793`, `3173-3179` — 不明引数・必須入力エラーと、help が生成処理を抜ける位置。
- `src/qwen35/q36_engine.cu:3735-3795` — Qwen family parser に help 分岐がなく、不明引数時は `2` で終了する経路。
- `docs/cli/README.md:1130-1133`, `1320-1325` — engine parser の対象境界と Qwen 用 scope の索引記載。

調査ではソースと索引を確認しました。既存実行ファイルの `--help` は実行しておらず、Release artifact と実機ごとの GPU 初期化結果は確認していません。
