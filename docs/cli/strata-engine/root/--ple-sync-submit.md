# `--ple-sync-submit`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--ple-sync-submit` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

PLE table の Direct 読み込みを発行するスレッドを切り替える A/B 用フラグです。既定では PLE reader が I/O worker thread を作成します。このフラグを付けると worker を作らず、読み込み処理を呼び出し側のスレッドで行います。ソースコメントではこれを token thread からの submit と説明しています。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --ple-gguf model-ple.gguf --ple-sync-submit
```

実際の prompt、pack、PLE GGUF のパスは利用するモデルに合わせてください。`--ple-gguf` を省略できる場合や必要な shard はモデル形式に依存します。

## 値と既定値

- 指定時は `ple_sync_submit` を `true` にします。未指定時は `false` で、I/O worker thread を使います。フラグ自体に値は不要で、同じ引数を複数回指定しても同じ真偽値を設定します。
- parser にこのフラグ固有の値検証はありません。別の値を続けて書く構文ではありません。
- 一般の実行では PLE は既定で必要で、`--no-ple` は診断用の明示的な ablation です。`--no-ple` と `--ple-gguf` は併用できません。

## 実行時の動作

parser はこの引数を見つけるとフラグを立てます（`src/program/generate.cpp:2473-2479`）。PLE table の設定時に `pio.io_thread = !o.ple_sync_submit` として reader に渡すため、このフラグは worker thread の有無を反転します（`src/program/generate.cpp:4033-4054`）。

I/O worker を使う既定経路では、worker が DirectFile 呼び出しと完了処理を担当し、呼び出し側の `issue` はジョブ構築と worker の wake にとどまります。worker を使わない場合は呼び出し側がそれらを実行します（`src/ngram/ple_reader.cpp:95-99,336-378`）。PLE table 自体が開かれるのは `--ple-gguf` が設定されている場合です（`src/program/generate.cpp:4033-4054`）。

`--ple-io` の既定値は `direct` です。`mmap` または `ram` は Direct reader を使わないため、このフラグによる worker の切り替えは読み込み経路に適用されません（`src/program/generate.cpp:479-481,4033-4040`; `src/kernels/ngram.cpp:340-354`）。

## 適用条件と副作用

- フラグは PLE table を開く処理で反映されるため、PLE を使わない診断実行では読み込み worker に影響しません（`src/program/generate.cpp:4033-4040,4177-4180`）。
- Direct mode では `--ple-sync-submit` により `pio.io_thread` が無効になると、`STRATA_SSD_KEEPALIVE` 等から設定した keep-alive 値も 0 にされます。Direct mode の SSD keep-alive は無効となり、起動時にその旨が stderr に出ます（`src/program/generate.cpp:4041-4050,4107-4112`）。
- 呼び出し側が Direct I/O と完了待ちを担うため、I/O worker への仕事の委譲はありません。worker 作成失敗の経路（`PleReader: cannot create I/O worker`）は通らなくなりますが、呼び出し側に I/O 処理が移ります（`src/ngram/ple_reader.cpp:95-99,364-375`）。性能上の優劣はこの調査では測定していません。

## 出力とエラー

このフラグ専用の出力や validation error はありません。PLE table の open が失敗した場合、エラー内容を `strata generate: ...` として stderr に出し、終了コード 1 で終了します（`src/program/generate.cpp:4052-4054`）。worker 作成失敗の具体的なエラーは reader が返しますが、このフラグを付けると worker 作成処理自体を行いません（`src/ngram/ple_reader.cpp:364-375`）。Direct 読み込みの token gather が失敗した場合は `PleTable::gather: ...` を stderr に出して PLE embedding 出力をゼロ埋めします（`src/kernels/ngram.cpp:639-648`）。この経路は gather 側でログと代替値を処理し、ここからエラー終了コードを返してはいません。

## 根拠と調査範囲

- parser の既定値・help 表示・引数設定: `src/program/generate.cpp:485,806-827,2473-2479`。
- PLE reader への設定、適用条件、Direct mode の keep-alive 相互作用: `src/program/generate.cpp:4033-4054,4107-4112`。
- worker と caller-thread の動作、worker 作成失敗: `src/ngram/ple_reader.cpp:95-99,336-378`。
- Direct の token gather 失敗時のログとゼロ埋め: `src/kernels/ngram.cpp:639-648`。
- Direct mode で reader に渡す処理と mmap/ram の区別: `src/kernels/ngram.cpp:340-354`。
- 索引は `strata-engine` root の parser を `src/program/generate.cpp` と定義しています（`docs/cli/README.md`）。同じフラグ文字列は `sycl/src/program/generate.cpp` にもありますが、この文書では索引の root parser 対象に合わせて説明しています。SYCL executable の配布・実行条件は確認していません。
