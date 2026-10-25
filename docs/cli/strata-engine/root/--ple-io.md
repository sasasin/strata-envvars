# `--ple-io`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` エンジンの引数 parser（`generate` 実行経路） |
| オプション | `--ple-io` |
| 別名 | なし |
| 値 | `direct`、`mmap`、`ram` のいずれか |

## 役割

PLE（per-layer token embedding）/n-gram テーブルの読み込み方式を選びます。テーブルは `--ple-gguf PATH` で指定します。通常は直接 I/O の `direct`、OS のファイルマッピングを使う `mmap`、マップした全テーブルのページを起動時に読み込んで RAM にロックする `ram` から選びます。エンジンの help では `direct` が既定値と説明されています（`src/program/generate.cpp:819-822`）。

## 使い方

```sh
strata --pack pack/full --tokens "1,2,3" --ple-gguf /models/ple.gguf --ple-io mmap
```

通常 parser の使用例です。実際に PLE を有効にするには `--ple-gguf` が必要で、`--no-ple` と `--ple-gguf` は併用できません（`src/program/generate.cpp:3290-3300`）。

## 値と既定値

- `direct`: 既定値です。テーブル行を非バッファの直接読み込みで取得し、PLE テーブルをプロセスのマップ領域として保持しません。
- `mmap`: PLE を含む GGUF のテーブル領域をマップし、OS のページキャッシュ経由で参照します。
- `ram`: `mmap` と同じマップを使い、起動時にテーブル全体のページを読み込み、可能ならメモリにロックします。

parser は値を文字列として受け取り、同じオプションを複数回指定した場合は後の値が残ります。値の検証は引数解析後に行われ、3種類以外の値は `invalid --ple-io/...` エラーで終了コード 2 になります。値を省略すると `--ple-io needs a value` を stderr に出し、終了コード 2 で終了します（`src/program/generate.cpp:480-481,2418-2421,2475,3181-3185`）。

## 実行時の動作

`--ple-gguf` が指定されていると、`direct` は `PleIo::Direct`、`mmap` と `ram` は `PleIo::Mmap` に変換されます。`ram` の場合だけロック要求も有効にします（`src/program/generate.cpp:4033-4040`）。テーブルの GGUF、tensor 名・形状・形式、データ範囲が不正な場合は開けず、理由を `strata generate:` 付きで stderr に出し、終了コード 1 になります（`src/kernels/ngram.cpp:255-267,271-295,316-337,339-354`; 呼び出し側 `src/program/generate.cpp:4052-4055`）。

`direct` では起動時に短いランダム行読み込み probe を行います。`STRATA_PLE_PROBE` が設定されている場合は probe をスキップします。測定値が 15,000 rows/s 未満で正の値なら通常は警告だけで `direct` を維持します。`STRATA_PLE_AUTO_MMAP` が非ゼロで、かつ `--ple-io` を明示していない場合に限り `mmap` へ切り替えてテーブルを開き直します。従って明示的な `--ple-io direct` は環境変数が有効でも切り替えられません。15,000 rows/s 以上の場合は probe 結果を stderr に表示します（`src/program/generate.cpp:2219-2240,4056-4089`）。環境変数の条件は [`STRATA_PLE_AUTO_MMAP`](../../../STRATA_PLE_AUTO_MMAP.md) の文書も参照してください。

直接読み込みは `--ple-inflight` の同時読み込み数や `--ple-row-cache` の行キャッシュと併用され、`--ple-sync-submit` を付けない限り I/O worker thread を使います。SSD の keep-alive も `direct` の worker 使用時だけ有効です。これらは当オプションとは別の設定ですが、読み込み経路に影響します（`src/program/generate.cpp:4038-4050`）。

## 適用条件と副作用

- `ram` は全テーブルの読み込みを伴うため、テーブル容量分の RAM とページロック可能量が必要です。POSIX では `madvise`、並列ページ読み込み、`mlock` を行います。Windows ではページをロックする helper を使います。ロック失敗時も起動は続きますが、全ページを触れて常駐を試みるだけとなり、ページは回収され得ます。成功・失敗はログに表示されます（`src/kernels/ngram.cpp:356-410`; 表示 `src/program/generate.cpp:4103-4106`）。
- POSIX で `direct` の PLE ファイルが回転ディスク上にあると判定された場合、prompt が長時間停止する可能性について警告します。自動変更はしません（`src/program/generate.cpp:4091-4101`）。
- Windows で PLE shard が expert tensor も含み、expert 側のマップを閉じた場合、`mmap`/`ram` では PLE shard のマッピングを維持するため、そのファイルからの expert 読み込みが直列化される旨を note として出します（`src/program/generate.cpp:8314-8323`）。
- `--ple-gguf` を指定しない通常経路では PLE テーブルの読み込み処理は実行されません。ネイティブモデル経路では対象 shard の自動選択条件もあります（`src/program/generate.cpp:3247-3253,4033`）。

## 出力とエラー

低速 probe、回転ディスクの警告、`ram` のロック状態や失敗、必要に応じて SSD keep-alive の状況は stderr に出ます。PLE ファイルを開けない場合や `mmap` への自動再オープンに失敗した場合はエラーを stderr に出して終了コード 1 です。値の不正や値の欠落は終了コード 2 です（`src/program/generate.cpp:3181-3185,4052-4055,4071-4087,4103-4112`）。

## 根拠

- Parser の既定値・明示指定フラグ: `src/program/generate.cpp:480-481`
- help 記載: `src/program/generate.cpp:819-822`
- 値の引数受け取り: `src/program/generate.cpp:2418-2421,2475`
- 値の検証と終了コード: `src/program/generate.cpp:3181-3185`
- PLE I/O 設定・環境変数・probe・自動 `mmap`・警告: `src/program/generate.cpp:4033-4112`
- GGUF テーブルの形式・サイズ検証と `direct`/`ram` の実装: `src/kernels/ngram.cpp:255-414`
- PLE shard 内の expert 読み込みに関する注意: `src/program/generate.cpp:8314-8323`
