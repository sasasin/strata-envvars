# `--version`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41` |
| オプション | `--version` |
| 別名 | なし |
| 値 | 取らない |

## 役割

`strata-dsv41` 実行ファイルの Strata バージョンとビルド ID を標準出力に表示し、終了します。この実行ファイルは `STRATA_BUILD_DSV41=ON` のビルドで作られる独立した DeepSeek-V4.1 engine CLI です。索引には Release での配布有無はソース inventory から断定できないと記されています。

## 使い方

```sh
strata-dsv41 --version
```

モデルの pack パスや GPU は必要ありません。

## 値と既定値

このフラグは値を受け取らず、値の validation もありません。出力形式は `strata-dsv41 <STRATA_VERSION> build <DS4_BUILD_ID>` と改行です。`STRATA_VERSION` は CMake の `project(strata VERSION ...)` に設定されたプロジェクト版です。`DS4_BUILD_ID` は明示指定された `STRATA_BUILD_ID`、なければソースツリーの `BUILD_ID` の先頭行、なければ configure 時点の Git 短縮 SHA（9文字）、いずれも得られない場合は `unknown` になります。

## 実行時の動作

parser は引数を左から順に処理し、`--version` に到達するとバージョン行を `stdout` に出して即座に終了コード `0` で戻ります。そのため、通常必要となる `--pack` や推論モードの引数がなくても使用できます。`--version` より後ろの引数は処理されません。先行する `--verbose` はその時点でビルド情報を `stderr` に出すため、`strata-dsv41 --verbose --version` は stderr にも出力します。

値を取るオプションの値として `--version` が消費された場合は version 分岐には入りません（例: `--pack --version` では `--version` が `--pack` の値になります）。また、先行する未知のオプションは version 分岐より前に失敗します。

バージョン判定は model load より前にあります。この経路では pack の読込、GPU 初期化、推論、推論用ファイル出力は行われません。ただし `main` は parser の前に `fine_timer()` を呼びます。Windows で `DS4_TIMER_MS` が正の整数なら `timeBeginPeriod` を呼びます（戻り値は検査されません）。それ以外の OS ではこの関数は何もしません。

## 適用条件と副作用

実行可能ファイルがある環境で利用できます。CMake では `STRATA_BUILD_DSV41=ON` の場合に `strata-dsv41` target を定義します。構成時の `STRATA_BUILD_ID` が指定されていればそれを使用し、未指定時は `BUILD_ID`、Git の短縮 SHA、`unknown` の順で決まります。

主な副作用は標準出力への1行出力とプロセス終了です。Windows の `DS4_TIMER_MS` 条件では、終了前にシステムタイマー解像度の要求を行います。

## 出力とエラー

成功時は標準出力に `strata-dsv41 <版> build <ID>` を1行出して終了コード `0` です。`--version` 自体に拒否値はありません。version 分岐に先行して未知の option がある場合は、標準エラーに `unknown option <値>` と usage を出し、終了コード `2` になります。version フラグ固有の失敗経路はソース上で確認できませんでした。

## 根拠

- `src/dsv41/ds4_main.cpp:1183-1188` — build ID の未定義時 fallback と `main` 冒頭の timer 呼び出し。
- `src/dsv41/ds4_main.cpp:1200-1208` — 左から順に処理する parser と、値不足時に標準エラーへ出して終了コード `2` とする処理。
- `src/dsv41/ds4_main.cpp:1248-1253` — `--verbose` の先行出力、`--version` の出力文字列と即時成功終了。
- `src/dsv41/ds4_main.cpp:1266-1273` — help と未知 option の出力・終了経路。
- `src/dsv41/ds4_main.cpp:1282-1295` — 通常実行の引数確認と model load。version 分岐はこの前に終了する。
- `src/dsv41/ds4_os.hpp:41-51` — Windows で `DS4_TIMER_MS` が正の場合に限る `timeBeginPeriod` 呼び出し。
- `CMakeLists.txt:11,23` — プロジェクト版と `STRATA_VERSION` 定義。
- `CMakeLists.txt:800-823` — 条件付き target、build ID の決定順と `DS4_BUILD_ID` 定義。
