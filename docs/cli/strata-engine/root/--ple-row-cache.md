# `strata generate --ple-row-cache`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジンの root 引数 parser） |
| オプション | `--ple-row-cache` |
| 別名 | なし |
| 値 | 行数を表す整数。0 以上。既定値は 1,048,576 行 |

## 役割

PLE（per-layer token embedding）テーブルを direct 読み込みする際、読み込んだ行を再利用するための上限行数を指定します。0 は行キャッシュを無効にします。この値は PLE テーブルの direct 読み込みに渡され、テーブルを mmap する経路では使われません（`engine/src/program/generate.cpp:820, 6270-6276`、`engine/src/kernels/ngram.hpp:167-175`）。

## 使い方

```sh
strata generate --native model.gguf --ple-gguf ple.gguf --tokens 1,2,3 --ple-row-cache 1048576
```

キャッシュを使わずに direct 読み込みを行う場合は `--ple-row-cache 0` を指定します。例は root parser が受け付ける `--native`、`--ple-gguf`、`--tokens` と本オプションを組み合わせています（`engine/src/program/generate.cpp:3851-3856, 3899-3902`）。

## 値と既定値

- parser の `Options` では `int64_t` の `ple_row_cache` を 1,048,576 に初期化しています（`engine/src/program/generate.cpp:820`）。
- `--ple-row-cache` の次の引数を `std::atoll` で変換します。オプション値の省略時は `--ple-row-cache needs a value` を stderr に出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:3842-3846, 3902`）。
- PLE 関連の共通 validation で負数は拒否されます。エラーは `strata generate: invalid --ple-io/--ple-row-cache/--ple-inflight/--ple-delay-us`、終了コードは 2 です（`engine/src/program/generate.cpp:5009-5012`）。
- parser は変換文字列全体の数値検証や `--ple-row-cache` 固有の上限チェックをしていません。したがって数値に変換できない文字列が `atoll` により 0 になる場合は無効値として拒否されず、負数は拒否されます。桁あふれ時の `atoll` の結果はこの parser から規定できません（同 `3902, 5009-5012`）。
- 同じオプションを複数回指定した場合、引数走査中に値を上書きするため最後の指定が残ります（同 `3842-3846, 3902`）。

## 実行時の動作

`--ple-gguf` が指定されると、parser の値を `PleIoOptions::cache_rows` に設定して PLE テーブルを開きます（`engine/src/program/generate.cpp:6269-6276`）。Direct モードでは `PleTable::open` がこの値を `PleReader::open` に渡し、`RowCache::init` がキャッシュ用のキー配列・行データ・置換位置配列を確保します（`engine/src/kernels/ngram.cpp:449-463`、`engine/src/ngram/ple_reader.cpp:347-368`）。

キャッシュは 8-way set-associative 方式です。指定行数を 8 で割った数を set 数とし、実際の格納枠はその 8 倍です。そのため 8 の倍数でない指定値は、格納枠数が指定値以下に切り下がります。ヒットした行はファイル読み込みをせず出力先へコピーし、読み込み完了した行はキャッシュへ挿入します（`engine/src/ngram/ple_reader.cpp:33-72, 467-482, 515-524, 253-256`）。既定の 1,048,576 行では行データ部分が 90 B × 1,048,576 行に相当し、キーと置換管理用の領域も別に必要です（同 `40-51`、`engine/src/program/generate.cpp:820, 1225`）。

## 適用条件と副作用

- 行キャッシュが参照・更新されるのは direct 読み込みの `PleReader` 経路です。明示的な `--ple-io mmap` / `ram` では `PleIoOptions::mode` が mmap となり、`PleTable::open` は reader を開かず mmap 側を使います（`engine/src/program/generate.cpp:6270-6275`、`engine/src/kernels/ngram.cpp:448-467`）。この場合、本オプションの行数は mmap のページ常駐量を制限しません。
- `--ple-io` を明示せず direct で始めた場合、メモリ常駐ポリシーまたは `STRATA_PLE_AUTO_MMAP` によって後から mmap に切り替わることがあります。切替後は行キャッシュが使われません。direct に戻す失敗経路では、元の `PleIoOptions` を復元して開き直します（`engine/src/program/generate.cpp:6303-6348, 6352-6382`）。
- 0 を指定すると `RowCache::init` の set 数が 0 になり、検索は常に miss、挿入は何もしません（`engine/src/ngram/ple_reader.cpp:45-51, 57-72`）。
- 指定値に比例するメモリを確保します。メモリ不足などの極端に大きい値に対する専用の上限や CLI エラー処理は確認できません（`engine/src/ngram/ple_reader.cpp:45-51, 347-368`）。

## 出力とエラー

負数は前述の共通 validation で拒否され、stderr に共通エラーを出してコード 2 で終了します。0 以上の値でキャッシュ初期化が成功した場合、このオプション固有のメッセージは確認できません。PLE ファイルの open 自体が失敗した場合は `strata generate: <エラー内容>` を stderr に出してコード 1 で終了します（`engine/src/program/generate.cpp:5009-5012, 6288-6290`）。

## 根拠

- `engine/src/program/generate.cpp:817-823` — PLE I/O 設定と既定値。
- `engine/src/program/generate.cpp:1221-1228, 3899-3905` — help 表示と parser。
- `engine/src/program/generate.cpp:5009-5012` — 負値を含む validation と失敗出力。
- `engine/src/program/generate.cpp:6269-6276, 6303-6348, 6352-6382` — PLE open、cache 行数の受け渡し、自動 mmap/ram への切替。
- `engine/src/kernels/ngram.hpp:165-175`、`engine/src/kernels/ngram.cpp:449-463` — I/O mode ごとの処理と `PleReader` への値の引き渡し。
- `engine/src/ngram/ple_reader.cpp:33-72, 347-368, 467-524, 253-256` — キャッシュ容量、検索、初期化、miss 行の挿入。

索引の `strata-engine/root` と現行の `engine/src/program/generate.cpp` parser は一致します。別の SYCL 用 parser にも同じオプションと値の受け渡しが見つかりました（`engine/sycl/src/program/generate.cpp:813, 1941, 2517-2520, 3350-3357`）。ただし `docs/cli/000_cli_tools.md` の `strata-engine` parser 所在欄にはこの SYCL parser が記載されていません。本調査では指定された `strata-engine/root` の文書として共通のオプション動作を記録し、索引は変更していません。
