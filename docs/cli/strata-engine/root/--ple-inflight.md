# `--ple-inflight`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（`strata generate` 引数 parser） |
| オプション | `--ple-inflight` |
| 別名 | なし |
| 値 | 整数 `N`。有効範囲は 1〜1024 |

## 役割

PLE n-gram テーブルを `direct` I/O で読むときに、同時に処理できる読み込み数を設定します。PLE 読み込みの I/O slot 数を制御し、未指定時は 256 です。`--ple-io mmap` または `--ple-io ram` では direct reader を開かないため、この値は読み込み処理に適用されません。

## 使い方

```sh
strata --pack ./pack --tokens "1,2,3" --ple-gguf ./model-00002-of-00002.gguf --ple-inflight 256
```

`--ple-gguf` には PLE テーブルを含む GGUF shard を指定します。`--tokens` はこの例の生成実行に必要です。PLE テーブルを指定しない場合も option の値は解析・検証されますが、reader の設定には使われません。

## 値と既定値

- 既定値は `256` です（`Options::ple_inflight`）。parser は次の引数を `std::atoi` で整数化します。
- 値は `1..1024` に限られます。0、負数、非数値文字列（`atoi` が 0 を返す場合を含む）は共通 validation で拒否されます。整数の後ろに変換できない文字が続く値は `atoi` の変換規則に従い、厳密な文字列全体の整数検証は行いません。
- 同じ option を複数回指定した場合、parser は指定のたびに同じフィールドへ代入するため、最後に解析された値が残ります。
- option 名だけで値が続かない場合、parser の `next` が `--ple-inflight needs a value` を stderr に出し、終了コード 2 で終了します。

## 実行時の動作

有効値は PLE table open 時に `PleIoOptions::max_inflight` へ渡されます。`PleTable::open` は `direct` モードの場合に `PleReader::open` を呼び、その値で slot 数を設定します。reader は slot ごとに `2 * PAGE` の aligned read buffer を確保し、free slot がある間だけ queued job を `DirectFile` に submit するため、同時に保持する読み込み slot 数の上限になります（`src/program/generate.cpp:4033-4040`、`src/kernels/ngram.cpp:340-354`、`src/ngram/ple_reader.cpp:148-177,336-356`）。

`--ple-io mmap` と `--ple-io ram` は mapped table を使う経路で、`PleReader::open` を通りません。このため `--ple-inflight` の検証自体は行われますが、値は mmap/ram の読み込み数を変えません（`src/program/generate.cpp:3181-3184,4033-4040`、`src/kernels/ngram.cpp:340-356`）。

## 適用条件と副作用

- PLE reader が実際に開かれるのは `--ple-gguf` が空でない場合です。指定があると `ple_table.open` が実行され、open に失敗した場合はエラー文字列を stderr に出して終了コード 1 で終了します（`src/program/generate.cpp:4033-4055`）。
- 通常経路では `--ple-gguf` が必須です。`--no-ple` は診断用の PLE 無効化ですが、`--no-ple` と `--ple-gguf` の併用は相互排他エラー（stderr、終了コード 2）になります。`--ple-inflight` 自体の範囲検証は、PLE を使わない設定でも parser 後に行われます（`src/program/generate.cpp:3181-3184,3290-3300`）。
- `--ple-inflight` は PLE 関連の `--ple-io`、`--ple-row-cache`、`--ple-delay-us` と同じ validation 条件で検査されます。無効値では `strata generate: invalid --ple-io/--ple-row-cache/--ple-inflight/--ple-delay-us` を stderr に出して終了コード 2 になります（`src/program/generate.cpp:3181-3184`）。
- ビルドに `STRATA_HAVE_QWEN35` があり、`--native` または `--model` で指定された GGUF が Qwen3.6 系として認識されると、通常 parser より前に `src/qwen35` の parser へ引き渡されます。この別実装の通常実行 parser は `--ple-inflight` をサポートしないため、未対応 option として usage を出し終了コード 2 になります。`--serve` 経路では未知の `--` option とその値を無視する実装です（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3735-3795`）。
- buffer 確保に失敗すると `PleReader::open` は `PleReader: cannot allocate read buffers` を返します。また、worker thread の起動に失敗する場合はエラーを返します。エンジン側ではこれらを含む open エラーを表示して終了します（`src/ngram/ple_reader.cpp:350-378`、`src/program/generate.cpp:4052-4055`）。

## 出力とエラー

通常の値指定は option 固有の出力を行いません。範囲外の値は上記の validation error（stderr、終了コード 2）となります。値欠落も stderr と終了コード 2 です。実際の reader open 失敗は stderr に原因を出し、終了コード 1 となります。

## 根拠

- option の既定値: `src/program/generate.cpp:479-485`
- help 表示: `src/program/generate.cpp:816-826`
- parser と値変換: `src/program/generate.cpp:2416-2421,2473-2479`
- validation: `src/program/generate.cpp:3181-3184`
- PLE 必須条件と `--no-ple` との相互排他: `src/program/generate.cpp:3290-3300`
- PLE 設定の受け渡し: `src/program/generate.cpp:4033-4055`
- direct reader と mmap/ram 経路の違い: `src/kernels/ngram.cpp:340-356`
- slot 上限・buffer 確保・submit 制御: `src/ngram/ple_reader.cpp:148-177,336-378`
- `--native` の Qwen3.6 振り分け: `src/program/generate.cpp:2393-2407`
- 振り分け先 parser の未知 option 処理: `src/qwen35/q36_engine.cu:3735-3795`

