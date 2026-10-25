# `--help`（alias: `-h`）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-device` |
| コマンド | `strata-device`（root） |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | 取らない。ヘルプフラグ。 |

## 役割

`strata-device` の usage と一部のオプション説明を表示し、終了します。これは `strata` Terminal CLI の `--help` ではなく、CMake が生成する単体の GPU 診断プログラムのトップレベル option です。実行ファイル自体は CUDA または HIP backend が有効な build で作られます（`CMakeLists.txt:333-351`）。索引もこの実行ファイルを独立 tool-id として掲載しています（`docs/cli/README.md:1399-1423`）。

## 使い方

```sh
strata-device --help
strata-device -h
```

## 値と既定値

値は不要です。独自の `argv` 走査で `--help` と `-h` を同じ分岐に割り当てています。値の型、既定値、範囲 validation はありません（`src/core/device_main.cpp:26-41`）。同じフラグを複数指定する必要はありません。走査中に最初の help flag が見つかった時点で終了するため、それより後の引数は処理されません。

## 実行時の動作

help 分岐は引数走査の中で usage を `stdout` に `printf` し、`0` を返します（`src/core/device_main.cpp:29-36`）。表示内容は `usage: strata-device [--selftest] [--list-devices]` と `--list-devices` の説明です。parser が実装する `--help` / `-h` 自身や `--selftest` の説明は usage 文面には列挙されていません（`src/core/device_main.cpp:32-36`）。

help 分岐はデバイス情報取得、VRAM plan 表示、arena selftest より前にあります。そのため help を認識した呼び出しでは GPU device query や GPU memory allocation を行わず、これらの通常処理へ進みません（`src/core/device_main.cpp:29-41,49-66,85-118`）。引数の順序にかかわらず、走査中に help に到達するとその場で終了します。たとえば `strata-device --help --unknown` は後続の未知引数を検査せず help 成功経路になります。一方、help より前に未知引数があれば、その時点でエラー終了します。

## 適用条件と副作用

オプション自体は GPU にアクセスしません。CMake 上の `strata-device` target は GPU runtime 用 `strata_core` とともに CUDA/HIP backend が有効な条件ブロック内で定義されています。したがって、このソースだけの確認では backend のない build に実行ファイルが存在するとはいえません（`CMakeLists.txt:333-351`）。

## 出力とエラー

`--help` / `-h` は標準出力に固定の usage 文を表示して終了コード `0` を返します（`src/core/device_main.cpp:32-36`）。未知の引数は `stderr` に `unknown argument: <引数>` を出し、終了コード `2` で終了します（`src/core/device_main.cpp:37-40`）。引数走査は左から順なので、未知引数の後ろに help があっても help には到達しません。

## 根拠

- `src/core/device_main.cpp:26-41` — 引数走査、help alias、usage 出力、未知引数の処理。
- `src/core/device_main.cpp:49-66,85-118` — help 分岐の後に行う device 列挙・情報取得、plan 表示、selftest。
- `CMakeLists.txt:333-351` — GPU backend 条件と `strata-device` target の定義。
- `docs/cli/README.md:1399-1423` — 独立診断 CLI としての索引上の scope、`--help` の予定リンク。

調査範囲は指定 commit の parser と同ファイル内の後続処理、CMake target 定義です。既存バイナリの有無や実行結果、各 GPU backend での動作、Release 配布物は確認していません。CLI help の実行、build、GPU 実行、テストは行っていません。
