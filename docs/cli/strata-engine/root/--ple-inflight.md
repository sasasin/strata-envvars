# `strata --ple-inflight`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--ple-inflight` |
| 別名 | なし |
| 値 | 整数 `N`、1〜1024 |

## 役割

PLE（per-layer token embedding）テーブルを direct I/O で読むとき、同時に保持できる SSD read の上限を指定します。PLE テーブルを使う推論で、テーブルの読み込み処理に渡されます。未指定時は256です。

## 使い方

```sh
strata --pack pack/full --tokens "1,2,3" --ple-gguf ple.gguf --ple-inflight 128
```

この例では PLE テーブルの direct 読み込み枠を128件にします。実際のモデル、トークン、PLE ファイルのパスに置き換えてください。

## 値と既定値

- `N` は `1..1024` の範囲で指定します。既定値は256です。
- parser は `std::atoi` で整数に変換し、後段で範囲を検査します。数値として読めない値は0となり拒否されます。`atoi` は厳密な文字列全体の検証をしないため、数値の後ろに文字が続く値は数値部分として解釈されます。
- 同じオプションを複数回指定すると、引数走査中に値が上書きされ、最後に指定した値が使われます。
- 値を省略すると parser は `<option> needs a value` を stderr に出して終了コード2で終了します。

## 実行時の動作

`--ple-inflight` の値は `PleIoOptions.max_inflight` に設定され、PLE テーブルの読み込み時に reader へ渡されます。reader はこの数の read slot を作り、direct 読み込みで同時に実行できる read 数を制限します。1 slot あたり2ページ分の aligned buffer を確保します。値を大きくすると同時 read の上限と buffer 枠が増えますが、速度向上は保証されません。

この値が設定されても、`--ple-gguf` が空ならテーブル初期化処理には入りません。`--ple-gguf` を指定した場合、`--ple-io direct`（既定）ではこの上限が direct reader に適用されます。`--ple-io mmap` または `--ple-io ram` では PLE テーブルを memory map するため、direct reader の同時 read 枠としては使われません。

## 適用条件と副作用

- 通常の `strata` エンジン parser と SYCL 版 parser の双方にこの引数があります。`strata-engine` の `root/` scope です。Qwen3.6 専用 parser は別 scope です。
- `--no-ple` と `--ple-gguf` は併用できず、PLE 無効時は PLE ファイルを開く処理も実行されません。
- direct 読み込みでは reader の初期化時に `N × 2ページ` 分の aligned read buffer を確保します。確保に失敗すると reader 初期化が失敗し、推論開始前にエラーになります。
- `--ple-io` が `mmap` または `ram` の場合はこの値で direct read buffer を確保しません。したがって同時 read 数を変える目的では影響しません。

## 出力とエラー

- `N < 1` または `N > 1024` の場合、stderr に `strata generate: invalid --ple-io/--ple-row-cache/--ple-inflight/--ple-delay-us` を出し、終了コード2で終了します。
- direct reader の buffer 確保に失敗した場合は、reader のエラー文字列を `strata generate: ...` として stderr に出し、終了コード1で終了します。

## 根拠

- `engine/src/program/generate.cpp:821` — 既定値256。
- `engine/src/program/generate.cpp:1218-1227` — PLE 関連オプションと help 表示上の既定値・用途。
- `engine/src/program/generate.cpp:3842-3846` — 値の取得方法と値省略時の終了コード2。
- `engine/src/program/generate.cpp:3901-3904` — `--ple-inflight` の parser と `atoi` 変換。
- `engine/src/program/generate.cpp:5009-5012` — 1〜1024の validation とエラー出力。
- `engine/src/program/generate.cpp:5205-5215` — `--no-ple` と `--ple-gguf` の条件、および PLE 必須条件。
- `engine/src/program/generate.cpp:6269-6276` — PLE ファイルが指定された場合の I/O mode と `max_inflight` 設定。
- `engine/include/strata/kernels/ngram.hpp:165-172` — Direct/Mmap のモードと `max_inflight` の説明。
- `engine/src/kernels/ngram.cpp:449-462` — Direct mode でのみ `PleReader` を開く処理。
- `engine/src/ngram/ple_reader.cpp:347-367` — reader 側の範囲確認、slot 数・read buffer の確保。
- `engine/sycl/src/program/generate.cpp:505,814,1942,2517-2520,3350-3357` — SYCL 版の既定値、parser、validation、reader option 設定が同じであること。
- `docs/cli/README.md:1036-1041,1169-1174` — `strata-engine` の `strata` root scope と本オプションの索引リンク。
