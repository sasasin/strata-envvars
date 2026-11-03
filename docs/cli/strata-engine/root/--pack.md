# `strata generate --pack`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジンの root 引数 parser） |
| オプション | `--pack` |
| 別名 | なし |
| 値 | pack ディレクトリのパス（文字列） |

## 役割

推論エンジンがモデルの重みと expert を読む pack ディレクトリを指定します。引数を省略すると `pack/full` を使います。エンジンの usage は `--pack DIR` と表示し、必須のトークン入力と併用する形式を示しています（`src/program/generate.cpp:1011-1017`）。

## 使い方

```sh
strata generate --pack /path/to/pack --tokens "1,2,3"
```

`--tokens` は `strata generate` の usage が示す必須の入力例です。CLI の parser は `--pack` の値を pack path として保存します（`src/program/generate.cpp:1013-1017,3294-3303`）。

## 値と既定値

- 値はディレクトリのパス文字列です。型・存在確認・値域検証は parser では行わず、指定値を `Options::pack` に代入します（`src/program/generate.cpp:594-598,3294-3303`）。
- 省略時は `pack/full` です（`src/program/generate.cpp:596,1015`）。
- 値を省略すると `next()` が標準エラーに `--pack needs a value` を出して終了コード 2 で終了します（`src/program/generate.cpp:3294-3297`）。重ねて指定した場合は parser が値を都度代入するため、最後に指定した値が残ります（`src/program/generate.cpp:3294-3303`）。
- 空文字列や存在しないパスを parser 自体は拒否しません。後続のファイル読み込みで失敗します。

## 実行時の動作

- 起動時に `<pack>/native_experts.txt` を調べます。ファイルがなければ標準の expert layout として扱い、存在すれば native layout を読み込みます。native layout の解析に失敗すると、その理由を `strata generate:` 付きで標準エラーに出して終了コード 1 です（`src/kernels/cpu/expert_layout.cpp:435-451`、`src/program/generate.cpp:4426-4433`）。
- 通常の重みは `<pack>/index.txt` からサイズと tensor 情報を得て GPU arena を確保し、各重みファイルをロードします。index が開けない場合は `cannot open <pack>/index.txt`、重みファイルが開けない場合はそのファイル名を含むエラーとなり、エンジンは終了コード 1 を返します（`src/core/weights.cpp:93-110,176-184`、`src/program/generate.cpp:4866-4872,4916-4922`）。ロード成功時は読込量と pack path を標準エラーに記録します（`src/program/generate.cpp:4924-4932`）。
- `native_experts.txt` がある native pack では、engine は `--native SHARD1`、`--spec T`（`T >= 2`）、および prefill 条件を要求します。不足時は要件を標準エラーに出して終了コード 2 です（`src/program/generate.cpp:4766-4777`）。
- `--mmap-experts` 併用時は `<pack>/experts.bin` を memory map します。native pack に `experts.bin` がない場合は native layout が示す model GGUF shard から expert を読みます。source を開けない場合は、通常はエラーを表示して終了コード 1、RAM 不足後の fallback 経路では arena 読み込みへ戻ります（`src/program/generate.cpp:7091-7117`）。

## 適用条件と副作用

- `--pack` は pack ディレクトリ内の index、重み、expert layout を読み込む場所を変えます。パスの作成・書き換えはこの option の処理では行いません（`src/core/weights.cpp:93-110,176-184`、`src/kernels/cpu/expert_layout.cpp:435-451`）。
- pack に `native_experts.txt` がなく CPU が必要な expert kernel 機能を持たない場合、エンジンは標準 Q2_0 pack と判定し、AVX-512 要件を説明してから CPU feature の拒否処理を呼びます。native pack で AVX-512 がない場合は利用する CPU kernel を標準エラーに案内します（`src/program/generate.cpp:4621-4645`）。
- native pack の読み込み経路は `--native` 等の条件に依存します。異なる pack 形式に対する適合性は parser では検査せず、各 pack metadata と後続 loader が検証します（`src/program/generate.cpp:4426-4433,4766-4777`）。

## 出力とエラー

option 自身には成功時の独立した出力はありません。pack の読み込み後、重みの読込量と使用 path が標準エラーに表示されます。pack metadata やファイルが欠けている・壊れている場合は loader の診断を標準エラーに出し、読み込み失敗は通常終了コード 1、native pack の必須 option 不足は終了コード 2 になります（`src/program/generate.cpp:4426-4433,4766-4777,4866-4872,4916-4932`）。

## 根拠

- parser の既定値・値の取り込み・不足時の扱い: `src/program/generate.cpp:594-598,1011-1017,3294-3303`
- native / canonical pack の識別と layout の読み込み: `src/kernels/cpu/expert_layout.cpp:435-451`、`src/program/generate.cpp:4426-4433,4621-4645`
- native pack の追加条件: `src/program/generate.cpp:4766-4777`
- index と重みファイルの読み込み・エラー: `src/core/weights.cpp:93-110,176-184`、`src/program/generate.cpp:4866-4872,4916-4932`
- mmap expert source と GGUF fallback: `src/program/generate.cpp:7091-7117`

調査範囲は上記 commit の checkout にある parser と loader のコードです。同 revision の既存 engine binary/help および Release archive は確認していません。
