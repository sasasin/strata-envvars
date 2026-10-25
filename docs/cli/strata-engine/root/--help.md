# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（CMake 生成のネイティブ推論エンジン、root 引数） |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし |

## 役割

エンジン引数の usage とオプション説明を表示して終了します。対象は Terminal CLI の Python 製 `strata` wrapper ではなく、`src/program/generate.cpp` をソースにするネイティブ実行ファイルです。

## 使い方

```sh
strata --help
```

短縮別名も同じ処理です。

```sh
strata -h
```

## 値と既定値

値は取りません。通常の engine parser は引数列を左から処理し、`--help` または `-h` に到達すると usage を表示して直ちに `0` を返します。したがって、その後ろにある通常 parser の引数は検証されません。`--help` の指定回数による差はなく、最初に到達した時点で終了します（`src/program/generate.cpp:2416-2424`）。

## 実行時の動作

usage 本文は `usage()` に固定文字列として実装されています。先頭に `strata generate --pack DIR --tokens ... [options]` の形式を示し、基本引数から診断・serve・GPU 関連などの説明を続けます。`usage()` は `std::fprintf(stderr, ...)` を使うため、ヘルプ本文の出力先は標準エラーです（`src/program/generate.cpp:806-808`, `src/program/generate.cpp:1069-1078`）。

help 分岐は通常 parser 内にあり、単独実行では引数解析ループ中に usage を出して `return 0` します。モデルや推論状態の初期化、トークン生成には進みません（`src/program/generate.cpp:2413-2424`, `src/program/generate.cpp:3174-3190`）。

## 適用条件と副作用

- `main()` は通常 parser より前に、先頭 2 引数までにある `--version` / `-V` と `--families` を処理します。これらが該当位置にあれば `--help` より先に終了し、version または family 一覧だけを標準出力へ出します（`src/program/generate.cpp:2331-2346`）。
- 同じ前処理では、`--gpu` の値を探して CUDA/HIP の可視デバイス環境変数をプロセス内で設定します。既存値と異なる場合は警告を標準エラーに出します。HIP build（`STRATA_USE_HIP`、gfx906 を除く）では、通常 parser より前に `prime_hw_queues()` も呼ばれます。このため、その経路の `--help` は前処理の環境変更や GPU queue 初期化より前には終了しません（`src/program/generate.cpp:2370-2392`, `src/program/generate.cpp:2410-2423`）。
- `STRATA_HAVE_QWEN35` build で `--native` または `--model` の値が Qwen35Moe family と判定されると、通常 parser の help 分岐に着く前に `strata::qwen35::run()` へ委譲します。専用 parser は `--help` / `-h` を受理せず、未知引数として usage を stderr に出して終了コード `2` を返します（family 判定と委譲: `src/program/generate.cpp:2393-2408`; 専用 parser: `src/qwen35/q36_engine.cu:3735-3746`, `src/qwen35/q36_engine.cu:3782-3795`）。索引でも専用 parser は `qwen36/` scope に分けられています（`docs/cli/README.md:1318-1323`）。
- 通常 parser で未知の引数に遭遇した場合は、`unknown argument: ...` を stderr に出し、同じ usage を表示して `2` を返します。これは `--help` の成功経路とは別です（`src/program/generate.cpp:2787-2793`）。

## 出力とエラー

通常 parser の `--help` / `-h` は usage を stderr に出し、終了コード `0` です。専用 Qwen35 parser に委譲された場合は同じ option を認識せず、usage を stderr に表示して終了コード `2` になります（`src/program/generate.cpp:2423`; `src/qwen35/q36_engine.cu:3782-3795`）。

## 根拠

- `src/program/generate.cpp:806-1078` — usage 本文と stderr 出力。
- `src/program/generate.cpp:2309-2413` — main の早期処理、`--gpu` 前処理、family 分岐。
- `src/program/generate.cpp:2416-2424` — `--help` / `-h` の parser 分岐と終了コード。
- `src/program/generate.cpp:2787-2793`, `src/program/generate.cpp:3174-3179` — 通常 parser の失敗・必須引数不足経路。
- `src/qwen35/q36_engine.cu:3735-3795` — Qwen35 専用 parser での引数処理と未知引数経路。
- `CMakeLists.txt:759` — `strata` executable が `src/program/generate.cpp` から作られる定義。

この調査では既存 CLI の help 出力は実行していません。上記は対象 checkout のソースを確認した結果です。Release 配布物との照合は行っていません。
