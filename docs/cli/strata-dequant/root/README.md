# `strata-dequant`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-dequant` |
| コマンド | `strata-dequant`（CMake 生成の単体 CLI） |
| 主な実装 | `src/artifact/dequant.cpp`、`include/strata/artifact/dequant.hpp`、`include/strata/artifact/gguf_reader.hpp` |
| 引数 | GGUF ファイルの位置引数 1 個。オプション parser はない |
| build target | `strata-dequant` |

## 役割

GGUF ファイル内の一部量子化 tensor を読み、Q2_0 の構造的不変条件を spot-check し、対応する量子化形式の checksum と先頭値を表示する診断・開発用コマンドです。推論用の変換コマンドではなく、復号値を F32 ファイルへ書き出す処理もありません。CMake では `strata-dequant` target が `src/artifact/dequant.cpp` から作られ、`STRATA_DEQUANT_SELFTEST` を定義して `main` を有効にします（`CMakeLists.txt:253-267`）。索引上も製品の Terminal CLI とは別の単体 CLI として扱われています（[`docs/cli/README.md`](../../README.md)）。

## 使い方

```sh
strata-dequant ./model.gguf
```

この例は、CMake で生成した実行ファイルを `PATH` 上で実行できる場所から呼び出す場合です。引数を省略すると `usage: dequant <file.gguf>` を標準出力に表示して終了コード 2 で終了します（`src/artifact/dequant.cpp:6-10`）。2 個目以降の引数は参照されないため、`--help` や `--check` はオプションとして処理されません。`--help` を引数 1 個目に置くとファイル名として開こうとします（同 `:11-14`）。

## 実行モードと主な動作

1. 指定された 1 ファイルを `strata::GgufFile` で読み込みます。reader はファイルを読み取り専用 mmap し、GGUF magic、version 3、metadata、tensor directory を解析します。分割 GGUF の shard 一覧を開く `GgufModel` ではなく単一ファイル reader を使うため、このコマンド自身は shard の探索・結合をしません（`src/artifact/dequant.cpp:11-14`; `include/strata/artifact/gguf_reader.hpp:378-411,414-446,459-504,535-562`）。
2. type id `42`（Q2_0）の tensor を列挙し、最大 8 tensor について各 tensor の先頭最大 64 block を復号します。復号値がその block の scale `d` に対する `{-d, 0, d, 2d}` のいずれか（または `d == 0`）かを調べます。違反は最大 3 件まで `VIOLATION` として出し、最初の Q2_0 tensor については先頭最大 64 block の `sum` と `sumabs` も表示します（`src/artifact/dequant.cpp:14-53`; Q2_0 の block 復号は `include/strata/artifact/dequant.hpp:68-78`）。
3. 続いて type id `6, 20, 14, 12, 13, 11, 23`（Q5_0、IQ4_NL、Q6_K、Q4_K、Q5_K、Q3_K、IQ4_XS）の tensor を処理します。各対象 tensor について先頭最大 64 block の checksum と最初の block の復号値 8 個を標準出力へ表示します。IQ4_XS（type 23）を処理した後は走査を終了します。これらの checksum は比較・検証のための表示であり、期待値との一致を判定する処理はありません（`src/artifact/dequant.cpp:54-114`）。

## 出力・終了コード

出力は `std::printf` による標準出力です。成功時は入力パス、Q2_0 の検査数と違反数、対応 tensor があれば checksum と先頭値を表示します。Q2_0 tensor がない場合も `checked == 0`、違反数 0 として `PASS` を表示し、終了コード 0 になり得ます。終了コード 1 になるのは Q2_0 の構造違反が見つかった場合、または例外が発生した場合です。例外は `ERROR: ...` と標準出力に表示されます。違反の詳細な表示も標準出力です（`src/artifact/dequant.cpp:27-33,115-120`）。

reader はファイルを開けない、mmap に失敗する、GGUF magic が異なる、version が 3 でない、header が切れている、dimension が不正などの場合に例外を送出します。`strata-dequant` はこれを捕捉して終了コード 1 にします（`include/strata/artifact/gguf_reader.hpp:414-446,459-504`; `src/artifact/dequant.cpp:118-120`）。

## 注意点

- このコマンドは tensor の全要素を変換して保存する用途ではありません。検査範囲は Q2_0 では先頭 8 tensor・各先頭 64 block、checksum 対象では各先頭 64 block までです（`src/artifact/dequant.cpp:14-20,42-53,70-73`）。
- Q2_0 の判定は復号値が同じ block の scale に基づく許容集合に入るかという構造検査です。ggml など別実装との数値一致を検証する比較処理ではありません（`src/artifact/dequant.cpp:24-28`; `include/strata/artifact/dequant.hpp:15-18`）。
- checksum や `REF first8` は人や外部 harness が照合するための値です。ソースには期待値との比較や不一致時の失敗経路がありません（`src/artifact/dequant.cpp:36-50,70-117`）。
- `include/strata/artifact/dequant.hpp:15-18` の古いコメントには ``--check <file.gguf>`` とありますが、現行 parser はなく、`main` は `argv[1]` を入力パスとして使うだけです。索引の「オプションなし（位置引数のみ）」と一致します（`src/artifact/dequant.cpp:6-14`; [`docs/cli/README.md`](../../README.md)）。
- `src/artifact/dequant.cpp:1` のコメントには「GGUF tensor を dequantize して F32 を dump」とありますが、現行の `main` は標準出力への部分検査・要約のみで、F32 ファイルを作成しません。

## 関連文書

- [CLI 文書索引](../../README.md) — この単体 CLI の配置と option scope。
- [CLI ツール一覧](../../000_cli_tools.md) — CMake 生成の診断・開発用プログラムの位置づけ。

## 根拠

- `CMakeLists.txt:253-267` — header-only artifact library、実行 target、self-test compile definition。
- `src/artifact/dequant.cpp:1-14,115-123` — CLI entry point、引数不足・入力 path・戻り値・例外処理。
- `src/artifact/dequant.cpp:14-53` — Q2_0 の tensor/block 上限、構造検査、最初の tensor の checksum。
- `src/artifact/dequant.cpp:54-114` — checksum 対象 type、block 上限、`REF first8` の出力と走査終了条件。
- `include/strata/artifact/dequant.hpp:15-18,68-78` — header 内コメントの `--check` 記述と Q2_0 復号処理。
- `include/strata/artifact/gguf_reader.hpp:378-411,414-446,459-504,535-562` — 単一ファイルの mmap/解析処理と、複数 shard を扱う `GgufModel` API。
