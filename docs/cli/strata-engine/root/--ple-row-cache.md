# `--ple-row-cache`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ `strata generate`（索引上の scope: `root`） |
| オプション | `--ple-row-cache` |
| 別名 | なし |
| 値 | 非負の整数 `N`（キャッシュ行数上限） |

## 役割

PLE（per-layer token embedding）テーブルから取得した行を、エンジン内の有界行キャッシュに保持する行数を指定します。行が再利用され、かつキャッシュに残っている場合、直接 I/O の再読み込みを省けます。これは読み込み経路の設定であり、PLE の計算自体を無効化する option ではありません。索引ではネイティブ engine の `generate.cpp` parser が対象です（`docs/cli/README.md:12`、同 `:1253`）。

## 使い方

```sh
strata generate --pack ./pack --tokens "1,2,3" --ple-gguf ./table.gguf --ple-row-cache 524288
```

`--ple-gguf` が指定され、PLE テーブルを開く場合にキャッシュ行数が `PleIoOptions` に渡されます（`src/program/generate.cpp:4033-4040`）。

## 値と既定値

- 省略時は `1,048,576` 行です。`--help` の説明では各行を 90 byte としています（`src/program/generate.cpp:482`、同 `:823`）。実際のキャッシュ領域はテーブル形式の row byte 数を使って確保されます。
- `0` はキャッシュなしです。実装は 8-way set-associative cache で、set 数を `N / 8` と整数除算するため、実際の容量は `floor(N / 8) * 8` 行です。8 未満は 0 行になります（`src/ngram/ple_reader.cpp:35-50`、同 `:545-546`）。
- 値は `std::atoll` で読み取り、変換後の値が負なら拒否します。数値として変換できない文字列は `atoll` の結果が 0 になるため、厳密な数値形式検査ではありません。重複指定を拒否する処理はなく、引数ループ上では後の値が前の値を置き換えます（`src/program/generate.cpp:2416-2421`、同 `:2476`、同 `:3181-3184`）。

## 実行時の動作

標準の `generate.cpp` 経路では、`--ple-row-cache` の値を `PleIoOptions::cache_rows` に設定し、直接 I/O の `PleTable::open` から `PleReader` に渡します（`src/program/generate.cpp:4033-4054`、`src/kernels/ngram.cpp:340-354`）。取得要求ごとにキャッシュを調べ、ヒット時は保持済みの行を出力バッファへコピーし、ミス時はテーブル読み込みを組み立てます（`src/ngram/ple_reader.cpp:422-465`）。各 set は 8-way で、置換位置を巡回させます（同 `:35-71`）。

このキャッシュが使われるのは `--ple-io direct`（既定）です。`--ple-io mmap` または `ram` は `PleIo::Mmap` に進み、`PleReader` を開かないため、この行キャッシュは参照されません（`src/program/generate.cpp:479-482`、同 `:4033-4040`、`src/kernels/ngram.cpp:340-356`）。

## 適用条件と副作用

- キャッシュは PLE テーブルを開いたときに初期化されます。`--ple-gguf` が空なら該当する初期化ブロックに入らず、指定値は読み込み処理に使われません（`src/program/generate.cpp:4033-4054`）。
- キャッシュ領域はホストメモリを使います。row data のほか、各行のキーと set ごとの置換情報も確保されるため、ヘルプの「90 byte × 行数」は総メモリ量そのものではありません（`src/ngram/ple_reader.cpp:35-50`）。
- `--ple-row-cache` 自体に明示的な上限はありません。値に応じて `vector` の領域を初期化しますが、この初期化部分には allocation exception を変換する処理が見当たりません。極端に大きな値ではメモリ確保に失敗し得ます（`src/program/generate.cpp:3181-3184`、`src/ngram/ple_reader.cpp:44-50`、同 `:336-378`）。
- 既定のキャッシュ規模が性能やメモリに与える効果は、モデル形式・アクセスパターン・実行環境に依存します。ソース確認だけでは具体的な速度向上量は確定できません。
- `--native` により別 family 実装へ分岐する場合があります。Qwen3.5/3.6 系の parser にはこの option の処理がなく、通常モードでは未対応 option として usage を出して終了コード 2 になります。`--serve` が先に処理されて serve mode になっている場合、未知 option は警告して読み飛ばします（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3735-3795`）。

## 出力とエラー

- 負数など、関連 option の値検証に失敗すると stderr に `strata generate: invalid --ple-io/--ple-row-cache/--ple-inflight/--ple-delay-us` を出し、終了コード 2 で終了します（`src/program/generate.cpp:3181-3184`）。値が欠落した場合は `--ple-row-cache needs a value` を stderr に出し、終了コード 2 で終了します（同 `:2418-2420`）。
- `--ple-gguf` のオープンに失敗した場合は `strata generate: <エラー>` を stderr に出して終了コード 1 になります（同 `:4052-4054`）。
- 直接 I/O の実行終了時には stdout に `ple io` 統計が出力され、キャッシュヒット率と使用行数／容量を確認できます（`src/kernels/ngram.cpp:622-632`、`src/program/generate.cpp:16940`）。

## 根拠

- 索引上のツール範囲・option 配置: `docs/cli/README.md:12`、同 `:1253`
- 既定値・help・parser: `src/program/generate.cpp:482`、同 `:823`、同 `:2476`
- 値検証とエラー: `src/program/generate.cpp:3181-3184`、同 `:2418-2420`
- PLE 条件と option 転送: `src/program/generate.cpp:4033-4054`
- cache 容量・置換・hit/miss: `src/ngram/ple_reader.cpp:35-71`、同 `:336-378`、同 `:422-465`
- Direct と mmap の分岐、統計: `src/kernels/ngram.cpp:340-356`、同 `:622-632`
- 別 family parser への分岐と未対応 option: `src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3735-3795`

調査ではソースと索引を確認し、CLI は実行していません。性能測定、build、GPU 実行、テストは行っていません。
